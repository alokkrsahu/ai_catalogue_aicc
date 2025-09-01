"""
IMMEDIATE CORS FIX - Direct view modification
This provides CORS headers directly in the views without requiring middleware restart
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

def add_cors_headers(response, request):
    """Add CORS headers to any response"""
    origin = request.META.get('HTTP_ORIGIN')
    
    # Allowed origins for public chatbot
    allowed_origins = [
        'https://oxfordcompetencycenters.github.io',
        'https://aicc.uksouth.cloudapp.azure.com', 
        'http://localhost:3000',
        'http://localhost:5173',
    ]
    
    # Set CORS headers
    if origin in allowed_origins:
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'  # Fallback for public API
    
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With, Cache-Control'
    response['Access-Control-Allow-Credentials'] = 'true'
    response['Access-Control-Max-Age'] = '86400'
    
    return response

# This can be imported and used immediately in views.py
