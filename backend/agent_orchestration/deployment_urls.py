"""
URL routing for workflow deployment endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .deployment_views import DeploymentViewSet, public_chat_endpoint, embed_chatbot_html, submit_deployment_human_input

# Create router for deployment management endpoints
router = DefaultRouter()
router.register(
    r'projects/(?P<project_id>[^/.]+)/deployment',
    DeploymentViewSet,
    basename='deployment'
)

urlpatterns = [
    # Public endpoint (unauthenticated)
    path('api/workflow-deploy/<uuid:project_id>/', public_chat_endpoint, name='workflow-deploy-public'),
    
    # Submit human input endpoint (for UserProxyAgent in deployment)
    path('api/workflow-deploy/<uuid:project_id>/submit-input/', submit_deployment_human_input, name='workflow-deploy-submit-input'),
    
    # Embed endpoint (serves chatbot HTML for iframe)
    path('api/workflow-deploy/<uuid:project_id>/embed/', embed_chatbot_html, name='workflow-deploy-embed'),
    
    # Explicit routes for ViewSet actions (ViewSet doesn't auto-map standard CRUD)
    path(
        'api/agent-orchestration/projects/<uuid:project_id>/deployment/',
        DeploymentViewSet.as_view({
            'get': 'retrieve',
            'post': 'create'
        }),
        name='deployment-detail'
    ),
    path(
        'api/agent-orchestration/projects/<uuid:project_id>/deployment/toggle/',
        DeploymentViewSet.as_view({'patch': 'toggle'}),
        name='deployment-toggle'
    ),
    path(
        'api/agent-orchestration/projects/<uuid:project_id>/deployment/origins/',
        DeploymentViewSet.as_view({
            'get': 'list_origins',
            'post': 'add_origin'
        }),
        name='deployment-origins'
    ),
    path(
        'api/agent-orchestration/projects/<uuid:project_id>/deployment/origins/<int:origin_id>/',
        DeploymentViewSet.as_view({
            'delete': 'remove_origin',
            'patch': 'update_origin'
        }),
        name='deployment-origin-detail'
    ),
    path(
        'api/agent-orchestration/projects/<uuid:project_id>/deployment/activity/',
        DeploymentViewSet.as_view({'get': 'get_deployment_activity'}),
        name='deployment-activity'
    ),
]

