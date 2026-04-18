"""
Custom CORS middleware for Workflow Deployment API
Handles CORS for workflow deployment endpoints with project-specific origin validation
"""
import logging
import re
from typing import Tuple, Optional
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import get_object_or_404

from agent_orchestration.models import WorkflowDeployment, WorkflowAllowedOrigin

logger = logging.getLogger('workflow_deployment')


class WorkflowDeploymentCORSMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware specifically for workflow deployment endpoints
    Validates origins against project-specific allowed origins
    """
    
    # Deployment-specific paths
    DEPLOYMENT_PATHS = [
        '/api/workflow-deploy/',
    ]
    
    def process_request(self, request):
        """Process incoming requests to add CORS headers for deployment endpoints"""
        # Check if this is a deployment endpoint
        is_deployment_path = request.path.startswith('/api/workflow-deploy/')

        if not is_deployment_path:
            return None

        # Skip CORS processing for embed HTML pages — they are loaded as page
        # navigations (in iframes or directly), not as XHR/fetch API calls.
        if '/embed/' in request.path:
            return None

        # Skip origin-check for the Public Chat URL control endpoints. These
        # are consumed by the Svelte /chat/<id> page on our own origin, and
        # access control on them is enforced by the signed auth cookie — not
        # by the allowed-origin list (which governs external iframe embeds).
        if any(seg in request.path for seg in ('/public-config/', '/public-auth/', '/public-logout/')):
            return None
        
        # Extract project_id from URL
        # Pattern: /api/workflow-deploy/{project_id}/
        path_match = re.match(r'/api/workflow-deploy/([^/]+)/?', request.path)
        if not path_match:
            logger.warning(f"🚫 CORS: Invalid deployment path format: {request.path}")
            return None
        
        project_id = path_match.group(1)
        origin = request.META.get('HTTP_ORIGIN')
        
        # Handle preflight requests
        if request.method == 'OPTIONS':
            logger.debug(f"🔥 CORS DEBUG: Preflight request for deployment endpoint")
            logger.debug(f"   Origin: {repr(origin)}")
            logger.debug(f"   Path: {request.path}")
            logger.debug(f"   Project ID: {project_id}")
            
            # Check if deployment exists and origin is allowed
            is_allowed, deployment = self._check_origin_allowed(project_id, origin)
            
            if is_allowed:
                response = JsonResponse({'status': 'ok'})
                self._add_cors_headers(response, origin)
                logger.info(f"🌍 CORS: Allowed preflight for {origin} (project {project_id})")
                return response
            else:
                logger.warning(f"🚫 CORS: Blocked preflight from unauthorized origin {origin} (project {project_id})")
                response = JsonResponse({'error': 'Origin not allowed'}, status=403)
                return response
        
        return None
    
    def process_response(self, request, response):
        """Add CORS headers to responses for deployment endpoints"""
        # Check if this is a deployment endpoint
        is_deployment_path = request.path.startswith('/api/workflow-deploy/')

        if not is_deployment_path:
            return response

        # Skip CORS processing for embed HTML pages
        if '/embed/' in request.path:
            return response

        # Same exemption as process_request — public control endpoints don't
        # participate in the allowed-origin CORS flow.
        if any(seg in request.path for seg in ('/public-config/', '/public-auth/', '/public-logout/')):
            return response
        
        # Extract project_id from URL
        path_match = re.match(r'/api/workflow-deploy/([^/]+)/?', request.path)
        if not path_match:
            return response
        
        project_id = path_match.group(1)
        origin = request.META.get('HTTP_ORIGIN')
        
        # Only add headers if they haven't been added by Django CORS middleware
        if not response.get('Access-Control-Allow-Origin'):
            # Check if deployment exists and origin is allowed
            is_allowed, deployment = self._check_origin_allowed(project_id, origin)
            
            if is_allowed:
                self._add_cors_headers(response, origin)
                logger.debug(f"🌍 CORS: Added headers for {origin} on {request.path}")
            else:
                logger.warning(f"🚫 CORS: Blocked response to unauthorized origin {origin} on {request.path}")
        
        return response
    
    def _check_origin_allowed(self, project_id: str, origin: str) -> Tuple[bool, Optional[WorkflowDeployment]]:
        """
        Check if origin is allowed for the deployment
        
        Args:
            project_id: Project ID (UUID string)
            origin: Request origin
            
        Returns:
            Tuple of (is_allowed, deployment)
        """
        try:
            # Get active deployment for this project
            from users.models import IntelliDocProject
            from django.core.exceptions import ObjectDoesNotExist
            
            try:
                project = IntelliDocProject.objects.get(project_id=project_id)
            except IntelliDocProject.DoesNotExist:
                logger.warning(f"🚫 CORS: Project {project_id} not found")
                return False, None
            
            deployment = WorkflowDeployment.objects.filter(
                project=project,
                is_active=True
            ).first()
            
            if not deployment:
                logger.warning(f"🚫 CORS: No active deployment for project {project_id}")
                return False, None
            
            # Allow requests with no origin header (e.g., from iframes, same-origin, or null origin)
            if not origin:
                logger.debug(f"✅ CORS: No origin header — allowing (likely iframe or same-origin)")
                return True, deployment
            
            # Normalize origin (remove trailing slash, lowercase)
            normalized_origin = origin.rstrip('/').lower()
            
            # Check against allowed origins
            allowed_origin = WorkflowAllowedOrigin.objects.filter(
                deployment=deployment,
                origin__iexact=normalized_origin,
                is_active=True
            ).first()
            
            if allowed_origin:
                logger.debug(f"✅ CORS: Origin {origin} is allowed for deployment {deployment.id}")
                return True, deployment
            else:
                logger.warning(f"🚫 CORS: Origin {origin} is not allowed for deployment {deployment.id}")
                return False, deployment
                
        except Exception as e:
            logger.error(f"❌ CORS: Error checking origin: {e}", exc_info=True)
            return False, None
    
    def _add_cors_headers(self, response, origin):
        """Add CORS headers to response"""
        response['Access-Control-Allow-Origin'] = origin or '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With'
        if origin:
            response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Max-Age'] = '86400'  # 24 hours
        
        # Special headers for streaming responses
        if response.get('Content-Type', '').startswith('text/event-stream'):
            response['Access-Control-Allow-Headers'] += ', Cache-Control'
            response['Cache-Control'] = 'no-cache'

