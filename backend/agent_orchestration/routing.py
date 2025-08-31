"""
WebSocket Routing for Agent Orchestration
Template Independent Real-time Communication
"""

from django.urls import re_path
from agent_orchestration.consumers import AgentOrchestrationConsumer, WorkflowStatusConsumer

websocket_urlpatterns = [
    # Main agent orchestration WebSocket (full features)
    re_path(r'ws/agent_orchestration/(?P<project_id>[0-9a-f-]+)/$', AgentOrchestrationConsumer.as_asgi()),
    
    # Lightweight status-only WebSocket
    re_path(r'ws/workflow_status/(?P<project_id>[0-9a-f-]+)/$', WorkflowStatusConsumer.as_asgi()),
]
