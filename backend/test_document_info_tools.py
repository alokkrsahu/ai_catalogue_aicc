#!/usr/bin/env python3
"""
Test script for the 3 new document-info tools:
  - list_project_files
  - count_project_files
  - get_document_summaries

Run from the backend directory:
    python test_document_info_tools.py

Requires: running PostgreSQL (the app's DB). Does NOT require the full stack.
"""
import sys
import os
import asyncio

# Add backend directory to path and configure Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from agent_orchestration import document_tool_service


def get_test_project_id():
    """Return a project_id that has at least one processed document, or any project."""
    from users.models import ProjectDocument, IntelliDocProject

    doc = (
        ProjectDocument.objects
        .filter(upload_status__in=("completed", "ready"))
        .select_related("project")
        .first()
    )
    if doc:
        return str(doc.project.project_id), doc.original_filename

    proj = IntelliDocProject.objects.first()
    return (str(proj.project_id) if proj else None), None


async def run_tests():
    passed = 0
    failed = 0

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f"  ✅ {msg}")

    def fail(msg):
        nonlocal failed
        failed += 1
        print(f"  ❌ {msg}")

    # ── 1. Schema tests (no DB) ─────────────────────────────────────────────
    print("\n── 1. Tool schema tests ──")
    try:
        tools = document_tool_service.build_document_info_tools()
        assert len(tools) == 3, f"Expected 3 tools, got {len(tools)}"

        names = {t["function"]["name"] for t in tools}
        assert document_tool_service.LIST_FILES_TOOL_NAME in names
        assert document_tool_service.COUNT_FILES_TOOL_NAME in names
        assert document_tool_service.GET_SUMMARIES_TOOL_NAME in names

        for t in tools:
            assert t["type"] == "function", f"Bad type: {t['type']}"
            assert t["function"]["description"], "Empty description"
            params = t["function"]["parameters"]
            assert params["type"] == "object"
            assert params["required"] == []

        ok("build_document_info_tools() returns 3 correct schemas")
    except AssertionError as e:
        fail(f"Schema assertion failed: {e}")
    except Exception as e:
        fail(f"Unexpected error in schema test: {e}")

    # ── 2. DB tests ─────────────────────────────────────────────────────────
    print("\n── 2. DB tests ──")
    project_id, first_filename = get_test_project_id()

    if not project_id:
        print("  ⚠️  No projects found in DB — skipping DB tests")
    else:
        print(f"  Using project_id: {project_id}")

        # count — unfiltered
        try:
            result = await document_tool_service.execute_count_files_tool(project_id)
            assert result.isdigit(), f"Not a digit string: {result!r}"
            ok(f"count_project_files (unfiltered) = {result}")
            doc_count = int(result)
        except AssertionError as e:
            fail(f"count_project_files: {e}")
            doc_count = 0
        except Exception as e:
            fail(f"count_project_files raised: {e}")
            doc_count = 0

        # count — nonexistent filename filter → must return "0"
        try:
            result = await document_tool_service.execute_count_files_tool(
                project_id, selected_filenames=["__nonexistent_file_xyz__.pdf"]
            )
            assert result == "0", f"Expected '0', got {result!r}"
            ok("count_project_files with nonexistent filter returns '0'")
        except AssertionError as e:
            fail(f"count_project_files (filter): {e}")
        except Exception as e:
            fail(f"count_project_files (filter) raised: {e}")

        # list — unfiltered
        try:
            result = await document_tool_service.execute_list_files_tool(project_id)
            assert isinstance(result, str) and result
            if doc_count > 0:
                assert result.startswith("1. "), (
                    f"Expected numbered list starting '1. ', got: {result[:100]!r}"
                )
                lines = result.strip().splitlines()
                assert len(lines) == doc_count, (
                    f"Line count {len(lines)} != doc count {doc_count}"
                )
            ok(f"list_project_files (unfiltered) returned {doc_count} entries")
        except AssertionError as e:
            fail(f"list_project_files: {e}")
        except Exception as e:
            fail(f"list_project_files raised: {e}")

        # list — scoped to one file
        if first_filename:
            try:
                result = await document_tool_service.execute_list_files_tool(
                    project_id, selected_filenames=[first_filename]
                )
                assert result.startswith("1. "), f"Expected 1 entry, got: {result!r}"
                lines = result.strip().splitlines()
                assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"
                assert first_filename in lines[0], (
                    f"Filename {first_filename!r} not in result line: {lines[0]!r}"
                )
                ok(f"list_project_files (scoped to 1 file) returned 1 entry correctly")
            except AssertionError as e:
                fail(f"list_project_files (scoped): {e}")
            except Exception as e:
                fail(f"list_project_files (scoped) raised: {e}")

        # summaries — unfiltered
        try:
            result = await document_tool_service.execute_get_summaries_tool(project_id)
            assert isinstance(result, str) and result
            if doc_count > 0:
                assert "--- " in result, (
                    f"Expected '--- filename ---' blocks, got: {result[:200]!r}"
                )
                blocks = [b for b in result.split("\n\n") if b.strip().startswith("---")]
                assert len(blocks) == doc_count, (
                    f"Block count {len(blocks)} != doc count {doc_count}"
                )
            ok(f"get_document_summaries returned {doc_count} formatted blocks")
        except AssertionError as e:
            fail(f"get_document_summaries: {e}")
        except Exception as e:
            fail(f"get_document_summaries raised: {e}")

        # summaries — verify document_summary accessor (the bug fix)
        try:
            from users.models import ProjectDocument
            docs_with_summary = (
                ProjectDocument.objects
                .filter(
                    project__project_id=project_id,
                    upload_status__in=("completed", "ready"),
                )
                .select_related("document_summary")
                .order_by("original_filename")
            )
            docs_list = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(docs_with_summary)
            )
            # Access doc.document_summary on each — should not raise
            for doc in docs_list:
                _ = getattr(doc, "document_summary", None)
            ok(f"document_summary accessor works on {len(docs_list)} docs (bug fix verified)")
        except Exception as e:
            fail(f"document_summary accessor raised: {e}")

    # ── Result ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print("💥 Some tests failed — see above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
