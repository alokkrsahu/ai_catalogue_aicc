"""
URL Configuration for Public Chatbot API - WITH CORS HOTFIX
Completely isolated endpoints - no impact on existing AI Catalogue URLs
"""
from django.urls import path
from . import views
from .cors_hotfix import cors_test_endpoint

app_name = 'public_chatbot'

urlpatterns = [
    # CORS test endpoint (temporary)
    path('cors-test/', cors_test_endpoint, name='cors_test'),
    
    # Main public chatbot API endpoint
    path('', views.public_chat_api, name='chat_api'),
    
    # Streaming chatbot API endpoint (Server-Sent Events)
    path('stream/', views.public_chat_stream_api, name='chat_stream_api'),
    
    # Health check endpoint for monitoring
    path('health/', views.health_check, name='health_check'),
]