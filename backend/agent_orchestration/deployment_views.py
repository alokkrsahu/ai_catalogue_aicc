"""
Workflow Deployment API Views
Management endpoints for deployments and public-facing chat endpoint
"""
import logging
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from asgiref.sync import sync_to_async
import asyncio

from users.models import IntelliDocProject, AgentWorkflow
from .models import (
    WorkflowDeployment,
    WorkflowAllowedOrigin,
    WorkflowDeploymentRequest,
    WorkflowDeploymentRequestStatus
)
from .deployment_executor import WorkflowDeploymentExecutor
from .deployment_rate_limiter import WorkflowDeploymentRateLimiter

logger = logging.getLogger('workflow_deployment')


class DeploymentViewSet(viewsets.ViewSet):
    """
    ViewSet for managing workflow deployments
    """
    permission_classes = [IsAuthenticated]
    
    def retrieve(self, request, project_id=None):
        """Get deployment status for a project"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get or create deployment
            deployment, created = WorkflowDeployment.objects.get_or_create(
                project=project,
                defaults={
                    'created_by': request.user,
                    'is_active': False,
                    'rate_limit_per_minute': 10,
                    'workflow': None  # Can be None initially
                }
            )
            
            # Get allowed origins
            allowed_origins = WorkflowAllowedOrigin.objects.filter(
                deployment=deployment
            ).order_by('origin')
            
            origins_data = []
            for origin in allowed_origins:
                origins_data.append({
                    'id': origin.id,
                    'origin': origin.origin,
                    'rate_limit_per_minute': origin.rate_limit_per_minute,
                    'is_active': origin.is_active,
                    'created_at': origin.created_at.isoformat()
                })
            
            # Get workflows for dropdown
            workflows = AgentWorkflow.objects.filter(project=project).order_by('-updated_at')
            workflows_data = []
            for workflow in workflows:
                workflows_data.append({
                    'workflow_id': str(workflow.workflow_id),
                    'name': workflow.name,
                    'description': workflow.description,
                    'status': workflow.status
                })
            
            response_data = {
                'deployment': {
                    'id': deployment.id,
                    'workflow_id': str(deployment.workflow.workflow_id) if deployment.workflow else None,
                    'workflow_name': deployment.workflow.name if deployment.workflow else None,
                    'is_active': deployment.is_active,
                    'endpoint_path': deployment.endpoint_path,
                    'rate_limit_per_minute': deployment.rate_limit_per_minute,
                    'initial_greeting': getattr(deployment, 'initial_greeting', ''),
                    'created_at': deployment.created_at.isoformat(),
                    'updated_at': deployment.updated_at.isoformat()
                },
                'allowed_origins': origins_data,
                'available_workflows': workflows_data
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error retrieving deployment: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve deployment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, project_id=None):
        """Create or update deployment"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            workflow_id = request.data.get('workflow_id')
            if not workflow_id:
                return Response(
                    {'error': 'workflow_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            workflow = get_object_or_404(AgentWorkflow, workflow_id=workflow_id, project=project)
            
            # Get or create deployment
            deployment, created = WorkflowDeployment.objects.get_or_create(
                project=project,
                defaults={
                    'workflow': workflow,
                    'created_by': request.user,
                    'is_active': False,
                    'rate_limit_per_minute': request.data.get('rate_limit_per_minute', 10),
                    'initial_greeting': request.data.get('initial_greeting', 'Hi! I am your AI assistant.')
                }
            )
            
            # Update deployment if it already exists
            if not created:
                # If there's an active deployment for another workflow, deactivate it
                if deployment.is_active and deployment.workflow and deployment.workflow != workflow:
                    deployment.is_active = False
                
                deployment.workflow = workflow
                if 'rate_limit_per_minute' in request.data:
                    deployment.rate_limit_per_minute = request.data['rate_limit_per_minute']
                if 'initial_greeting' in request.data:
                    deployment.initial_greeting = request.data['initial_greeting']
                deployment.save()
            
            logger.info(f"✅ DEPLOYMENT: {'Created' if created else 'Updated'} deployment for project {project.name}")
            
            return Response({
                'id': deployment.id,
                'workflow_id': str(deployment.workflow.workflow_id),
                'workflow_name': deployment.workflow.name,
                'is_active': deployment.is_active,
                'endpoint_path': deployment.endpoint_path,
                'rate_limit_per_minute': deployment.rate_limit_per_minute,
                'initial_greeting': getattr(deployment, 'initial_greeting', 'Hi! I am your AI assistant.'),
                'message': 'Deployment created successfully' if created else 'Deployment updated successfully'
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error creating/updating deployment: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to create/update deployment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['patch'], url_path='toggle')
    def toggle(self, request, project_id=None):
        """Toggle deployment active status"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            deployment = get_object_or_404(WorkflowDeployment, project=project)
            
            # Toggle active status
            new_active_status = not deployment.is_active
            
            # Check if trying to activate without workflow
            if new_active_status and not deployment.workflow:
                return Response(
                    {'error': 'Cannot activate deployment without a workflow. Please select a workflow first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            deployment.is_active = new_active_status
            
            # If activating, ensure no other active deployment exists
            if deployment.is_active:
                # Deactivate any other active deployments for this project (shouldn't happen due to constraint, but safety check)
                WorkflowDeployment.objects.filter(
                    project=project,
                    is_active=True
                ).exclude(id=deployment.id).update(is_active=False)
            
            deployment.save()
            
            logger.info(f"🔄 DEPLOYMENT: Toggled deployment to {'active' if deployment.is_active else 'inactive'} for project {project.name}")
            
            return Response({
                'id': deployment.id,
                'is_active': deployment.is_active,
                'message': f'Deployment {"activated" if deployment.is_active else "deactivated"} successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error toggling deployment: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to toggle deployment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='origins')
    def list_origins(self, request, project_id=None):
        """List allowed origins for deployment"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get deployment - return empty list if doesn't exist yet
            try:
                deployment = WorkflowDeployment.objects.get(project=project)
            except WorkflowDeployment.DoesNotExist:
                return Response({'origins': []})
            
            origins = WorkflowAllowedOrigin.objects.filter(
                deployment=deployment
            ).order_by('origin')
            
            origins_data = []
            for origin in origins:
                origins_data.append({
                    'id': origin.id,
                    'origin': origin.origin,
                    'rate_limit_per_minute': origin.rate_limit_per_minute,
                    'is_active': origin.is_active,
                    'created_at': origin.created_at.isoformat(),
                    'updated_at': origin.updated_at.isoformat()
                })
            
            return Response({'origins': origins_data})
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error listing origins: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to list origins'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='origins')
    def add_origin(self, request, project_id=None):
        """Add allowed origin"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get deployment - must exist before adding origins
            try:
                deployment = WorkflowDeployment.objects.get(project=project)
            except WorkflowDeployment.DoesNotExist:
                return Response(
                    {'error': 'Deployment does not exist. Please save deployment configuration first by selecting a workflow.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            origin = request.data.get('origin', '').strip()
            if not origin:
                return Response(
                    {'error': 'origin is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate origin format (basic validation)
            if not (origin.startswith('http://') or origin.startswith('https://')):
                return Response(
                    {'error': 'Origin must start with http:// or https://'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Normalize origin (remove trailing slash and ensure no double protocol)
            origin = origin.rstrip('/')
            # Fix double https:// or http://
            if origin.startswith('https://https://') or origin.startswith('http://http://'):
                origin = origin.replace('https://https://', 'https://').replace('http://http://', 'http://')
            
            rate_limit = request.data.get('rate_limit_per_minute', deployment.rate_limit_per_minute)
            
            # Create or update origin
            allowed_origin, created = WorkflowAllowedOrigin.objects.get_or_create(
                deployment=deployment,
                origin=origin,
                defaults={
                    'rate_limit_per_minute': rate_limit,
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing origin
                allowed_origin.rate_limit_per_minute = rate_limit
                allowed_origin.is_active = True
                allowed_origin.save()
            
            logger.info(f"✅ DEPLOYMENT: {'Added' if created else 'Updated'} origin {origin} for project {project.name}")
            
            return Response({
                'id': allowed_origin.id,
                'origin': allowed_origin.origin,
                'rate_limit_per_minute': allowed_origin.rate_limit_per_minute,
                'is_active': allowed_origin.is_active,
                'message': 'Origin added successfully' if created else 'Origin updated successfully'
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error adding origin: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to add origin'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'], url_path='origins/(?P<origin_id>[^/.]+)')
    def remove_origin(self, request, project_id=None, origin_id=None):
        """Remove allowed origin"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get deployment (must exist to have origins)
            try:
                deployment = WorkflowDeployment.objects.get(project=project)
            except WorkflowDeployment.DoesNotExist:
                return Response(
                    {'error': 'No deployment found for this project'},
                    status=status.HTTP_404_NOT_FOUND
                )
            origin = get_object_or_404(WorkflowAllowedOrigin, id=origin_id, deployment=deployment)
            
            origin.delete()
            
            logger.info(f"🗑️ DEPLOYMENT: Removed origin {origin.origin} for project {project.name}")
            
            return Response({'message': 'Origin removed successfully'})
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error removing origin: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to remove origin'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['patch'], url_path='origins/(?P<origin_id>[^/.]+)')
    def update_origin(self, request, project_id=None, origin_id=None):
        """Update origin rate limit or active status"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check project access
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get deployment (must exist to have origins)
            try:
                deployment = WorkflowDeployment.objects.get(project=project)
            except WorkflowDeployment.DoesNotExist:
                return Response(
                    {'error': 'No deployment found for this project'},
                    status=status.HTTP_404_NOT_FOUND
                )
            origin = get_object_or_404(WorkflowAllowedOrigin, id=origin_id, deployment=deployment)
            
            # Update fields
            if 'rate_limit_per_minute' in request.data:
                origin.rate_limit_per_minute = request.data['rate_limit_per_minute']
            if 'is_active' in request.data:
                origin.is_active = request.data['is_active']
            
            origin.save()
            
            logger.info(f"🔄 DEPLOYMENT: Updated origin {origin.origin} for project {project.name}")
            
            return Response({
                'id': origin.id,
                'origin': origin.origin,
                'rate_limit_per_minute': origin.rate_limit_per_minute,
                'is_active': origin.is_active,
                'message': 'Origin updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error updating origin: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to update origin'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Public endpoint (unauthenticated)
@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@never_cache
def public_chat_endpoint(request, project_id):
    """
    Public chat endpoint for deployed workflows
    
    POST /api/workflow-deploy/{project_id}/
    """
    # Handle CORS preflight (middleware should handle this, but safety check)
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        return response
    
    # Generate unique request ID
    origin = request.META.get('HTTP_ORIGIN', '')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    request_id = f"deploy_{timestamp}_{hash(origin) % 10000:04d}_{uuid.uuid4().hex[:8]}"
    
    # Initialize tracking
    deployment_request = None
    start_time = timezone.now()
    
    try:
        # Get project and deployment
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'error': 'Project not found',
                'request_id': request_id
            }, status=404)
        
        deployment = WorkflowDeployment.objects.filter(
            project=project,
            is_active=True
        ).first()
        
        if not deployment:
            return JsonResponse({
                'status': 'error',
                'error': 'No active deployment found for this project',
                'request_id': request_id
            }, status=404)
        
        if not deployment.workflow:
            return JsonResponse({
                'status': 'error',
                'error': 'Deployment has no workflow configured',
                'request_id': request_id
            }, status=400)
        
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'error': 'Invalid JSON format',
                'request_id': request_id
            }, status=400)
        
        # Extract message
        message = data.get('message', '').strip()
        session_id = data.get('session_id', '')
        
        if not message:
            return JsonResponse({
                'status': 'error',
                'error': 'Message is required',
                'request_id': request_id
            }, status=400)
        
        # Validate message length
        if len(message) > 1000:
            return JsonResponse({
                'status': 'error',
                'error': 'Message too long (max 1000 characters)',
                'request_id': request_id
            }, status=400)
        
        # Check rate limit
        rate_limiter = WorkflowDeploymentRateLimiter()
        is_allowed, retry_after = rate_limiter.check_rate_limit(deployment, origin)
        
        if not is_allowed:
            # Create tracking record
            try:
                deployment_request = WorkflowDeploymentRequest.objects.create(
                    deployment=deployment,
                    origin=origin,
                    request_id=request_id,
                    session_id=session_id[:100] if session_id else None,
                    message_preview=message[:100],
                    status=WorkflowDeploymentRequestStatus.RATE_LIMITED,
                    response_generated=False
                )
            except Exception:
                pass
            
            return JsonResponse({
                'status': 'error',
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': retry_after,
                'request_id': request_id
            }, status=429)
        
        # Create tracking record
        try:
            deployment_request = WorkflowDeploymentRequest.objects.create(
                deployment=deployment,
                origin=origin,
                request_id=request_id,
                session_id=session_id[:100] if session_id else None,
                message_preview=message[:100],
                status=WorkflowDeploymentRequestStatus.SUCCESS,
                response_generated=False
            )
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Failed to create request record: {e}")
        
        # Execute workflow
        executor = WorkflowDeploymentExecutor()
        
        # Run async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            execution_result = loop.run_until_complete(
                executor.execute_deployment_workflow(
                    deployment,
                    message,
                    session_id
                )
            )
        finally:
            loop.close()
        
        execution_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        
        # Update tracking record
        if deployment_request:
            try:
                deployment_request.response_generated = execution_result.get('status') == 'success'
                deployment_request.status = (
                    WorkflowDeploymentRequestStatus.SUCCESS
                    if execution_result.get('status') == 'success'
                    else WorkflowDeploymentRequestStatus.ERROR
                )
                deployment_request.execution_time_ms = execution_time_ms
                if execution_result.get('error'):
                    deployment_request.error_message = execution_result['error']
                deployment_request.save()
            except Exception as e:
                logger.error(f"❌ DEPLOYMENT: Failed to update request record: {e}")
        
        # Return response
        if execution_result.get('status') == 'success':
            return JsonResponse({
                'status': 'success',
                'response': execution_result.get('response', ''),
                'metadata': {
                    'request_id': request_id,
                    'execution_time_ms': execution_time_ms,
                    'workflow_name': execution_result.get('workflow_name', '')
                }
            })
        else:
            return JsonResponse({
                'status': 'error',
                'error': execution_result.get('error', 'Workflow execution failed'),
                'request_id': request_id
            }, status=500)
        
    except Exception as e:
        logger.error(f"❌ DEPLOYMENT: Error in public endpoint: {e}", exc_info=True)
        
        # Update tracking record
        if deployment_request:
            try:
                deployment_request.status = WorkflowDeploymentRequestStatus.ERROR
                deployment_request.error_message = str(e)
                deployment_request.execution_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                deployment_request.save()
            except Exception:
                pass
        
        return JsonResponse({
            'status': 'error',
            'error': 'An error occurred while processing your request',
            'request_id': request_id
        }, status=500)


@csrf_exempt
def embed_chatbot_html(request, project_id):
    """
    Serve the chatbot HTML for iframe embedding.
    This endpoint returns a complete HTML page with the chatbot interface.
    """
    from django.shortcuts import get_object_or_404
    from django.http import HttpResponse
    from users.models import IntelliDocProject
    
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        deployment = WorkflowDeployment.objects.filter(
            project=project,
            is_active=True
        ).first()
        
        if not deployment or not deployment.workflow:
            return HttpResponse(
                '<html><body><p>Chatbot not available. Please ensure deployment is active and a workflow is configured.</p></body></html>',
                status=404,
                content_type='text/html'
            )
        
        # Get the endpoint URL
        base_url = request.build_absolute_uri('/').rstrip('/')
        endpoint_url = f"{base_url}{deployment.endpoint_path}"
        initial_greeting = getattr(deployment, 'initial_greeting', 'Hi! I am your AI assistant.')
        
        # Generate the HTML
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AICC Workflow Chatbot</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; background:#f5f5f7; margin:0; padding:0; display:flex; justify-content:center; align-items:center; height:100vh; }}
    .chat-container {{ width: 420px; max-width: 100%; height: 620px; background:#ffffff; border-radius:16px; box-shadow:0 18px 45px rgba(15,23,42,0.18); display:flex; flex-direction:column; overflow:hidden; }}
    .chat-header {{ padding:14px 18px; background:#0b3b66; color:#fff; display:flex; align-items:center; justify-content:space-between; }}
    .chat-header-title {{ font-weight:600; font-size:15px; }}
    .chat-header-sub {{ font-size:11px; opacity:0.8; }}
    .chat-messages {{ flex:1; padding:14px 16px; overflow-y:auto; background:#f9fafb; font-size:14px; }}
    .msg {{ margin-bottom:10px; display:flex; }}
    .msg.user {{ justify-content:flex-end; }}
    .msg.assistant {{ justify-content:flex-start; }}
    .bubble {{ max-width:80%; padding:8px 11px; border-radius:12px; line-height:1.4; }}
    .msg.user .bubble {{ background:#0b3b66; color:#fff; border-bottom-right-radius:4px; }}
    .msg.assistant .bubble {{ background:#ffffff; border:1px solid #e5e7eb; color:#111827; border-bottom-left-radius:4px; }}
    .chat-input {{ padding:10px 12px; border-top:1px solid #e5e7eb; background:#ffffff; display:flex; gap:8px; }}
    .chat-input textarea {{ flex:1; resize:none; border:1px solid #d1d5db; border-radius:10px; padding:8px 10px; font-size:13px; max-height:80px; }}
    .chat-input button {{ background:#0b3b66; color:#fff; border:none; border-radius:10px; padding:0 14px; font-size:13px; cursor:pointer; display:flex; align-items:center; gap:6px; }}
    .chat-input button:disabled {{ opacity:0.6; cursor:not-allowed; }}
    .status {{ font-size:11px; color:#6b7280; padding:4px 12px 8px; }}
  </style>
</head>
<body>
<div class="chat-container">
  <div class="chat-header">
    <div>
      <div class="chat-header-title">AICC Workflow Chatbot</div>
      <div class="chat-header-sub">Powered by your deployed agent workflow</div>
    </div>
  </div>
  <div id="messages" class="chat-messages"></div>
  <div id="status" class="status"></div>
  <div class="chat-input">
    <textarea id="input" rows="1" placeholder="Ask a question about your documents..."></textarea>
    <button id="sendBtn">
      <span>Send</span>
    </button>
  </div>
</div>

<script>
  const ENDPOINT_URL = {json.dumps(endpoint_url)};
  const INITIAL_GREETING = {json.dumps(initial_greeting)};

  const messages = [];
  const sessionId = 'sess_' + Math.random().toString(36).slice(2);

  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('sendBtn');
  const statusEl = document.getElementById('status');

  function appendMessage(role, text) {{
    const msg = document.createElement('div');
    msg.className = 'msg ' + (role === 'user' ? 'user' : 'assistant');
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    msg.appendChild(bubble);
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }}

  function serializeConversation() {{
    return messages
      .map(m => (m.role === 'user' ? 'User' : 'Assistant') + ': ' + m.content)
      .join('\\n');
  }}

  async function sendMessage() {{
    const text = inputEl.value.trim();
    if (!text) return;

    appendMessage('user', text);
    messages.push({{ role: 'user', content: text }});

    inputEl.value = '';
    sendBtn.disabled = true;
    statusEl.textContent = 'Contacting workflow...';

    const fullPrompt = serializeConversation();

    try {{
      const resp = await fetch(ENDPOINT_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          message: fullPrompt,
          session_id: sessionId,
          conversation: messages
        }})
      }});

      if (!resp.ok) {{
        const err = await resp.json().catch(() => ({{}}));
        throw new Error(err.error || 'HTTP ' + resp.status);
      }}

      const data = await resp.json();
      if (data.status === 'success') {{
        const reply = data.response || '(No response)';
        appendMessage('assistant', reply);
        messages.push({{ role: 'assistant', content: reply }});
        statusEl.textContent = '';
      }} else {{
        appendMessage('assistant', 'Error: ' + (data.error || 'Unexpected error'));
        statusEl.textContent = 'Error from workflow endpoint';
      }}
    }} catch (e) {{
      console.error('Chat error:', e);
      appendMessage('assistant', 'Sorry, there was a problem talking to the workflow.');
      statusEl.textContent = e.message || 'Network error';
    }} finally {{
      sendBtn.disabled = false;
    }}
  }}

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter' && !e.shiftKey) {{
      e.preventDefault();
      sendMessage();
    }}
  }});

  // Initial greeting
  appendMessage('assistant', INITIAL_GREETING);
  messages.push({{ role: 'assistant', content: INITIAL_GREETING }});
</script>
</body>
</html>'''
        
        return HttpResponse(html_content, content_type='text/html')
        
    except Exception as e:
        logger.error(f"❌ DEPLOYMENT: Error serving embed HTML: {e}", exc_info=True)
        return HttpResponse(
            '<html><body><p>Error loading chatbot. Please try again later.</p></body></html>',
            status=500,
            content_type='text/html'
        )

