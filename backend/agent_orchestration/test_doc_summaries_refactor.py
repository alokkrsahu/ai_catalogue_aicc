import unittest
from unittest.mock import MagicMock, patch

from agent_orchestration.docaware_handler import DocAwareHandler
from vector_search.document_summarization.file_based_document_summarizer import _parse_long_short_summaries


class TestFileBasedDocumentSummarizerParsing(unittest.TestCase):
    def test_parses_json_with_code_fences(self):
        raw = """
        ```json
        {
          "long_summary": "LONG_SUMMARY_TEXT",
          "short_summary": "SHORT_SUMMARY_TEXT"
        }
        ```
        """
        long_summary, short_summary = _parse_long_short_summaries(raw)
        self.assertEqual(long_summary, "LONG_SUMMARY_TEXT")
        self.assertEqual(short_summary, "SHORT_SUMMARY_TEXT")


class TestDocAwareDocSummaryInjection(unittest.IsolatedAsyncioTestCase):
    async def test_injects_short_summary_once_per_document(self):
        handler = DocAwareHandler()

        # Two chunks for the same document_id; the document short summary should appear once.
        doc_id = "11111111-1111-1111-1111-111111111111"
        search_results = [
            {
                "content": "Chunk 1 content",
                "metadata": {"score": 0.9, "source": "file1.pdf", "page": 1, "document_id": doc_id},
            },
            {
                "content": "Chunk 2 content",
                "metadata": {"score": 0.8, "source": "file1.pdf", "page": 2, "document_id": doc_id},
            },
        ]

        class DummyDocAwareService:
            def __init__(self, project_id: str):
                self.project_id = project_id

            def search_documents(self, **kwargs):
                return search_results

        # Mock ProjectDocumentSummary query results
        short_summary_text = "DOC_SHORT_SUMMARY"
        mock_summary_qs = MagicMock()
        mock_summary_qs.values_list.return_value = [(doc_id, short_summary_text)]
        mock_summary_model = MagicMock()
        mock_summary_model.objects.filter.return_value = mock_summary_qs

        agent_node = {
            "data": {
                "search_method": "hybrid_search",
                "search_parameters": {"search_limit": 2},
                "content_filters": [],
            }
        }

        with patch("agent_orchestration.docaware_handler.EnhancedDocAwareAgentService", DummyDocAwareService), patch(
            "agent_orchestration.docaware_handler.ProjectDocumentSummary", mock_summary_model
        ):
            context = await handler.get_docaware_context_from_conversation_query(
                agent_node=agent_node,
                search_query="What is in the document?",
                project_id="",  # falsy so metric saving is skipped
                conversation_history="User: What is in the document?",
            )

        self.assertIn(short_summary_text, context)
        self.assertEqual(context.count("=== Document Short Summary ==="), 1)

    async def test_does_not_inject_when_short_summary_missing(self):
        handler = DocAwareHandler()

        doc_id = "22222222-2222-2222-2222-222222222222"
        search_results = [
            {
                "content": "Chunk content",
                "metadata": {"score": 0.9, "source": "file2.pdf", "page": 1, "document_id": doc_id},
            }
        ]

        class DummyDocAwareService:
            def __init__(self, project_id: str):
                self.project_id = project_id

            def search_documents(self, **kwargs):
                return search_results

        mock_summary_qs = MagicMock()
        mock_summary_qs.values_list.return_value = []
        mock_summary_model = MagicMock()
        mock_summary_model.objects.filter.return_value = mock_summary_qs

        agent_node = {
            "data": {
                "search_method": "hybrid_search",
                "search_parameters": {"search_limit": 1},
                "content_filters": [],
            }
        }

        with patch("agent_orchestration.docaware_handler.EnhancedDocAwareAgentService", DummyDocAwareService), patch(
            "agent_orchestration.docaware_handler.ProjectDocumentSummary", mock_summary_model
        ):
            context = await handler.get_docaware_context_from_conversation_query(
                agent_node=agent_node,
                search_query="Summarize this.",
                project_id="",
                conversation_history="User: Summarize this.",
            )

        self.assertNotIn("=== Document Short Summary ===", context)


if __name__ == "__main__":
    unittest.main()

