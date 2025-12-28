"""
Workflow Deployment API Views
Management endpoints for deployments and public-facing chat endpoint
"""
import logging
import json
import uuid
import hashlib
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
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
        # Update session with assistant response
        if assistant_response:
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
                sessions_query = sessions_query.filter(session_id__icontains=session_id_filter)
            
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
        # This allows us to return the response immediately
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
        
        # Create a thread-safe result container
        result_container = {'result': None, 'error': None, 'completed': False}
        
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
                assistant_response = executor._extract_end_node_output(result, graph_json)
            else:
                # Fallback: try to get from result directly
                assistant_response = result.get('response', '') or result.get('conversation_history', '')
            
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
    .human-input-modal {{ display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:1000; justify-content:center; align-items:center; }}
    .human-input-modal.active {{ display:flex; }}
    .human-input-box {{ background:#fff; border-radius:12px; padding:24px; max-width:500px; width:90%; box-shadow:0 20px 60px rgba(0,0,0,0.3); }}
    .human-input-title {{ font-size:18px; font-weight:600; color:#0b3b66; margin-bottom:12px; }}
    .human-input-message {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; padding:12px; margin-bottom:16px; font-size:14px; color:#374151; line-height:1.5; }}
    .human-input-textarea {{ width:100%; min-height:80px; border:1px solid #d1d5db; border-radius:8px; padding:10px; font-size:14px; resize:vertical; font-family:inherit; }}
    .human-input-buttons {{ display:flex; gap:8px; justify-content:flex-end; margin-top:16px; }}
    .human-input-buttons button {{ padding:8px 16px; border-radius:8px; font-size:14px; cursor:pointer; border:none; }}
    .human-input-buttons .submit-btn {{ background:#0b3b66; color:#fff; }}
    .human-input-buttons .submit-btn:disabled {{ opacity:0.6; cursor:not-allowed; }}
    .human-input-buttons .cancel-btn {{ background:#f3f4f6; color:#374151; }}
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

<!-- Human Input Modal -->
<div id="humanInputModal" class="human-input-modal">
  <div class="human-input-box">
    <div class="human-input-title" id="humanInputTitle">USER INPUT REQUIRED</div>
    <div class="human-input-message" id="humanInputMessage"></div>
    <textarea id="humanInputTextarea" class="human-input-textarea" placeholder="Enter your response..."></textarea>
    <div class="human-input-buttons">
      <button class="cancel-btn" id="humanInputCancel">Cancel</button>
      <button class="submit-btn" id="humanInputSubmit">Submit</button>
    </div>
  </div>
</div>

<script>
  const ENDPOINT_URL = {json.dumps(endpoint_url)};
  const SUBMIT_INPUT_URL = ENDPOINT_URL.replace(/\/$/, '') + '/submit-input/';
  const INITIAL_GREETING = {json.dumps(initial_greeting)};

  const messages = [];
  const sessionId = 'sess_' + Math.random().toString(36).slice(2);
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

  function showHumanInputModal(title, message) {{
    humanInputTitle.textContent = title || 'USER INPUT REQUIRED';
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
    statusEl.textContent = 'Submitting your response...';

    try {{
      const resp = await fetch(SUBMIT_INPUT_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          session_id: sessionId,
          user_input: userInput
        }})
      }});

      if (!resp.ok) {{
        const err = await resp.json().catch(() => ({{}}));
        throw new Error(err.error || 'HTTP ' + resp.status);
      }}

      const data = await resp.json();
      
      // Add user input to conversation
      appendMessage('user', userInput);
      messages.push({{ role: 'user', content: userInput }});
      
      hideHumanInputModal();

      if (data.status === 'awaiting_human_input') {{
        // Another UserProxyAgent requires input
        showHumanInputModal(data.title, data.last_conversation_message);
        currentExecutionId = data.execution_id;
      }} else if (data.status === 'success') {{
        const reply = data.response || '(No response)';
        appendMessage('assistant', reply);
        messages.push({{ role: 'assistant', content: reply }});
        statusEl.textContent = '';
        currentExecutionId = null;
      }} else if (data.status === 'processing') {{
        statusEl.textContent = 'Workflow is processing. Please wait...';
        // Poll for completion or show message
        setTimeout(() => {{
          statusEl.textContent = 'Processing complete. Check the conversation.';
        }}, 2000);
      }} else {{
        appendMessage('assistant', 'Error: ' + (data.error || 'Unexpected error'));
        statusEl.textContent = 'Error from workflow endpoint';
      }}
    }} catch (e) {{
      console.error('Submit input error:', e);
      appendMessage('assistant', 'Sorry, there was a problem submitting your input.');
      statusEl.textContent = e.message || 'Network error';
    }} finally {{
      humanInputSubmit.disabled = false;
    }}
  }}

  async function sendMessage() {{
    const text = inputEl.value.trim();
    if (!text) return;

    if (awaitingHumanInput) {{
      alert('Please respond to the human input request first');
      return;
    }}

    appendMessage('user', text);
    messages.push({{ role: 'user', content: text }});

    inputEl.value = '';
    sendBtn.disabled = true;
    statusEl.textContent = 'Contacting workflow...';

    try {{
      const resp = await fetch(ENDPOINT_URL, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          user_query: text,
          session_id: sessionId
        }})
      }});

      if (!resp.ok) {{
        const err = await resp.json().catch(() => ({{}}));
        throw new Error(err.error || 'HTTP ' + resp.status);
      }}

      const data = await resp.json();
      
      if (data.status === 'awaiting_human_input') {{
        // UserProxyAgent requires human input
        showHumanInputModal(data.title, data.last_conversation_message);
        currentExecutionId = data.execution_id;
        statusEl.textContent = 'Waiting for your input...';
      }} else if (data.status === 'success') {{
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
      if (!awaitingHumanInput) {{
        sendBtn.disabled = false;
      }}
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
    statusEl.textContent = 'Input cancelled';
  }});
  humanInputTextarea.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter' && e.ctrlKey) {{
      e.preventDefault();
      submitHumanInput();
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

