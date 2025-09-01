"""
Custom CORS middleware for Public Chatbot API
Handles CORS for public chatbot endpoints specifically
"""

import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('public_chatbot')


class PublicChatbotCORSMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware specifically for public chatbot endpoints
    Handles GitHub Pages and other external origins
    """
    
    # Allowed origins for public chatbot
    ALLOWED_ORIGINS = [
        'https://oxfordcompetencycenters.github.io',
        'https://aicc.uksouth.cloudapp.azure.com',
        'http://localhost:3000',
        'http://localhost:5173',
        'http://localhost:8080',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:8080',
        # Add any other origins that need access to the public chatbot
    ]
    
    # Chatbot-specific paths
    CHATBOT_PATHS = [
        '/api/public-chatbot/',
        '/api/public-chatbot/stream/',
        '/api/public-chatbot/health/',
    ]
    
    def process_request(self, request):
        """Process incoming requests to add CORS headers for chatbot endpoints"""
        # Check if this is a chatbot endpoint - be more flexible with path matching
        is_chatbot_path = (
            request.path.startswith('/api/public-chatbot/') or
            request.path.startswith('/api/public-chatbot')
        )
        
        if not is_chatbot_path:
            return None
        
        origin = request.META.get('HTTP_ORIGIN')
        
        # DEBUG: Log all preflight requests for chatbot endpoints
        if request.method == 'OPTIONS':
            logger.info(f"🌍 CORS DEBUG: Preflight request")
            logger.info(f"   Origin: {origin}")
            logger.info(f"   Path: {request.path}")
            logger.info(f"   Method: {request.method}")
            logger.info(f"   Allowed origins: {self.ALLOWED_ORIGINS}")
            logger.info(f"   Origin in allowed: {origin in self.ALLOWED_ORIGINS}")
            
            # Check if origin is allowed
            if origin in self.ALLOWED_ORIGINS:
                response = JsonResponse({'status': 'ok'})
                self._add_cors_headers(response, origin)
                logger.info(f"🌍 CORS: Allowed preflight for {origin}")
                return response
            else:
                logger.warning(f"🚫 CORS: Blocked preflight from unauthorized origin {origin}")
                response = JsonResponse({'error': 'Origin not allowed'}, status=403)
                return response
        
        return None
    
    def process_response(self, request, response):
        """Add CORS headers to responses for chatbot endpoints"""
        # Check if this is a chatbot endpoint - be more flexible with path matching
        is_chatbot_path = (
            request.path.startswith('/api/public-chatbot/') or
            request.path.startswith('/api/public-chatbot')
        )
        
        if not is_chatbot_path:
            return response
        
        origin = request.META.get('HTTP_ORIGIN')
        
        # Add CORS headers if origin is allowed
        if origin in self.ALLOWED_ORIGINS:
            self._add_cors_headers(response, origin)
            logger.debug(f"🌍 CORS: Added headers for {origin} on {request.path}")
        else:
            logger.warning(f"🚫 CORS: Blocked response to unauthorized origin {origin} on {request.path}")
        
        return response
    
    def _add_cors_headers(self, response, origin):
        """Add CORS headers to response"""
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With'
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Max-Age'] = '86400'  # 24 hours
        
        # Special headers for streaming responses
        if '/stream/' in getattr(response, 'url', '') or response.get('Content-Type', '').startswith('text/event-stream'):
            response['Access-Control-Allow-Headers'] += ', Cache-Control'
            response['Cache-Control'] = 'no-cache'
