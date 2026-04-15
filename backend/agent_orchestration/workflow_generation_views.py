"""
API endpoint for AI-powered workflow generation.
"""
import json
import logging
import asyncio
import os
from typing import List, Optional

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import IntelliDocProject

logger = logging.getLogger(__name__)


# Per-file extracted-text cap and aggregate cap to keep the LLM prompt bounded.
MAX_FILES_PER_TURN = 5
PER_FILE_TEXT_CAP = 20_000
TOTAL_ATTACHED_TEXT_CAP = 80_000


def _extract_attached_files_text(uploaded_files: list) -> Optional[str]:
    """
    Run uploaded files through the existing DocumentProcessor and stitch the
    extracted text into a single block to fold into the user message.

    Returns None when no files are uploaded. Per-file failures and unsupported
    extensions are recorded inline (so a bad file never fails the whole turn).
    """
    if not uploaded_files:
        return None

    # Lazy-import to avoid Django app-loading issues at module import time.
    from public_chatbot.document_processor import DocumentProcessor

    processor = DocumentProcessor()
    supported = DocumentProcessor.SUPPORTED_FORMATS  # ext → method name
    chunks: List[str] = []
    total_chars = 0

    files = list(uploaded_files)[:MAX_FILES_PER_TURN]

    for idx, f in enumerate(files, start=1):
        name = getattr(f, "name", f"file_{idx}")
        ext = os.path.splitext(name)[1].lower()

        method_name = supported.get(ext)
        if not method_name:
            chunks.append(f"[{idx}] {name} — [skipped: extension {ext or '(none)'} not supported]")
            continue

        try:
            method = getattr(processor, method_name, None)
            if not callable(method):
                chunks.append(f"[{idx}] {name} — [skipped: no extractor for {ext}]")
                continue
            text = method(f) or ""
        except Exception as e:
            logger.warning(f"⚠️ WORKFLOW GEN: Failed to extract '{name}': {e}")
            chunks.append(f"[{idx}] {name} — [error extracting: {str(e)[:200]}]")
            continue

        truncated = False
        if len(text) > PER_FILE_TEXT_CAP:
            text = text[:PER_FILE_TEXT_CAP].rstrip() + "\n…[truncated]"
            truncated = True
        header = f"[{idx}] {name} ({len(text):,} chars{' — truncated' if truncated else ''})"
        chunks.append(f"{header}\n{text}")
        total_chars += len(text)

    if not chunks:
        return None

    body = "\n\n".join(chunks)
    if len(body) > TOTAL_ATTACHED_TEXT_CAP:
        body = body[:TOTAL_ATTACHED_TEXT_CAP].rstrip() + "\n…[aggregate truncated]"

    return f"--- ATTACHED FILES ---\n{body}\n--- END ATTACHED FILES ---"


def _coerce_json_field(value):
    """Form-encoded multipart sends nested JSON as a string — parse if needed."""
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return None
    return value


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def generate_workflow_view(request, project_id):
    """
    Generate a workflow from natural language requirements using LLM tool-calling.

    POST /api/agent-orchestration/projects/{project_id}/generate-workflow/

    JSON body (no attachments):
      { "message": str, "conversation_history": [...], "current_graph": {...} }

    Multipart body (with file attachments):
      message                  : str
      conversation_history     : JSON string
      current_graph            : JSON string
      files                    : one or more uploaded files
    """
    try:
        project = IntelliDocProject.objects.get(project_id=project_id)
    except IntelliDocProject.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check user access
    if not project.has_user_access(request.user):
        return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

    user_message = (request.data.get("message") or "").strip()
    if not user_message:
        return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

    # In multipart requests, nested fields arrive as JSON strings.
    conversation_history = _coerce_json_field(request.data.get("conversation_history", []))
    if conversation_history is None:
        conversation_history = []
    current_graph = _coerce_json_field(request.data.get("current_graph", None))

    # Files (if any) — DRF makes them available via request.FILES.getlist.
    uploaded_files = request.FILES.getlist("files") if hasattr(request, "FILES") else []
    if len(uploaded_files) > MAX_FILES_PER_TURN:
        return Response(
            {"error": f"At most {MAX_FILES_PER_TURN} files per message."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        attached_files_text = _extract_attached_files_text(uploaded_files)
    except Exception as e:
        logger.error(f"❌ WORKFLOW GEN: file extraction crashed: {e}", exc_info=True)
        return Response(
            {"error": f"Failed to read attached files: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from .workflow_generator import generate_workflow

        async def _run_with_timeout():
            return await asyncio.wait_for(
                generate_workflow(
                    project=project,
                    user_message=user_message,
                    conversation_history=conversation_history,
                    current_graph=current_graph,
                    attached_files_text=attached_files_text,
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
            # Pillar 1: plan from the planning phase (empty for fresh builds)
            "plan": result.get("plan", ""),
            # Pillar 4: diff for preview UX (None for fresh builds — frontend
            # then auto-applies as before)
            "diff": result.get("diff"),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"❌ WORKFLOW GEN: Error generating workflow: {e}", exc_info=True)
        return Response(
            {"error": f"Failed to generate workflow: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
