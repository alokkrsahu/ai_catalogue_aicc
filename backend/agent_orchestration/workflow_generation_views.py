"""
API endpoint for AI-powered workflow generation.
"""
import json
import logging
import asyncio

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import IntelliDocProject

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_workflow_view(request, project_id):
    """
    Generate a workflow from natural language requirements using LLM tool-calling.

    POST /api/agent-orchestration/projects/{project_id}/generate-workflow/
    Body: { "message": string, "conversation_history": [...] }
    """
    try:
        project = IntelliDocProject.objects.get(project_id=project_id)
    except IntelliDocProject.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check user access
    if not project.has_user_access(request.user):
        return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

    user_message = request.data.get("message", "").strip()
    if not user_message:
        return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

    conversation_history = request.data.get("conversation_history", [])
    current_graph = request.data.get("current_graph", None)

    try:
        from .workflow_generator import generate_workflow

        async def _run_with_timeout():
            return await asyncio.wait_for(
                generate_workflow(
                    project=project,
                    user_message=user_message,
                    conversation_history=conversation_history,
                    current_graph=current_graph,
                ),
                timeout=120.0,  # 2 minutes max
            )

        try:
            result = asyncio.run(_run_with_timeout())
        except asyncio.TimeoutError:
            return Response(
                {"error": "Workflow generation timed out. Try a simpler request."},
                status=status.HTTP_408_REQUEST_TIMEOUT,
            )

        return Response({
            "graph_json": result["graph_json"],
            "explanation": result["explanation"],
            "tool_calls": result["tool_calls"],
            "errors": result["errors"],
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"❌ WORKFLOW GEN: Error generating workflow: {e}", exc_info=True)
        return Response(
            {"error": f"Failed to generate workflow: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
