"""
Workflow Deployment API Views
Management endpoints for deployments and public-facing chat endpoint.

Deployment / chat limitations (see DEPLOYMENT_CHAT_LIMITATIONS.md in project root):
- No user file upload in embed chat; attachments come from workflow config only.
- Streaming is simulated (full response then word-by-word); not true LLM token streaming.
- Concurrent requests with the same session_id can overwrite turns; no per-session locking.
"""
import logging
import json
import queue as queue_mod
import uuid
import hashlib
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404
from django.db import transaction
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
    WorkflowDeploymentRequestStatus,
    DeploymentSession,
    DeploymentExecution
)
from .deployment_executor import WorkflowDeploymentExecutor
from .deployment_rate_limiter import WorkflowDeploymentRateLimiter

logger = logging.getLogger('workflow_deployment')


def _embed_hex_to_rgb_csv(hex_color: str, fallback_rgb: str) -> str:
    """
    Convert #RRGGBB or #RGB to 'r, g, b' for CSS --*-rgb custom properties.
    Invalid or non-hex values return fallback_rgb (comma-separated decimals).
    """
    if not hex_color or not isinstance(hex_color, str):
        return fallback_rgb
    h = hex_color.strip().lstrip('#')
    try:
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        if len(h) != 6:
            return fallback_rgb
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'{r}, {g}, {b}'
    except ValueError:
        return fallback_rgb


def _add_cors_headers(response, request):
    """Add CORS headers to response"""
    origin = request.META.get('HTTP_ORIGIN', '')
    if origin:
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
    else:
        response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


def _save_session_conversation_sync(deployment_session, conversation_history):
    """
    Persist current conversation_history to the deployment session (sync).
    Used when returning an error (e.g. rate limit) so the user message is not lost.
    """
    if conversation_history is None:
        return
    try:
        deployment_session.conversation_history = conversation_history
        deployment_session.message_count = len(conversation_history)
        deployment_session.last_activity = timezone.now()
        deployment_session.save()
        logger.info(f"💾 DEPLOYMENT: Saved session {deployment_session.session_id[:8]} on rate limit ({deployment_session.message_count} messages)")
    except Exception as e:
        logger.error(f"❌ DEPLOYMENT: Failed to save session on rate limit: {e}", exc_info=True)


def _save_deployment_data_async(
    deployment_session,
    conversation_history,
    assistant_response,
    execution_id,
    deployment_request,
    execution_result,
    execution_time_ms,
    workflow_execution_id,
    user_query
):
    """
    Background task to save deployment data after response is sent to client.
    This function runs in a separate thread to avoid blocking the response.
    """
    from django.db import close_old_connections
    
    # Ensure fresh database connection for this thread
    close_old_connections()
    
    try:
        # Update session whenever conversation_history is provided (success or failure)
        # So user message is never lost when a turn fails
        if conversation_history is not None:
            deployment_session.conversation_history = conversation_history
            deployment_session.message_count = len(conversation_history)
            deployment_session.last_activity = timezone.now()
            deployment_session.save()
            logger.info(f"💾 DEPLOYMENT: Updated session {deployment_session.session_id[:8]} with {deployment_session.message_count} messages (background)")
        
        # Try to get WorkflowExecution (non-blocking, optional)
        workflow_execution = None
        if workflow_execution_id:
            try:
                from users.models import WorkflowExecution
                workflow_execution = WorkflowExecution.objects.filter(execution_id=workflow_execution_id).first()
            except Exception as e:
                logger.warning(f"⚠️ DEPLOYMENT: Could not link to WorkflowExecution {workflow_execution_id}: {e}")
        
        # Create DeploymentExecution record
        try:
            from .models import DeploymentExecution, WorkflowDeploymentRequestStatus
            DeploymentExecution.objects.create(
                execution_id=execution_id,
                deployment_session=deployment_session,
                workflow_execution=workflow_execution,
                user_query=user_query,
                assistant_response=assistant_response,
                execution_time_ms=execution_time_ms,
                status=(
                    WorkflowDeploymentRequestStatus.SUCCESS
                    if execution_result.get('status') == 'success'
                    else WorkflowDeploymentRequestStatus.ERROR
                ),
                error_message=execution_result.get('error', '') if execution_result.get('status') != 'success' else None
            )
            logger.info(f"📝 DEPLOYMENT: Created execution record {execution_id[:8]} for session {deployment_session.session_id[:8]} (background)")
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Failed to create execution record in background: {e}", exc_info=True)
        
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
                logger.debug(f"📊 DEPLOYMENT: Updated request record {deployment_request.request_id[:8]} (background)")
            except Exception as e:
                logger.error(f"❌ DEPLOYMENT: Failed to update request record in background: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"❌ DEPLOYMENT: Error in background save task: {e}", exc_info=True)
    finally:
        # Clean up database connection for this thread
        close_old_connections()


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
                    # Chatbot branding customization
                    'chatbot_title': getattr(deployment, 'chatbot_title', 'AI Assistant'),
                    'chatbot_subtitle': getattr(deployment, 'chatbot_subtitle', 'Powered by AICC IntelliDoc'),
                    'primary_color': getattr(deployment, 'primary_color', '#78b2e8'),
                    'secondary_color': getattr(deployment, 'secondary_color', '#3a6d98'),
                    'logo_url': getattr(deployment, 'logo_url', None),
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
                    'initial_greeting': request.data.get('initial_greeting', 'Hi! I am your AI assistant.'),
                    # Chatbot branding customization
                    'chatbot_title': request.data.get('chatbot_title', 'AI Assistant'),
                    'chatbot_subtitle': request.data.get('chatbot_subtitle', 'Powered by AICC IntelliDoc'),
                    'primary_color': request.data.get('primary_color', '#78b2e8'),
                    'secondary_color': request.data.get('secondary_color', '#3a6d98'),
                    'logo_url': request.data.get('logo_url', None)
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
                # Handle chatbot branding customization
                if 'chatbot_title' in request.data:
                    deployment.chatbot_title = request.data['chatbot_title']
                if 'chatbot_subtitle' in request.data:
                    deployment.chatbot_subtitle = request.data['chatbot_subtitle']
                if 'primary_color' in request.data:
                    deployment.primary_color = request.data['primary_color']
                if 'secondary_color' in request.data:
                    deployment.secondary_color = request.data['secondary_color']
                if 'logo_url' in request.data:
                    deployment.logo_url = request.data['logo_url']
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
                # Chatbot branding customization
                'chatbot_title': getattr(deployment, 'chatbot_title', 'AI Assistant'),
                'chatbot_subtitle': getattr(deployment, 'chatbot_subtitle', 'Powered by AICC IntelliDoc'),
                'primary_color': getattr(deployment, 'primary_color', '#78b2e8'),
                'secondary_color': getattr(deployment, 'secondary_color', '#3a6d98'),
                'logo_url': getattr(deployment, 'logo_url', None),
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
    
    @action(detail=False, methods=['get'], url_path='projects/(?P<project_id>[^/.]+)/deployment/activity')
    def get_deployment_activity(self, request, project_id=None):
        """
        Get all deployment sessions and their conversation history for Activity Tracker
        GET /api/agent-orchestration/projects/{project_id}/deployment/activity/
        """
        try:
            # Get project
            try:
                project = IntelliDocProject.objects.get(project_id=project_id)
            except IntelliDocProject.DoesNotExist:
                return Response(
                    {'error': 'Project not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have permission to access this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get deployment
            try:
                deployment = WorkflowDeployment.objects.get(project=project)
            except WorkflowDeployment.DoesNotExist:
                return Response({
                    'sessions': [],
                    'total_sessions': 0,
                    'message': 'No deployment found for this project'
                })
            
            # Get query parameters
            session_id_filter = request.query_params.get('session_id', '').strip()
            limit = int(request.query_params.get('limit', 50))
            offset = int(request.query_params.get('offset', 0))
            
            # Query sessions
            sessions_query = DeploymentSession.objects.filter(deployment=deployment)
            
            if session_id_filter:
                # Exact match so preload / activity lookup returns the intended session (icontains can match wrong rows)
                sessions_query = sessions_query.filter(session_id=session_id_filter)
            
            total_sessions = sessions_query.count()
            sessions = sessions_query.order_by('-last_activity')[offset:offset + limit]
            
            # Build response
            sessions_data = []
            for session in sessions:
                # Get executions for this session
                executions = DeploymentExecution.objects.filter(
                    deployment_session=session
                ).order_by('created_at')[:100]  # Limit to recent 100 executions
                
                sessions_data.append({
                    'session_id': session.session_id,
                    'message_count': session.message_count,
                    'is_active': session.is_active,
                    'created_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat(),
                    'conversation_history': session.conversation_history or [],
                    'executions': [
                        {
                            'execution_id': exec.execution_id,
                            'user_query': exec.user_query,
                            'assistant_response': exec.assistant_response,
                            'execution_time_ms': exec.execution_time_ms,
                            'status': exec.status,
                            'created_at': exec.created_at.isoformat(),
                            'workflow_execution_id': exec.workflow_execution.execution_id if exec.workflow_execution else None
                        }
                        for exec in executions
                    ]
                })
            
            logger.info(f"📊 DEPLOYMENT: Retrieved {len(sessions_data)} sessions for project {project.name}")
            
            return Response({
                'sessions': sessions_data,
                'total_sessions': total_sessions,
                'limit': limit,
                'offset': offset
            })
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error getting deployment activity: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve deployment activity'},
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
        
        # Extract user query and session_id (client now sends only current query)
        user_query = data.get('user_query', '').strip()
        # Fallback to 'message' for backward compatibility
        if not user_query:
            user_query = data.get('message', '').strip()
        session_id = data.get('session_id', '').strip()
        
        if not user_query:
            return JsonResponse({
                'status': 'error',
                'error': 'User query is required',
                'request_id': request_id
            }, status=400)
        
        if not session_id:
            return JsonResponse({
                'status': 'error',
                'error': 'Session ID is required',
                'request_id': request_id
            }, status=400)
        
        # Validate message length
        if len(user_query) > 1000:
            return JsonResponse({
                'status': 'error',
                'error': 'Message too long (max 1000 characters)',
                'request_id': request_id
            }, status=400)
        
        # Get or create deployment session.
        # Note: No per-session locking; concurrent requests with same session_id can overwrite (last save wins).
        # Embed UI should disable send while a request is in flight (see DEPLOYMENT_CHAT_LIMITATIONS.md).
        try:
            deployment_session, created = DeploymentSession.objects.get_or_create(
                deployment=deployment,
                session_id=session_id,
                defaults={
                    'conversation_history': [],
                    'message_count': 0,
                    'is_active': True
                }
            )
            
            conversation_history = deployment_session.conversation_history or []
            
            if created:
                # Add initial greeting for new sessions
                initial_greeting = getattr(deployment, 'initial_greeting', 'Hi! I am your AI assistant.')
                conversation_history.append({
                    'role': 'assistant',
                    'content': initial_greeting,
                    'timestamp': timezone.now().isoformat()
                })
                logger.info(f"🆕 DEPLOYMENT: Created new session {session_id[:8]} for project {project.name} with initial greeting")
            else:
                logger.info(f"🔄 DEPLOYMENT: Retrieved existing session {session_id[:8]} with {deployment_session.message_count} messages")
            
            # Add user query to conversation history
            conversation_history.append({
                'role': 'user',
                'content': user_query,
                'timestamp': timezone.now().isoformat()
            })
            
            # Build full conversation history string for workflow execution
            # Format: "Assistant: greeting\nUser: query1\nAssistant: response1\nUser: query2..."
            conversation_text_parts = []
            for msg in conversation_history:
                role_label = 'User' if msg['role'] == 'user' else 'Assistant'
                conversation_text_parts.append(f"{role_label}: {msg['content']}")
            
            full_conversation = '\n'.join(conversation_text_parts)
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error managing session: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'error': 'Failed to manage session',
                'request_id': request_id
            }, status=500)
        
        # Check rate limit
        rate_limiter = WorkflowDeploymentRateLimiter()
        is_allowed, retry_after = rate_limiter.check_rate_limit(deployment, origin)
        
        if not is_allowed:
            # Persist user message so it is not lost (session persistence on failure)
            _save_session_conversation_sync(deployment_session, conversation_history)
            # Create tracking record
            try:
                deployment_request = WorkflowDeploymentRequest.objects.create(
                    deployment=deployment,
                    origin=origin,
                    request_id=request_id,
                    session_id=session_id[:100] if session_id else None,
                    message_preview=user_query[:100],
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
        
        # Create tracking record (will be updated after execution)
        try:
            deployment_request = WorkflowDeploymentRequest.objects.create(
                deployment=deployment,
                origin=origin,
                request_id=request_id,
                session_id=session_id[:100] if session_id else None,
                message_preview=user_query[:100],
                status=WorkflowDeploymentRequestStatus.SUCCESS,
                response_generated=False
            )
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Failed to create request record: {e}")
        
        # Execute workflow with full conversation history
        executor = WorkflowDeploymentExecutor()
        
        # Generate unique execution ID
        execution_id = f"deploy_exec_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Run async execution - use asyncio.run() for better efficiency
        try:
            execution_result = asyncio.run(
                executor.execute_deployment_workflow(
                    deployment,
                    full_conversation,
                    session_id,
                    execution_id,
                    current_user_query=user_query  # Pass current user query for UserProxyAgent handling
                )
            )
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Error executing workflow: {e}", exc_info=True)
            _exec_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            _fail_result = {'status': 'error', 'error': 'Workflow execution failed'}
            threading.Thread(
                target=_save_deployment_data_async,
                args=(
                    deployment_session,
                    conversation_history,
                    '',
                    execution_id,
                    deployment_request,
                    _fail_result,
                    _exec_time_ms,
                    None,
                    user_query
                ),
                daemon=True,
                name=f"deploy-save-fail-{execution_id[:8]}"
            ).start()
            return JsonResponse({
                'status': 'error',
                'error': 'Workflow execution failed',
                'request_id': request_id
            }, status=500)
        
        execution_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        
        # Extract assistant response
        assistant_response = execution_result.get('response', '') if execution_result.get('status') == 'success' else ''
        
        # Add assistant response to conversation history for background save
        if assistant_response:
            conversation_history.append({
                'role': 'assistant',
                'content': assistant_response,
                'timestamp': timezone.now().isoformat()
            })
        
        # Get workflow_execution_id for background task
        workflow_execution_id = execution_result.get('execution_id')
        
        # Start background task to save all deployment data (non-blocking)
        # Session is persisted even on failure (awaiting_human_input / error) so user message is not lost
        background_thread = threading.Thread(
            target=_save_deployment_data_async,
            args=(
                deployment_session,
                conversation_history,
                assistant_response,
                execution_id,
                deployment_request,
                execution_result,
                execution_time_ms,
                workflow_execution_id,
                user_query
            ),
            daemon=True,
            name=f"deploy-save-{execution_id[:8]}"
        )
        background_thread.start()
        logger.debug(f"🚀 DEPLOYMENT: Started background save task for execution {execution_id[:8]}")
        
        # Return response immediately (don't wait for database writes)
        if execution_result.get('status') == 'success':
            return JsonResponse({
                'status': 'success',
                'response': assistant_response,
                'metadata': {
                    'request_id': request_id,
                    'execution_time_ms': execution_time_ms,
                    'workflow_name': execution_result.get('workflow_name', ''),
                    'session_id': session_id
                }
            })
        elif execution_result.get('status') == 'awaiting_human_input':
            # UserProxyAgent requires human input - return special response
            return JsonResponse({
                'status': 'awaiting_human_input',
                'human_input_required': True,
                'title': execution_result.get('title', 'USER INPUT REQUIRED'),
                'last_conversation_message': execution_result.get('last_conversation_message', ''),
                'agent_name': execution_result.get('agent_name', ''),
                'execution_id': execution_result.get('execution_id', ''),
                'session_id': session_id,
                'metadata': {
                    'request_id': request_id,
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
@require_http_methods(["POST", "OPTIONS"])
@never_cache
def public_chat_endpoint_stream(request, project_id):
    """
    Public streaming chat endpoint for deployed workflows
    
    POST /api/workflow-deploy/{project_id}/stream/
    Returns Server-Sent Events (SSE) stream
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        _add_cors_headers(response, request)
        return response
    
    def generate_stream():
        """Generator function for SSE streaming"""
        deployment_session = None
        conversation_history = None
        try:
            # Generate unique request ID
            origin = request.META.get('HTTP_ORIGIN', '')
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            request_id = f"deploy_stream_{timestamp}_{hash(origin) % 10000:04d}_{uuid.uuid4().hex[:8]}"
            
            start_time = timezone.now()
            
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'request_id': request_id})}\n\n"
            
            # Get project and deployment
            try:
                project = IntelliDocProject.objects.get(project_id=project_id)
            except IntelliDocProject.DoesNotExist:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Project not found', 'request_id': request_id})}\n\n"
                return
            
            deployment = WorkflowDeployment.objects.filter(
                project=project,
                is_active=True
            ).first()
            
            if not deployment:
                yield f"data: {json.dumps({'type': 'error', 'error': 'No active deployment found', 'request_id': request_id})}\n\n"
                return
            
            if not deployment.workflow:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Deployment has no workflow configured', 'request_id': request_id})}\n\n"
                return
            
            # Parse request body
            try:
                data = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Invalid JSON format', 'request_id': request_id})}\n\n"
                return
            
            # Extract user query and session_id
            user_query = data.get('user_query', '').strip()
            if not user_query:
                user_query = data.get('message', '').strip()
            session_id = data.get('session_id', '').strip()
            
            if not user_query or not session_id:
                yield f"data: {json.dumps({'type': 'error', 'error': 'User query and session ID are required', 'request_id': request_id})}\n\n"
                return
            
            # Get or create deployment session
            try:
                deployment_session, created = DeploymentSession.objects.get_or_create(
                    deployment=deployment,
                    session_id=session_id,
                    defaults={
                        'conversation_history': [],
                        'message_count': 0,
                        'is_active': True
                    }
                )
                
                conversation_history = deployment_session.conversation_history or []
                
                if created:
                    initial_greeting = getattr(deployment, 'initial_greeting', 'Hi! I am your AI assistant.')
                    conversation_history.append({
                        'role': 'assistant',
                        'content': initial_greeting,
                        'timestamp': timezone.now().isoformat()
                    })
                
                # Add user query to conversation history
                conversation_history.append({
                    'role': 'user',
                    'content': user_query,
                    'timestamp': timezone.now().isoformat()
                })
                
                # Build conversation history string
                conversation_text_parts = []
                for msg in conversation_history:
                    role_label = 'User' if msg['role'] == 'user' else 'Assistant'
                    conversation_text_parts.append(f"{role_label}: {msg['content']}")
                
                full_conversation = '\n'.join(conversation_text_parts)
                
            except Exception as e:
                logger.error(f"❌ DEPLOYMENT STREAM: Error managing session: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': 'Failed to manage session', 'request_id': request_id})}\n\n"
                return
            
            # Check rate limit
            rate_limiter = WorkflowDeploymentRateLimiter()
            is_allowed, retry_after = rate_limiter.check_rate_limit(deployment, origin)
            
            if not is_allowed:
                # Persist user message so it is not lost (session persistence on failure)
                _save_session_conversation_sync(deployment_session, conversation_history)
                yield f"data: {json.dumps({'type': 'error', 'error': 'Rate limit exceeded', 'retry_after': retry_after, 'request_id': request_id})}\n\n"
                return
            
            # Send thinking indicator
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"
            
            # Execute workflow in background thread with event queue
            executor = WorkflowDeploymentExecutor()
            execution_id = f"deploy_exec_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            event_queue = queue_mod.Queue()

            def _emit_event(event_type, data):
                event_queue.put({"type": event_type, **data})

            result_holder = [None, None]  # [result, error]

            def _run_workflow():
                try:
                    result_holder[0] = asyncio.run(
                        executor.execute_deployment_workflow(
                            deployment,
                            full_conversation,
                            session_id,
                            execution_id,
                            current_user_query=user_query,
                            event_callback=_emit_event,
                        )
                    )
                except Exception as exc:
                    result_holder[1] = exc
                finally:
                    event_queue.put({"type": "_done"})

            wf_thread = threading.Thread(
                target=_run_workflow, daemon=True,
                name=f"deploy-wf-{execution_id[:8]}"
            )
            wf_thread.start()

            # Consume intermediate events from queue and yield as SSE
            while True:
                try:
                    evt = event_queue.get(timeout=0.5)
                except queue_mod.Empty:
                    continue
                if evt["type"] == "_done":
                    break
                yield f"data: {json.dumps(evt)}\n\n"

            wf_thread.join(timeout=5)

            if result_holder[1] is not None:
                e = result_holder[1]
                logger.error(f"❌ DEPLOYMENT STREAM: Error executing workflow: {e}", exc_info=True)
                _exec_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                _fail_result = {'status': 'error', 'error': 'Workflow execution failed'}
                threading.Thread(
                    target=_save_deployment_data_async,
                    args=(
                        deployment_session,
                        conversation_history,
                        '',
                        execution_id,
                        None,
                        _fail_result,
                        _exec_time_ms,
                        None,
                        user_query
                    ),
                    daemon=True,
                    name=f"deploy-stream-save-fail-{execution_id[:8]}"
                ).start()
                yield f"data: {json.dumps({'type': 'error', 'error': 'Workflow execution failed', 'request_id': request_id})}\n\n"
                return

            execution_result = result_holder[0]
            execution_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            
            # Handle different execution results (persist session on each path so user message is not lost)
            if execution_result.get('status') == 'awaiting_human_input':
                threading.Thread(
                    target=_save_deployment_data_async,
                    args=(
                        deployment_session,
                        conversation_history,
                        '',
                        execution_id,
                        None,
                        execution_result,
                        execution_time_ms,
                        execution_result.get('execution_id'),
                        user_query
                    ),
                    daemon=True,
                    name=f"deploy-stream-save-await-{execution_id[:8]}"
                ).start()
                yield f"data: {json.dumps({'type': 'awaiting_human_input', 'title': execution_result.get('title', 'USER INPUT REQUIRED'), 'last_conversation_message': execution_result.get('last_conversation_message', ''), 'agent_name': execution_result.get('agent_name', ''), 'execution_id': execution_result.get('execution_id', ''), 'session_id': session_id, 'request_id': request_id})}\n\n"
                return
            
            if execution_result.get('status') != 'success':
                threading.Thread(
                    target=_save_deployment_data_async,
                    args=(
                        deployment_session,
                        conversation_history,
                        '',
                        execution_id,
                        None,
                        execution_result,
                        execution_time_ms,
                        execution_result.get('execution_id'),
                        user_query
                    ),
                    daemon=True,
                    name=f"deploy-stream-save-fail-{execution_id[:8]}"
                ).start()
                yield f"data: {json.dumps({'type': 'error', 'error': execution_result.get('error', 'Workflow execution failed'), 'request_id': request_id})}\n\n"
                return
            
            # Extract assistant response
            assistant_response = execution_result.get('response', '')
            
            if not assistant_response:
                _no_resp_result = {'status': 'error', 'error': 'No response generated'}
                threading.Thread(
                    target=_save_deployment_data_async,
                    args=(
                        deployment_session,
                        conversation_history,
                        '',
                        execution_id,
                        None,
                        _no_resp_result,
                        execution_time_ms,
                        execution_result.get('execution_id'),
                        user_query
                    ),
                    daemon=True,
                    name=f"deploy-stream-save-fail-{execution_id[:8]}"
                ).start()
                yield f"data: {json.dumps({'type': 'error', 'error': 'No response generated', 'request_id': request_id})}\n\n"
                return
            
            # Persist conversation (including full assistant response) BEFORE streaming
            # so the response survives even if the client disconnects mid-stream.
            stream_citations = execution_result.get('citations') or []
            assistant_history_entry = {
                'role': 'assistant',
                'content': assistant_response,
                'timestamp': timezone.now().isoformat(),
            }
            if stream_citations:
                assistant_history_entry['citations'] = stream_citations
            conversation_history.append(assistant_history_entry)
            _save_session_conversation_sync(deployment_session, conversation_history)

            # Strip ---CITATIONS--- block from the response before streaming.
            # Citations are sent as a separate SSE event after the content stream.
            import re as _re
            _citations_match = _re.search(
                r'---CITATIONS---\s*([\s\S]*?)\s*---END_?CITATIONS---',
                assistant_response,
            )
            parsed_citations_json = None
            if _citations_match:
                try:
                    parsed_citations_json = json.loads(_citations_match.group(1))
                except (json.JSONDecodeError, ValueError):
                    pass
                assistant_response = assistant_response[:_citations_match.start()].rstrip()
            # Strip trailing "CITATIONS" header some models leave
            assistant_response = _re.sub(r'\n*CITATIONS\s*$', '', assistant_response).rstrip()

            # Stream the cleaned response word by word for smooth appearance
            words = assistant_response.split(' ')
            accumulated = ""

            for i, word in enumerate(words):
                accumulated += word
                if i < len(words) - 1:
                    accumulated += " "

                # Send chunk
                yield f"data: {json.dumps({'type': 'content', 'content': word + (' ' if i < len(words) - 1 else ''), 'request_id': request_id})}\n\n"

                # Small delay for smooth streaming (optional)
                import time
                time.sleep(0.02)  # 20ms delay between words

            # Send parsed citations as a separate event after content stream
            if parsed_citations_json:
                yield f"data: {json.dumps({'type': 'citations', 'citations': parsed_citations_json, 'request_id': request_id})}\n\n"
            
            # Save execution metadata in background (conversation already persisted above)
            background_thread = threading.Thread(
                target=_save_deployment_data_async,
                args=(
                    deployment_session,
                    conversation_history,
                    assistant_response,
                    execution_id,
                    None,  # deployment_request (None for streaming)
                    execution_result,
                    execution_time_ms,
                    execution_result.get('execution_id'),
                    user_query
                ),
                daemon=True,
                name=f"deploy-stream-save-{execution_id[:8]}"
            )
            background_thread.start()
            
            # Send completion (stream_citations computed earlier, before streaming)
            yield f"data: {json.dumps({'type': 'done', 'request_id': request_id, 'execution_time_ms': execution_time_ms, 'citations': stream_citations})}\n\n"
            
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT STREAM: Error in stream generation: {e}", exc_info=True)
            # Persist user message if we already had a session (so it is not lost)
            if deployment_session is not None and conversation_history is not None:
                try:
                    _save_session_conversation_sync(deployment_session, conversation_history)
                    logger.info(f"💾 DEPLOYMENT STREAM: Saved session on outer exception so user message is not lost")
                except Exception as save_err:
                    logger.warning(f"⚠️ DEPLOYMENT STREAM: Failed to save session on outer exception: {save_err}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    response = StreamingHttpResponse(generate_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
    _add_cors_headers(response, request)
    return response


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@never_cache
def submit_deployment_human_input(request, project_id):
    """
    Submit human input for a paused deployment workflow execution.
    
    POST /api/workflow-deploy/{project_id}/submit-input/
    Body: { "session_id": "...", "user_input": "..." }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        return response
    
    origin = request.META.get('HTTP_ORIGIN', '')
    request_id = f"submit_input_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
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
        
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'error': 'Invalid JSON format',
                'request_id': request_id
            }, status=400)
        
        session_id = data.get('session_id', '').strip()
        user_input = data.get('user_input', '').strip()
        
        if not session_id:
            return JsonResponse({
                'status': 'error',
                'error': 'Session ID is required',
                'request_id': request_id
            }, status=400)
        
        if not user_input:
            return JsonResponse({
                'status': 'error',
                'error': 'User input is required',
                'request_id': request_id
            }, status=400)
        
        # Get deployment session
        try:
            deployment_session = DeploymentSession.objects.get(
                deployment=deployment,
                session_id=session_id
            )
        except DeploymentSession.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'error': 'Session not found',
                'request_id': request_id
            }, status=404)
        
        # Check if session is awaiting human input
        if not deployment_session.awaiting_human_input:
            return JsonResponse({
                'status': 'error',
                'error': 'Session is not awaiting human input',
                'request_id': request_id
            }, status=400)
        
        # Get the paused execution
        if not deployment_session.paused_execution_id:
            return JsonResponse({
                'status': 'error',
                'error': 'No paused execution found for this session',
                'request_id': request_id
            }, status=400)
        
        # Resume workflow execution asynchronously (non-blocking)
        import threading
        from .conversation_orchestrator import ConversationOrchestrator
        
        # Create a thread-safe result container (appended_input: True if thread already saved human message)
        result_container = {'result': None, 'error': None, 'completed': False, 'appended_input': False}
        
        def resume_workflow_async():
            """Resume workflow in background thread"""
            from django.db import close_old_connections
            close_old_connections()
            
            try:
                from users.models import WorkflowExecution
                # Get fresh session and execution records in the background thread
                session = DeploymentSession.objects.get(
                    deployment=deployment,
                    session_id=session_id
                )
                
                if not session.paused_execution_id:
                    raise ValueError(f"No paused execution ID found in session {session_id}")
                
                logger.info(f"🔍 DEPLOYMENT: Looking for execution_id: {session.paused_execution_id}")
                
                try:
                    execution_record = WorkflowExecution.objects.get(
                        execution_id=session.paused_execution_id
                    )
                    logger.info(f"✅ DEPLOYMENT: Found execution record {execution_record.execution_id[:8]}")
                    
                    # Verify execution is in a valid state for resuming
                    from users.models import WorkflowExecutionStatus
                    if execution_record.status not in [WorkflowExecutionStatus.RUNNING, WorkflowExecutionStatus.PENDING]:
                        logger.error(f"❌ DEPLOYMENT: Execution {execution_record.execution_id[:8]} is in {execution_record.status} state, cannot resume")
                        raise ValueError(f"Execution {execution_record.execution_id} is in {execution_record.status} state, cannot resume")
                    
                except WorkflowExecution.DoesNotExist:
                    logger.error(f"❌ DEPLOYMENT: WorkflowExecution {session.paused_execution_id} not found")
                    logger.error(f"❌ DEPLOYMENT: Session paused_execution_id: {session.paused_execution_id}")
                    logger.error(f"❌ DEPLOYMENT: Session awaiting_human_input: {session.awaiting_human_input}")
                    
                    # Try to find the execution by checking recent executions for this workflow
                    workflow = deployment.workflow
                    if workflow:
                        recent_execution = WorkflowExecution.objects.filter(
                            workflow=workflow
                        ).order_by('-start_time').first()
                        
                        if recent_execution:
                            # Verify execution is in a valid state for resuming
                            from users.models import WorkflowExecutionStatus
                            if recent_execution.status not in [WorkflowExecutionStatus.RUNNING, WorkflowExecutionStatus.PENDING]:
                                logger.error(f"❌ DEPLOYMENT: Recent execution {recent_execution.execution_id[:8]} is in {recent_execution.status} state, cannot resume")
                                raise ValueError(f"Execution {recent_execution.execution_id} is in {recent_execution.status} state, cannot resume")
                            
                            logger.warning(f"⚠️ DEPLOYMENT: Using recent execution {recent_execution.execution_id[:8]} instead")
                            execution_record = recent_execution
                            # Update session with correct execution_id
                            session.paused_execution_id = execution_record.execution_id
                            session.save()
                        else:
                            raise ValueError(f"WorkflowExecution {session.paused_execution_id} not found and no recent executions available")
                    else:
                        raise ValueError(f"WorkflowExecution {session.paused_execution_id} not found and no workflow available")
                
                # Add user input to conversation history immediately (before resuming workflow)
                # This ensures it appears in the chat UI right away
                session.conversation_history.append({
                    'role': 'user',
                    'content': user_input,
                    'timestamp': timezone.now().isoformat()
                })
                session.message_count = len(session.conversation_history)
                session.last_activity = timezone.now()
                session.save()
                result_container['appended_input'] = True
                logger.info(f"📝 DEPLOYMENT: Added user input to session conversation history: {user_input[:100]}...")
                
                # Resume workflow with user input
                orchestrator = ConversationOrchestrator()
                result = asyncio.run(
                    orchestrator.resume_workflow_with_human_input(
                        execution_record.execution_id,
                        user_input,
                        deployment.created_by
                    )
                )
                
                result_container['result'] = result
                result_container['completed'] = True
                
                # Clear pause state from session
                session.awaiting_human_input = False
                session.paused_execution_id = None
                session.human_input_prompt = ''
                session.human_input_agent_name = ''
                session.human_input_agent_id = ''
                session.save()
                
                logger.info(f"✅ DEPLOYMENT: Resumed workflow execution {execution_record.execution_id[:8]} with user input")
                
            except Exception as e:
                logger.error(f"❌ DEPLOYMENT: Failed to resume workflow: {e}", exc_info=True)
                result_container['error'] = str(e)
                result_container['completed'] = True
        
        # Start background thread
        resume_thread = threading.Thread(
            target=resume_workflow_async,
            daemon=True,
            name=f"deploy-resume-{deployment_session.paused_execution_id[:8]}"
        )
        resume_thread.start()
        
        # Wait for completion (with timeout)
        import time
        timeout = 60  # 60 seconds timeout
        elapsed = 0
        while not result_container['completed'] and elapsed < timeout:
            time.sleep(0.1)
            elapsed += 0.1
        
        if not result_container['completed']:
            # Timeout - return response indicating processing is ongoing
            return JsonResponse({
                'status': 'processing',
                'message': 'Workflow is being processed. Please check back shortly.',
                'session_id': session_id,
                'request_id': request_id
            })
        
        if result_container['error']:
            # Persist human input to session when resume failed and thread did not append it
            if not result_container.get('appended_input'):
                try:
                    deployment_session.conversation_history = deployment_session.conversation_history or []
                    deployment_session.conversation_history.append({
                        'role': 'user',
                        'content': user_input,
                        'timestamp': timezone.now().isoformat()
                    })
                    deployment_session.message_count = len(deployment_session.conversation_history)
                    deployment_session.last_activity = timezone.now()
                    deployment_session.save()
                    logger.info(f"📝 DEPLOYMENT: Persisted human input to session after resume failure: {user_input[:100]}...")
                except Exception as save_err:
                    logger.warning(f"⚠️ DEPLOYMENT: Failed to persist human input on resume failure: {save_err}")
            return JsonResponse({
                'status': 'error',
                'error': result_container['error'],
                'request_id': request_id
            }, status=500)
        
        # Extract response from result
        result = result_container['result']
        
        # Check if workflow is still awaiting human input (another UserProxyAgent)
        if result.get('status') == 'awaiting_human_input':
            # Another UserProxyAgent requires input - return the same format
            return JsonResponse({
                'status': 'awaiting_human_input',
                'human_input_required': True,
                'title': result.get('title', 'USER INPUT REQUIRED'),
                'last_conversation_message': result.get('last_conversation_message', ''),
                'agent_name': result.get('agent_name', ''),
                'execution_id': result.get('execution_id', ''),
                'session_id': session_id,
                'metadata': {
                    'request_id': request_id
                }
            })
        elif result.get('status') == 'success':
            # Extract response from execution result
            from .deployment_executor import WorkflowDeploymentExecutor
            executor = WorkflowDeploymentExecutor()
            
            # Get workflow graph for response extraction
            workflow = deployment.workflow
            if workflow:
                graph_json = workflow.graph_json
                assistant_response, response_citations = executor._extract_end_node_output(result, graph_json)
            else:
                # Fallback: try to get from result directly
                assistant_response = result.get('response', '') or result.get('conversation_history', '')
                response_citations = result.get('citations') or []
            
            # User input was already added to conversation history when submitted
            # Just add the assistant response now
            if assistant_response:
                deployment_session.conversation_history.append({
                    'role': 'assistant',
                    'content': assistant_response,
                    'timestamp': timezone.now().isoformat()
                })
            deployment_session.message_count = len(deployment_session.conversation_history)
            deployment_session.last_activity = timezone.now()
            deployment_session.save()
            
            execution_time_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            
            return JsonResponse({
                'status': 'success',
                'response': assistant_response,
                'citations': response_citations or [],
                'metadata': {
                    'request_id': request_id,
                    'execution_time_ms': execution_time_ms,
                    'session_id': session_id
                }
            })
        else:
            return JsonResponse({
                'status': 'error',
                'error': result.get('error', 'Workflow execution failed'),
                'request_id': request_id
            }, status=500)
        
    except Exception as e:
        logger.error(f"❌ DEPLOYMENT: Error in submit-input endpoint: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': 'An error occurred while processing your input',
            'request_id': request_id
        }, status=500)


@csrf_exempt
@xframe_options_exempt
def embed_chatbot_html(request, project_id):
    """
    Serve the chatbot HTML for iframe embedding.
    This endpoint returns a complete HTML page with the chatbot interface.
    Features a modern glassmorphism design with customizable branding.
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
                '<html><body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f7;"><p style="color:#6b7280;">Chatbot not available. Please ensure deployment is active and a workflow is configured.</p></body></html>',
                status=404,
                content_type='text/html'
            )
        
        # Absolute URL fallback (e.g. external embeds). In-app iframe must use the browser's
        # origin — build_absolute_uri often yields 127.0.0.1:8000 or internal Docker host behind
        # Vite/nginx proxy, which the user's browser cannot reach → fetch fails ("connection problem").
        # Use X-Forwarded-Proto to determine the scheme when behind a reverse proxy.
        base_url = request.build_absolute_uri('/').rstrip('/')
        if request.META.get('HTTP_X_FORWARDED_PROTO') == 'https' and base_url.startswith('http://'):
            base_url = 'https://' + base_url[len('http://'):]
        endpoint_url = f"{base_url}{deployment.endpoint_path}"
        initial_greeting = getattr(deployment, 'initial_greeting', 'Hi! I am your AI assistant.')
        
        # Get branding customization with defaults
        chatbot_title = getattr(deployment, 'chatbot_title', 'AI Assistant')
        chatbot_subtitle = getattr(deployment, 'chatbot_subtitle', 'Powered by AICC IntelliDoc')
        primary_color = getattr(deployment, 'primary_color', '#78b2e8')
        secondary_color = getattr(deployment, 'secondary_color', '#3a6d98')
        logo_url = getattr(deployment, 'logo_url', None) or ''
        
        # Generate the modern HTML with glassmorphism design
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{chatbot_title}</title>
  <style>
    :root {{
      --primary-color: {primary_color};
      --secondary-color: {secondary_color};
      --primary-rgb: {_embed_hex_to_rgb_csv(primary_color, '120, 178, 232')};
      --secondary-rgb: {_embed_hex_to_rgb_csv(secondary_color, '58, 109, 152')};
    }}
    
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    html, body {{
      font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: transparent;
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}
    
    .chat-container {{
      width: 100%;
      height: 100%;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-radius: 0;
      box-shadow: 
        0 25px 50px -12px rgba(0, 0, 0, 0.25),
        0 0 0 1px rgba(255, 255, 255, 0.1);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}
    
    .chat-container:hover {{
      transform: translateY(-2px);
      box-shadow: 
        0 30px 60px -12px rgba(0, 0, 0, 0.3),
        0 0 0 1px rgba(255, 255, 255, 0.15);
    }}
    
    .chat-header {{
      padding: 20px 24px;
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
      color: #fff;
      display: flex;
      align-items: center;
      gap: 14px;
      position: relative;
      overflow: hidden;
    }}
    
    .chat-header::before {{
      content: '';
      position: absolute;
      top: -50%;
      right: -50%;
      width: 100%;
      height: 200%;
      background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
      pointer-events: none;
    }}
    
    .header-logo {{
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      backdrop-filter: blur(10px);
      overflow: hidden;
    }}
    
    .header-logo img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 12px;
    }}
    
    .header-logo-placeholder {{
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      text-transform: uppercase;
    }}
    
    .header-text {{
      flex: 1;
      min-width: 0;
    }}
    
    .chat-header-title {{
      font-weight: 700;
      font-size: 17px;
      letter-spacing: -0.3px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    
    .chat-header-sub {{
      font-size: 12px;
      opacity: 0.85;
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    
    .online-indicator {{
      width: 10px;
      height: 10px;
      background: #22c55e;
      border-radius: 50%;
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.3);
      animation: pulse 2s infinite;
    }}
    
    @keyframes pulse {{
      0%, 100% {{ box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.3); }}
      50% {{ box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.1); }}
    }}
    
    .chat-messages {{
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      scrollbar-gutter: stable;
      background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
      font-size: 14px;
      scroll-behavior: smooth;
    }}
    
    .chat-messages::-webkit-scrollbar {{
      width: 7px;
    }}
    
    .chat-messages::-webkit-scrollbar-track {{
      background: rgba(0, 0, 0, 0.03);
    }}
    
    .chat-messages::-webkit-scrollbar-thumb {{
      background: rgba(0, 0, 0, 0.15);
      border-radius: 4px;
    }}
    
    .chat-messages::-webkit-scrollbar-thumb:hover {{
      background: rgba(0, 0, 0, 0.25);
    }}
    
    .msg {{
      margin-bottom: 16px;
      display: flex;
      animation: slideIn 0.3s ease-out;
    }}
    
    @keyframes slideIn {{
      from {{
        opacity: 0;
        transform: translateY(10px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}
    
    .msg.user {{
      justify-content: flex-end;
    }}
    
    .msg.assistant {{
      justify-content: flex-start;
    }}
    
    .bubble {{
      max-width: 85%;
      padding: 12px 16px;
      border-radius: 18px;
      line-height: 1.5;
      position: relative;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }}
    
    .msg.user .bubble {{
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
      color: #fff;
      border-bottom-right-radius: 6px;
    }}
    
    .msg.assistant .bubble {{
      background: #ffffff;
      color: #1e293b;
      border: 1px solid rgba(0, 0, 0, 0.06);
      border-bottom-left-radius: 6px;
    }}
    
    .chat-input-container {{
      padding: 16px 20px 20px;
      background: #ffffff;
      border-top: 1px solid rgba(0, 0, 0, 0.06);
    }}
    
    .chat-input {{
      display: flex;
      align-items: flex-end;
      gap: 12px;
      background: #f1f5f9;
      border-radius: 16px;
      padding: 8px 8px 8px 16px;
      transition: box-shadow 0.2s ease, background 0.2s ease;
    }}
    
    .chat-input:focus-within {{
      background: #fff;
      box-shadow: 0 0 0 2px var(--primary-color), 0 4px 12px rgba(var(--primary-rgb), 0.15);
    }}
    
    .chat-input textarea {{
      flex: 1;
      resize: none;
      border: none;
      background: transparent;
      padding: 8px 0;
      font-size: 14px;
      line-height: 1.5;
      color: #1e293b;
      font-family: inherit;
      min-height: 24px;
      max-height: 120px;
      overflow-y: auto;
    }}
    
    .chat-input textarea::placeholder {{
      color: #94a3b8;
    }}
    
    .chat-input textarea:focus {{
      outline: none;
    }}
    
    .chat-input button {{
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
      color: #fff;
      border: none;
      border-radius: 12px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      flex-shrink: 0;
    }}
    
    .chat-input button:hover:not(:disabled) {{
      transform: scale(1.05);
      box-shadow: 0 4px 12px rgba(var(--primary-rgb), 0.4);
    }}
    
    .chat-input button:active:not(:disabled) {{
      transform: scale(0.95);
    }}
    
    .chat-input button:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
    }}
    
    .chat-input button:focus-visible {{
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }}
    
    .chat-input button svg {{
      width: 20px;
      height: 20px;
      transition: transform 0.2s ease;
    }}
    
    .chat-input button:hover:not(:disabled) svg {{
      transform: translateX(2px);
    }}
    
    .status {{
      font-size: 11px;
      color: #64748b;
      padding: 8px 20px 0;
      text-align: center;
    }}
    
    .human-input-modal {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
      z-index: 1000;
      justify-content: center;
      align-items: center;
      padding: 16px;
    }}
    
    .human-input-modal.active {{
      display: flex;
    }}
    
    .human-input-box {{
      background: #fff;
      border-radius: 20px;
      padding: 28px;
      max-width: 480px;
      width: 100%;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
      animation: modalSlideIn 0.3s ease-out;
    }}
    
    @keyframes modalSlideIn {{
      from {{
        opacity: 0;
        transform: scale(0.95) translateY(10px);
      }}
      to {{
        opacity: 1;
        transform: scale(1) translateY(0);
      }}
    }}
    
    .human-input-title {{
      font-size: 18px;
      font-weight: 700;
      color: var(--primary-color);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    
    .human-input-title::before {{
      content: '';
      width: 4px;
      height: 20px;
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
      border-radius: 2px;
    }}
    
    .human-input-message {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 20px;
      font-size: 14px;
      color: #475569;
      line-height: 1.6;
    }}
    
    .human-input-textarea {{
      width: 100%;
      min-height: 100px;
      border: 2px solid #e2e8f0;
      border-radius: 12px;
      padding: 14px;
      font-size: 14px;
      resize: vertical;
      font-family: inherit;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .human-input-textarea:focus {{
      outline: none;
      border-color: var(--primary-color);
      box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.1);
    }}
    
    .human-input-buttons {{
      display: flex;
      gap: 12px;
      justify-content: flex-end;
      margin-top: 20px;
    }}
    
    .human-input-buttons button {{
      padding: 12px 24px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s ease;
    }}
    
    .human-input-buttons .submit-btn {{
      background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
      color: #fff;
    }}
    
    .human-input-buttons .submit-btn:hover:not(:disabled) {{
      box-shadow: 0 4px 12px rgba(var(--primary-rgb), 0.4);
      transform: translateY(-1px);
    }}
    
    .human-input-buttons .submit-btn:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
    }}
    
    .human-input-buttons .cancel-btn {{
      background: #f1f5f9;
      color: #475569;
    }}
    
    .human-input-buttons .cancel-btn:hover {{
      background: #e2e8f0;
    }}
    
    .thinking-indicator {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
    }}
    
    .thinking-dots {{
      display: flex;
      gap: 5px;
    }}
    
    .thinking-dot {{
      width: 8px;
      height: 8px;
      background: var(--primary-color);
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out both;
    }}
    
    .thinking-dot:nth-child(1) {{ animation-delay: -0.32s; }}
    .thinking-dot:nth-child(2) {{ animation-delay: -0.16s; }}
    .thinking-dot:nth-child(3) {{ animation-delay: 0s; }}
    
    @keyframes bounce {{
      0%, 80%, 100% {{
        transform: scale(0.6);
        opacity: 0.4;
      }}
      40% {{
        transform: scale(1);
        opacity: 1;
      }}
    }}
    
    /* Markdown Styles */
    .bubble markdown {{
      display: block;
    }}
    
    .bubble markdown p {{
      margin: 8px 0;
    }}
    
    .bubble markdown p:first-child {{
      margin-top: 0;
    }}
    
    .bubble markdown p:last-child {{
      margin-bottom: 0;
    }}
    
    .bubble markdown strong {{
      font-weight: 600;
    }}
    
    .bubble markdown em {{
      font-style: italic;
    }}
    
    .bubble markdown code {{
      background: rgba(0, 0, 0, 0.06);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'SF Mono', 'Consolas', monospace;
      font-size: 0.875em;
    }}
    
    .msg.user .bubble markdown code {{
      background: rgba(255, 255, 255, 0.2);
    }}
    
    .bubble markdown pre {{
      background: #1e293b;
      color: #e2e8f0;
      padding: 14px;
      border-radius: 10px;
      overflow-x: auto;
      margin: 10px 0;
    }}
    
    .bubble markdown pre code {{
      background: none;
      padding: 0;
      color: inherit;
    }}
    
    .bubble markdown ul, .bubble markdown ol {{
      margin: 8px 0;
      padding-left: 24px;
    }}
    
    .bubble markdown li {{
      margin: 4px 0;
    }}
    
    .bubble markdown blockquote {{
      border-left: 3px solid var(--primary-color);
      padding-left: 12px;
      margin: 10px 0;
      color: #64748b;
      font-style: italic;
    }}
    
    .bubble markdown a {{
      color: var(--primary-color);
      text-decoration: underline;
    }}
    
    .msg.user .bubble markdown a {{
      color: #fff;
    }}
    
    .bubble markdown h1 {{ font-size: 1.4em; font-weight: 700; margin: 14px 0 8px; }}
    .bubble markdown h2 {{ font-size: 1.25em; font-weight: 700; margin: 12px 0 6px; }}
    .bubble markdown h3 {{ font-size: 1.1em; font-weight: 600; margin: 10px 0 4px; }}
    .bubble markdown hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }}

    .cite-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 18px;
      height: 18px;
      padding: 0 4px;
      border-radius: 4px;
      background: var(--primary-color, #0ea5e9);
      color: white;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      vertical-align: super;
      margin: 0 1px;
      line-height: 1;
      transition: background 0.15s;
    }}
    .cite-chip:hover {{
      filter: brightness(0.85);
    }}
    .cite-tooltip {{
      position: fixed;
      max-width: 340px;
      background: #1e293b;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 13px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.3);
      z-index: 9999;
      animation: citeIn 0.15s ease-out;
    }}
    .cite-tooltip-title {{
      font-weight: 600;
      color: #38bdf8;
      margin-bottom: 6px;
      font-size: 12px;
    }}
    .cite-tooltip-link {{
      color: #38bdf8;
      text-decoration: underline;
      text-underline-offset: 2px;
      cursor: pointer;
      transition: color 0.15s;
    }}
    .cite-tooltip-link:hover {{
      color: #7dd3fc;
    }}
    .cite-tooltip-source {{
      font-size: 11px;
      color: #94a3b8;
      margin-bottom: 4px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .cite-tooltip-quote {{
      font-style: italic;
      color: #cbd5e1;
      font-size: 12px;
      line-height: 1.5;
    }}
    @keyframes citeIn {{
      from {{ opacity: 0; transform: translateY(-4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── Activity / Planning panel ────────────────────────────── */
    .activity-panel {{
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      margin: 0 16px 6px 56px;
      overflow: hidden;
      transition: max-height 0.35s ease, opacity 0.25s ease;
      max-height: 320px;
      opacity: 1;
    }}
    .activity-panel.collapsed {{
      max-height: 32px;
      cursor: pointer;
    }}
    .activity-header {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      color: #64748b;
      user-select: none;
      cursor: pointer;
    }}
    .activity-header svg {{
      width: 14px; height: 14px; flex-shrink: 0;
      transition: transform 0.25s;
    }}
    .activity-panel.collapsed .activity-header svg {{
      transform: rotate(-90deg);
    }}
    .activity-items {{
      max-height: 260px;
      overflow-y: auto;
      padding: 0 12px 8px;
    }}
    .activity-panel.collapsed .activity-items {{
      display: none;
    }}
    .activity-item {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 5px 0;
      font-size: 12px;
      color: #475569;
      line-height: 1.45;
      border-bottom: 1px solid #e2e8f0;
      animation: actItemIn 0.2s ease-out;
    }}
    .activity-item:last-child {{ border-bottom: none; }}
    .activity-item-icon {{
      flex-shrink: 0;
      width: 18px; height: 18px;
      display: flex; align-items: center; justify-content: center;
      border-radius: 4px;
      font-size: 11px;
    }}
    .activity-item-body b {{ color: #334155; }}

    .activity-item.expandable {{
      cursor: pointer;
      flex-wrap: wrap;
    }}
    .activity-item.expandable:hover {{
      background: #e2e8f0;
      border-radius: 6px;
    }}
    .activity-item.expandable .activity-item-body::after {{
      content: ' ▸';
      font-size: 10px;
      color: #94a3b8;
      transition: transform 0.2s;
    }}
    .activity-item.expanded .activity-item-body::after {{
      content: ' ▾';
    }}
    .activity-detail {{
      display: none;
      width: 100%;
      margin-top: 4px;
      padding: 8px 10px;
      background: #e8ecf1;
      border-radius: 6px;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 11px;
      line-height: 1.55;
      color: #334155;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 180px;
      overflow-y: auto;
      animation: detailSlide 0.2s ease-out;
    }}
    .activity-item.expanded .activity-detail {{
      display: block;
    }}
    @keyframes detailSlide {{
      from {{ opacity: 0; max-height: 0; }}
      to {{ opacity: 1; max-height: 180px; }}
    }}

    @keyframes actItemIn {{
      from {{ opacity: 0; transform: translateX(-6px); }}
      to {{ opacity: 1; transform: translateX(0); }}
    }}
  </style>
</head>
<body>
<div class="chat-container">
  <div class="chat-header">
    <div class="header-logo">
      {f'<img src="{logo_url}" alt="Logo" />' if logo_url else f'<span class="header-logo-placeholder">{chatbot_title[0] if chatbot_title else "A"}</span>'}
    </div>
    <div class="header-text">
      <div class="chat-header-title">{chatbot_title}</div>
      <div class="chat-header-sub">{chatbot_subtitle}</div>
    </div>
    <div class="online-indicator" role="status" aria-label="Assistant online" title="Online"></div>
  </div>
  <div id="messages" class="chat-messages"></div>
  <div id="status" class="status"></div>
  <div class="chat-input-container">
    <div class="chat-input">
      <textarea id="input" rows="1" placeholder="Type your message..."></textarea>
      <button id="sendBtn" title="Send message">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </div>
  </div>
</div>

<!-- Human Input Modal -->
<div id="humanInputModal" class="human-input-modal">
  <div class="human-input-box">
    <div class="human-input-title" id="humanInputTitle">Input Required</div>
    <div class="human-input-message" id="humanInputMessage"></div>
    <textarea id="humanInputTextarea" class="human-input-textarea" placeholder="Enter your response..."></textarea>
    <div class="human-input-buttons">
      <button class="cancel-btn" id="humanInputCancel">Cancel</button>
      <button class="submit-btn" id="humanInputSubmit">Submit</button>
    </div>
  </div>
</div>

<script>
  // Resolve chat API from the page URL so POST /stream/ stays same-origin (proxied /api on :5173).
  const _pathPartsForEndpoint = window.location.pathname.split('/').filter(Boolean);
  const _wdIdx = _pathPartsForEndpoint.indexOf('workflow-deploy');
  const _embedProjectId = (_wdIdx >= 0 && _wdIdx + 1 < _pathPartsForEndpoint.length)
    ? _pathPartsForEndpoint[_wdIdx + 1]
    : '';
  const ENDPOINT_URL = _embedProjectId
    ? (window.location.origin + '/api/workflow-deploy/' + _embedProjectId + '/')
    : {json.dumps(endpoint_url)};
  const STREAM_URL = ENDPOINT_URL.replace(/\\/$/, '') + '/stream/';
  const SUBMIT_INPUT_URL = ENDPOINT_URL.replace(/\\/$/, '') + '/submit-input/';
  const INITIAL_GREETING = {json.dumps(initial_greeting)};
  
  // Enhanced markdown renderer
  function renderMarkdown(text) {{
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    
    // Headers
    html = html.replace(/^######\\s+(.+)$/gm, '<h6>$1</h6>');
    html = html.replace(/^#####\\s+(.+)$/gm, '<h5>$1</h5>');
    html = html.replace(/^####\\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^###\\s+(.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^##\\s+(.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^#\\s+(.+)$/gm, '<h1>$1</h1>');
    
    // Horizontal rules
    html = html.replace(/^\\s*[-*]{{3,}}\\s*$/gm, '<hr>');
    
    // Code blocks
    html = html.replace(/```(\\w+)?[\\n\\r]+([\\s\\S]*?)```/g, function(match, lang, code) {{
      return '<pre><code>' + code.trim() + '</code></pre>';
    }});
    
    // Blockquotes
    html = html.replace(/^>\\s+(.+)$/gm, '<blockquote>$1</blockquote>');
    
    // Process lists
    const lines = html.split('\\n');
    const processedLines = [];
    let inOrderedList = false;
    let inUnorderedList = false;
    
    for (let i = 0; i < lines.length; i++) {{
      const line = lines[i];
      const orderedMatch = line.match(/^(\\d+)\\.\\s+(.+)$/);
      const unorderedMatch = line.match(/^[-*]\\s+(.+)$/);
      
      if (orderedMatch) {{
        if (!inOrderedList) {{
          if (inUnorderedList) {{ processedLines.push('</ul>'); inUnorderedList = false; }}
          processedLines.push('<ol>');
          inOrderedList = true;
        }}
        processedLines.push('<li>' + orderedMatch[2] + '</li>');
      }} else if (unorderedMatch) {{
        if (!inUnorderedList) {{
          if (inOrderedList) {{ processedLines.push('</ol>'); inOrderedList = false; }}
          processedLines.push('<ul>');
          inUnorderedList = true;
        }}
        processedLines.push('<li>' + unorderedMatch[1] + '</li>');
      }} else {{
        if (inOrderedList) {{ processedLines.push('</ol>'); inOrderedList = false; }}
        if (inUnorderedList) {{ processedLines.push('</ul>'); inUnorderedList = false; }}
        processedLines.push(line);
      }}
    }}
    if (inOrderedList) processedLines.push('</ol>');
    if (inUnorderedList) processedLines.push('</ul>');
    html = processedLines.join('\\n');
    
    // Links
    html = html.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    
    // Bold
    html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    html = html.replace(/__(?!_)([^_]+)__/g, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\\*(?!\\*)([^*]+)\\*(?!\\*)/g, '<em>$1</em>');
    html = html.replace(/_(?!_)([^_]+)_(?!_)/g, '<em>$1</em>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Paragraphs
    const paragraphs = html.split(/\\n\\n+/);
    html = paragraphs.map(function(p) {{
      p = p.trim();
      if (!p) return '';
      if (/^<(pre|blockquote|ul|ol|hr|h[1-6])/i.test(p)) return p;
      p = p.replace(/\\n/g, '<br>');
      return '<p>' + p + '</p>';
    }}).filter(function(p) {{ return p; }}).join('');
    
    return html;
  }}

  let _chatCitations = [];
  let _activeCiteTooltip = null;

  function parseCitations(text) {{
    const pattern = /---CITATIONS---\\s*([\\s\\S]*?)\\s*---END_CITATIONS---/;
    const m = text.match(pattern);
    if (!m) return {{ cleanText: text, citations: [] }};
    var cleanText = text.slice(0, m.index).trim();
    // Strip trailing "CITATIONS" headings the LLM sometimes emits before the block
    cleanText = cleanText.replace(/[\\n\\r]+(?:#{1,6}\\s*)?(?:\\*{{1,2}})?CITATIONS(?:\\*{{1,2}})?\\s*$/i, '').trim();
    let citations = [];
    try {{
      citations = JSON.parse(m[1].trim());
      if (!Array.isArray(citations)) citations = [];
      else citations = citations.filter(function(c) {{
        if (!c || typeof c !== 'object') return false;
        var r = parseInt(c.ref, 10);
        if (isNaN(r)) return false;
        c.ref = r;
        return true;
      }});
    }} catch(e) {{ citations = []; }}
    return {{ cleanText, citations }};
  }}

  function renderCitationChips(html, citations) {{
    if (!citations || citations.length === 0) return html;
    return html.replace(/\\[(\\d+)\\]/g, function(match, num) {{
      const ref = parseInt(num, 10);
      const cit = citations.find(function(c) {{ return Number(c.ref) === ref; }});
      if (!cit) return match;
      return '<span class="cite-chip" data-ref="' + ref + '">' + ref + '</span>';
    }});
  }}

  function _getCiteAuthHeaders() {{
    try {{
      var raw = localStorage.getItem('auth');
      if (raw) {{
        var parsed = JSON.parse(raw);
        if (parsed && parsed.token) return {{ 'Authorization': 'Bearer ' + parsed.token }};
      }}
    }} catch(_e) {{}}
    return {{}};
  }}

  function openCitationDocument(documentId) {{
    if (!projectId || !documentId) return;
    var url = '/api/projects/' + projectId + '/documents/' + documentId + '/download/';
    fetch(url, {{ headers: _getCiteAuthHeaders() }})
      .then(function(resp) {{
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return resp.blob();
      }})
      .then(function(blob) {{
        var blobUrl = URL.createObjectURL(blob);
        window.open(blobUrl, '_blank');
        setTimeout(function() {{ URL.revokeObjectURL(blobUrl); }}, 60000);
      }})
      .catch(function(err) {{
        console.error('Citation document open failed:', err);
      }});
  }}

  function showCiteTooltip(chipEl, ref) {{
    if (_activeCiteTooltip) {{ _activeCiteTooltip.remove(); _activeCiteTooltip = null; }}
    const cit = _chatCitations.find(function(c) {{ return Number(c.ref) === ref; }});
    if (!cit) return;
    const tip = document.createElement('div');
    tip.className = 'cite-tooltip';
    var isWeb = cit.url || cit.source === 'web';
    var titleHtml;
    if (cit.document_id) {{
      var loc = '';
      if (cit.page) loc += 'p.' + cit.page;
      if (cit.section) loc += (loc ? ', ' : '') + cit.section;
      var titleText = (cit.document_title || 'Document') + (loc ? ' &mdash; ' + loc : '');
      titleHtml = '<a class="cite-tooltip-link" href="#" data-docid="' + cit.document_id + '">' + titleText + '</a>';
    }} else if (isWeb && cit.url) {{
      var safeUrl = cit.url.replace(/"/g, '&quot;').replace(/</g, '&lt;');
      titleHtml = '<a class="cite-tooltip-link" href="' + safeUrl + '" target="_blank" rel="noopener">' + (cit.document_title || cit.url).replace(/</g, '&lt;') + '</a>';
    }} else {{
      titleHtml = (cit.document_title || 'Source').replace(/</g, '&lt;');
    }}
    var sourceHtml = '';
    if (isWeb && cit.url) {{
      try {{
        var domain = new URL(cit.url).hostname.replace(/^www\\./, '');
        sourceHtml = '<div class="cite-tooltip-source">&#127760; ' + domain.replace(/</g, '&lt;') + '</div>';
      }} catch(_e) {{
        sourceHtml = '<div class="cite-tooltip-source">&#127760; Web</div>';
      }}
    }}
    tip.innerHTML = '<div class="cite-tooltip-title">' + titleHtml + '</div>' +
      sourceHtml +
      '<div class="cite-tooltip-quote">&ldquo;' +
      ((cit.quoted_text || '').slice(0, 300).replace(/</g,'&lt;')) +
      '&rdquo;</div>';
    const rect = chipEl.getBoundingClientRect();
    tip.style.left = rect.left + 'px';
    tip.style.top = (rect.bottom + 6) + 'px';
    document.body.appendChild(tip);
    _activeCiteTooltip = tip;
  }}

  document.addEventListener('click', function(e) {{
    var link = e.target.closest && e.target.closest('.cite-tooltip-link');
    if (link) {{
      if (link.dataset.docid) {{
        e.preventDefault();
        e.stopPropagation();
        openCitationDocument(link.dataset.docid);
        return;
      }}
      if (link.href && link.target === '_blank') {{
        return;
      }}
    }}
    const chip = e.target.closest && e.target.closest('.cite-chip');
    if (chip) {{
      const ref = parseInt(chip.dataset.ref, 10);
      if (_activeCiteTooltip && _activeCiteTooltip._ref === ref) {{
        _activeCiteTooltip.remove(); _activeCiteTooltip = null;
      }} else {{
        showCiteTooltip(chip, ref);
        if (_activeCiteTooltip) _activeCiteTooltip._ref = ref;
      }}
    }} else if (_activeCiteTooltip) {{
      _activeCiteTooltip.remove(); _activeCiteTooltip = null;
    }}
  }});

  const messages = [];
  // Allow explicit session_id via URL for in-app chatbot, fallback to random for external embeds
  const urlParams = new URLSearchParams(window.location.search || '');
  const urlSessionId = (urlParams.get('session_id') || '').trim();
  const sessionId = urlSessionId || ('sess_' + Math.random().toString(36).slice(2));
  let currentExecutionId = null;
  let awaitingHumanInput = false;

  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('sendBtn');
  const statusEl = document.getElementById('status');
  const humanInputModal = document.getElementById('humanInputModal');
  const humanInputTitle = document.getElementById('humanInputTitle');
  const humanInputMessage = document.getElementById('humanInputMessage');
  const humanInputTextarea = document.getElementById('humanInputTextarea');
  const humanInputSubmit = document.getElementById('humanInputSubmit');
  const humanInputCancel = document.getElementById('humanInputCancel');
  
  // Forward Escape key to the parent window so fullscreen can be exited
  // even when the iframe has keyboard focus.
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
      try {{ parent.postMessage({{ type: 'chatbot_escape' }}, '*'); }} catch(_) {{}}
    }}
  }});

  // Extract projectId from URL path: /api/workflow-deploy/<project_id>/embed/
  const _pathParts = window.location.pathname.split('/').filter(Boolean);
  const _pidIdx = _pathParts.indexOf('workflow-deploy') + 1;
  const projectId = _pidIdx > 0 && _pidIdx < _pathParts.length ? _pathParts[_pidIdx] : null;

  // Preload existing conversation history for this session (if any)
  const preloadPromise = (async function preloadConversation() {{
    try {{
      if (!projectId || !sessionId) {{
        return;
      }}

      const activityUrl = `/api/agent-orchestration/projects/${{projectId}}/deployment/activity/?session_id=${{encodeURIComponent(sessionId)}}&limit=1`;
      // SPA uses JWT in localStorage; REST_FRAMEWORK is JWT-only (no session auth for this API)
      let _preloadHeaders = {{}};
      try {{
        const _rawAuth = localStorage.getItem('auth');
        if (_rawAuth) {{
          const _authParsed = JSON.parse(_rawAuth);
          if (_authParsed && _authParsed.token) {{
            _preloadHeaders = {{ 'Authorization': 'Bearer ' + _authParsed.token }};
          }}
        }}
      }} catch (_e) {{}}
      const resp = await fetch(activityUrl, {{
        credentials: 'include',
        headers: _preloadHeaders
      }});
      if (!resp.ok) {{
        console.warn('Chatbot preload: activity request failed', resp.status);
        return;
      }}

      const data = await resp.json().catch(() => null);
      if (!data || !Array.isArray(data.sessions) || data.sessions.length === 0) {{
        return;
      }}

      const session = data.sessions[0];
      const history = Array.isArray(session.conversation_history) ? session.conversation_history : [];

      // Optionally cap to last 100 messages
      const recentHistory = history.slice(-100);
      for (const msg of recentHistory) {{
        if (!msg || !msg.role || typeof msg.content !== 'string') continue;
        const msgCitations = Array.isArray(msg.citations) ? msg.citations : undefined;
        appendMessage(msg.role === 'user' ? 'user' : 'assistant', msg.content, false, msgCitations);
        messages.push({{ role: msg.role, content: msg.content }});
      }}
    }} catch (e) {{
      console.warn('Chatbot preload failed:', e);
    }}
  }})();
  
  // Auto-resize textarea
  function autoResize() {{
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  }}
  inputEl.addEventListener('input', autoResize);

  function appendMessage(role, text, isStreaming = false, apiCitations = undefined) {{
    const msg = document.createElement('div');
    msg.className = 'msg ' + (role === 'user' ? 'user' : 'assistant');
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    
    if (role === 'assistant' && !isStreaming) {{
      let cleanText = text;
      let citations = [];
      if (Array.isArray(apiCitations) && apiCitations.length > 0) {{
        citations = apiCitations;
      }} else {{
        const parsed = parseCitations(text);
        cleanText = parsed.cleanText;
        citations = parsed.citations;
      }}
      if (citations.length > 0) _chatCitations = citations;
      const markdownEl = document.createElement('markdown');
      let rendered = renderMarkdown(cleanText);
      if (citations.length > 0) rendered = renderCitationChips(rendered, citations);
      markdownEl.innerHTML = rendered;
      bubble.appendChild(markdownEl);
    }} else {{
      bubble.textContent = text;
    }}
    
    msg.appendChild(bubble);
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }}
  
  function showThinkingIndicator() {{
    const msg = document.createElement('div');
    msg.className = 'msg assistant';
    msg.id = 'thinking-indicator';
    const indicator = document.createElement('div');
    indicator.className = 'thinking-indicator';
    indicator.innerHTML = '<div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div>';
    msg.appendChild(indicator);
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }}
  
  function hideThinkingIndicator() {{
    const indicator = document.getElementById('thinking-indicator');
    if (indicator) indicator.remove();
  }}

  /* ── Activity / planning panel ─────────────────────────── */
  let _activityPanel = null;
  let _activityItems = null;
  let _activityHeader = null;
  let _activityStartTs = null;

  const _activityIcons = {{
    planning: '📋', delegate_start: '🤝', delegate_plan: '📝',
    tool_result: '🔍', delegate_done: '✅', synthesizing: '⚙️',
  }};

  function _ensureActivityPanel() {{
    if (_activityPanel) return;
    _activityStartTs = Date.now();

    _activityPanel = document.createElement('div');
    _activityPanel.className = 'activity-panel';

    _activityHeader = document.createElement('div');
    _activityHeader.className = 'activity-header';
    _activityHeader.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
      '<polyline points="6 9 12 15 18 9"></polyline></svg>' +
      '<span>Processing…</span>';
    var panelRef = _activityPanel;
    _activityHeader.addEventListener('click', function() {{
      panelRef.classList.toggle('collapsed');
    }});

    _activityItems = document.createElement('div');
    _activityItems.className = 'activity-items';

    _activityPanel.appendChild(_activityHeader);
    _activityPanel.appendChild(_activityItems);

    const thinkingEl = document.getElementById('thinking-indicator');
    if (thinkingEl) {{
      thinkingEl.parentNode.insertBefore(_activityPanel, thinkingEl);
      thinkingEl.remove();
    }} else {{
      messagesEl.appendChild(_activityPanel);
    }}
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }}

  function showActivityItem(data) {{
    _ensureActivityPanel();
    const icon = _activityIcons[data.type] || '•';
    let desc = '';
    switch (data.type) {{
      case 'planning':
        desc = '<b>' + (data.agent || '') + '</b> created a plan';
        break;
      case 'delegate_start':
        desc = '<b>' + (data.agent || '') + '</b> started — ' +
               (Array.isArray(data.tasks) ? data.tasks.length + ' task(s)' : '');
        break;
      case 'delegate_plan':
        desc = '<b>' + (data.agent || '') + '</b> created its plan';
        break;
      case 'tool_result':
        desc = '<b>' + (data.agent || '') + '</b> queried <i>' +
               (data.tool || '') + '</i> (' + (data.chars || 0) + ' chars)';
        break;
      case 'delegate_done':
        desc = '<b>' + (data.agent || '') + '</b> finished (' +
               (data.chars || 0) + ' chars)';
        break;
      case 'synthesizing':
        desc = '<b>' + (data.agent || '') + '</b> is synthesizing the final answer';
        break;
      default:
        desc = JSON.stringify(data);
    }}

    let detail = '';
    if ((data.type === 'planning' || data.type === 'delegate_plan') && data.content) {{
      detail = data.content;
    }} else if (data.type === 'delegate_start' && Array.isArray(data.tasks) && data.tasks.length) {{
      detail = data.tasks.map(function(t, i) {{ return (i + 1) + '. ' + t; }}).join('\\n');
    }} else if (data.type === 'tool_result' && data.content) {{
      detail = data.content;
    }}

    const item = document.createElement('div');
    item.className = 'activity-item' + (detail ? ' expandable' : '');
    const bodyEl = document.createElement('span');
    bodyEl.className = 'activity-item-body';
    bodyEl.innerHTML = desc;

    if (detail) {{
      const detailEl = document.createElement('div');
      detailEl.className = 'activity-detail';
      detailEl.textContent = detail;
      bodyEl.appendChild(detailEl);
      item.addEventListener('click', function() {{
        item.classList.toggle('expanded');
      }});
    }}

    item.innerHTML = '<span class="activity-item-icon">' + icon + '</span>';
    item.appendChild(bodyEl);
    _activityItems.appendChild(item);
    _activityItems.scrollTop = _activityItems.scrollHeight;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }}

  function collapseActivityPanel() {{
    if (!_activityPanel) return;
    const elapsed = _activityStartTs
      ? Math.round((Date.now() - _activityStartTs) / 1000)
      : 0;
    const hdr = _activityPanel.querySelector('.activity-header span');
    if (hdr) hdr.textContent = 'Processed in ' + elapsed + 's — click to expand';
    _activityPanel.classList.add('collapsed');
  }}

  function resetActivityPanel() {{
    _activityPanel = null;
    _activityItems = null;
    _activityHeader = null;
    _activityStartTs = null;
  }}

  function showHumanInputModal(title, message) {{
    humanInputTitle.textContent = title || 'Input Required';
    humanInputMessage.textContent = message || 'Please provide your input to continue.';
    humanInputTextarea.value = '';
    humanInputModal.classList.add('active');
    humanInputTextarea.focus();
    awaitingHumanInput = true;
    inputEl.disabled = true;
    sendBtn.disabled = true;
  }}

  function hideHumanInputModal() {{
    humanInputModal.classList.remove('active');
    awaitingHumanInput = false;
    inputEl.disabled = false;
    sendBtn.disabled = false;
  }}

  async function submitHumanInput() {{
    const userInput = humanInputTextarea.value.trim();
    if (!userInput) {{
      alert('Please enter your response');
      return;
    }}

    humanInputSubmit.disabled = true;
    statusEl.textContent = 'Submitting...';

    try {{
      const resp = await fetch(SUBMIT_INPUT_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ session_id: sessionId, user_input: userInput }})
      }});

      if (!resp.ok) {{
        const err = await resp.json().catch(() => ({{}}));
        throw new Error(err.error || 'HTTP ' + resp.status);
      }}

      const data = await resp.json();
      appendMessage('user', userInput);
      messages.push({{ role: 'user', content: userInput }});
      hideHumanInputModal();

      if (data.status === 'awaiting_human_input') {{
        showHumanInputModal(data.title, data.last_conversation_message);
        currentExecutionId = data.execution_id;
      }} else if (data.status === 'success') {{
        const reply = data.response || '(No response)';
        appendMessage('assistant', reply, false, data.citations);
        messages.push({{ role: 'assistant', content: reply }});
        statusEl.textContent = '';
        currentExecutionId = null;
      }} else if (data.status === 'processing') {{
        statusEl.textContent = 'Processing...';
        setTimeout(() => {{ statusEl.textContent = ''; }}, 2000);
      }} else {{
        appendMessage('assistant', 'Error: ' + (data.error || 'Unexpected error'));
        statusEl.textContent = '';
      }}
    }} catch (e) {{
      console.error('Submit error:', e);
      appendMessage('assistant', 'Sorry, there was a problem.');
      statusEl.textContent = e.message || 'Error';
    }} finally {{
      humanInputSubmit.disabled = false;
    }}
  }}

  async function sendMessage() {{
    const text = inputEl.value.trim();
    if (!text || awaitingHumanInput) return;

    appendMessage('user', text);
    messages.push({{ role: 'user', content: text }});

    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendBtn.disabled = true;
    statusEl.textContent = '';
    showThinkingIndicator();

    try {{
      const resp = await fetch(STREAM_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ user_query: text, session_id: sessionId }})
      }});

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      let thinkingHidden = false;
      let msg = null, bubble = null, markdownEl = null;
      let accumulatedContent = '';
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {{
        const {{ done, value }} = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, {{ stream: true }});
        const lines = chunk.split('\\n');
        
        for (const line of lines) {{
          if (line.startsWith('data: ')) {{
            try {{
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'planning' || data.type === 'delegate_start' ||
                  data.type === 'delegate_plan' || data.type === 'tool_result' ||
                  data.type === 'delegate_done' || data.type === 'synthesizing') {{
                showActivityItem(data);
              }} else if (data.type === 'content') {{
                if (!thinkingHidden) {{
                  collapseActivityPanel();
                  hideThinkingIndicator();
                  thinkingHidden = true;
                  msg = document.createElement('div');
                  msg.className = 'msg assistant';
                  bubble = document.createElement('div');
                  bubble.className = 'bubble';
                  markdownEl = document.createElement('markdown');
                  bubble.appendChild(markdownEl);
                  msg.appendChild(bubble);
                  messagesEl.appendChild(msg);
                }}
                accumulatedContent += data.content;
                markdownEl.innerHTML = renderMarkdown(accumulatedContent);
                messagesEl.scrollTop = messagesEl.scrollHeight;
              }} else if (data.type === 'citations') {{
                // Render citation chips below the streamed message
                if (markdownEl && Array.isArray(data.citations) && data.citations.length > 0) {{
                  _chatCitations = data.citations;
                  markdownEl.innerHTML = renderCitationChips(renderMarkdown(accumulatedContent), data.citations);
                  messagesEl.scrollTop = messagesEl.scrollHeight;
                }}
              }} else if (data.type === 'awaiting_human_input') {{
                hideThinkingIndicator();
                showHumanInputModal(data.title, data.last_conversation_message);
                currentExecutionId = data.execution_id;
                statusEl.textContent = 'Waiting for input...';
                if (msg) msg.remove();
                return;
              }} else if (data.type === 'error') {{
                hideThinkingIndicator();
                if (msg) msg.remove();
                appendMessage('assistant', 'Error: ' + (data.error || 'Unexpected error'));
                return;
              }} else if (data.type === 'done') {{
                collapseActivityPanel();
                // Always clean the streamed text (strip citations block + heading)
                const parsed = parseCitations(accumulatedContent);
                let cleanContent = parsed.cleanText;
                let citations = [];
                if (Array.isArray(data.citations) && data.citations.length > 0) {{
                  citations = data.citations;
                }} else {{
                  citations = parsed.citations;
                }}
                _chatCitations = citations;
                if (markdownEl) {{
                  markdownEl.innerHTML = citations.length > 0
                    ? renderCitationChips(renderMarkdown(cleanContent), citations)
                    : renderMarkdown(cleanContent);
                }}
                messages.push({{ role: 'assistant', content: cleanContent }});
                statusEl.textContent = '';
                resetActivityPanel();
                return;
              }}
            }} catch (e) {{
              console.error('Parse error:', e);
            }}
          }}
        }}
      }}
    }} catch (e) {{
      console.error('Chat error:', e);
      hideThinkingIndicator();
      collapseActivityPanel();
      resetActivityPanel();
      appendMessage('assistant', 'Sorry, there was a connection problem.');
      statusEl.textContent = '';
    }} finally {{
      if (!awaitingHumanInput) sendBtn.disabled = false;
    }}
  }}

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter' && !e.shiftKey && !awaitingHumanInput) {{
      e.preventDefault();
      sendMessage();
    }}
  }});

  humanInputSubmit.addEventListener('click', submitHumanInput);
  humanInputCancel.addEventListener('click', () => {{
    hideHumanInputModal();
    statusEl.textContent = '';
  }});
  humanInputTextarea.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter' && e.ctrlKey) {{
      e.preventDefault();
      submitHumanInput();
    }}
  }});

  // Show default greeting only after preload — and only if this session has no stored history yet
  preloadPromise.then(() => {{
    if (messages.length === 0) {{
      appendMessage('assistant', INITIAL_GREETING);
      messages.push({{ role: 'assistant', content: INITIAL_GREETING }});
    }}
  }});
</script>
</body>
</html>'''
        
        return HttpResponse(html_content, content_type='text/html')
        
    except Exception as e:
        logger.error(f"❌ DEPLOYMENT: Error serving embed HTML: {e}", exc_info=True)
        return HttpResponse(
            '<html><body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f7;"><p style="color:#ef4444;">Error loading chatbot. Please try again later.</p></body></html>',
            status=500,
            content_type='text/html'
        )

