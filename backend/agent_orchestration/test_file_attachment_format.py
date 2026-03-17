"""
Tests for ChatManager.format_messages_with_file_refs and alignment with
OpenAI Responses API (_build_responses_api_input).
File refs are attached only to the last user message.
"""
import unittest

from agent_orchestration.chat_manager import ChatManager


class TestFormatMessagesWithFileRefs(unittest.TestCase):
    """Test file ref formatting and OpenAI Responses API compatibility."""

    def test_file_refs_only_on_last_user_message(self):
        """File refs are attached only to the most recent user message."""
        messages = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question with files"},
        ]
        file_references = [
            {"file_id": "file-abc", "filename": "doc.pdf", "provider": "openai"},
        ]
        result = ChatManager.format_messages_with_file_refs(
            messages, file_references, "openai"
        )
        self.assertEqual(len(result), 3)
        # First user message: unchanged (string content)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "First question")
        # Assistant: unchanged
        self.assertEqual(result[1]["role"], "assistant")
        self.assertEqual(result[1]["content"], "First answer")
        # Last user message: content is array with text + file
        self.assertEqual(result[2]["role"], "user")
        self.assertIsInstance(result[2]["content"], list)
        parts = result[2]["content"]
        self.assertGreaterEqual(len(parts), 2)
        self.assertEqual(parts[0].get("type"), "text")
        self.assertEqual(parts[0].get("text"), "Second question with files")
        self.assertEqual(parts[1].get("type"), "file")
        self.assertEqual(parts[1].get("file", {}).get("file_id"), "file-abc")

    def test_openai_responses_api_accepts_formatted_messages(self):
        """Output of format_messages_with_file_refs is valid for OpenAI _build_responses_api_input."""
        from llm_eval.providers.openai_provider import OpenAIProvider

        messages = [
            {"role": "user", "content": "Summarize the document."},
        ]
        file_references = [
            {"file_id": "file-xyz", "filename": "report.pdf", "provider": "openai"},
        ]
        formatted = ChatManager.format_messages_with_file_refs(
            messages, file_references, "openai"
        )
        self.assertTrue(OpenAIProvider._messages_contain_file_refs(formatted))
        instructions, input_items = OpenAIProvider._build_responses_api_input(formatted)
        self.assertIsNone(instructions)
        self.assertEqual(len(input_items), 1)
        content = input_items[0].get("content") or []
        text_parts = [p for p in content if isinstance(p, dict) and p.get("type") == "input_text"]
        file_parts = [p for p in content if isinstance(p, dict) and p.get("type") == "input_file"]
        self.assertEqual(len(text_parts), 1)
        self.assertEqual(text_parts[0].get("text"), "Summarize the document.")
        self.assertEqual(len(file_parts), 1)
        self.assertEqual(file_parts[0].get("file_id"), "file-xyz")

    def test_content_already_array_appends_file_parts(self):
        """When last user message content is already a list, file refs are appended."""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Use this file."}]},
        ]
        file_references = [
            {"file_id": "file-123", "filename": "a.pdf", "provider": "openai"},
        ]
        result = ChatManager.format_messages_with_file_refs(
            messages, file_references, "openai"
        )
        self.assertEqual(len(result), 1)
        parts = result[0]["content"]
        self.assertIsInstance(parts, list)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], {"type": "text", "text": "Use this file."})
        self.assertEqual(parts[1].get("type"), "file")
        self.assertEqual(parts[1].get("file", {}).get("file_id"), "file-123")

    def test_empty_file_references_returns_unchanged(self):
        """When file_references is empty, messages are returned unchanged."""
        messages = [{"role": "user", "content": "Hello"}]
        result = ChatManager.format_messages_with_file_refs(messages, [], "openai")
        self.assertEqual(result, messages)

    def test_anthropic_format_has_document_blocks(self):
        """Anthropic provider gets document blocks with file_id."""
        messages = [{"role": "user", "content": "Review this."}]
        file_references = [{"file_id": "ant-file-1", "filename": "x.pdf", "provider": "anthropic"}]
        result = ChatManager.format_messages_with_file_refs(
            messages, file_references, "anthropic"
        )
        parts = result[0]["content"]
        self.assertEqual(parts[0].get("type"), "text")
        self.assertEqual(parts[1].get("type"), "document")
        self.assertEqual(parts[1].get("source", {}).get("file_id"), "ant-file-1")

    def test_gemini_format_has_file_data_parts(self):
        """Google/Gemini provider gets file_data with file_uri and mime_type."""
        messages = [{"role": "user", "content": "Analyze."}]
        file_references = [
            {"file_id": "gem-uri-1", "filename": "y.pdf", "file_type": "application/pdf"},
        ]
        result = ChatManager.format_messages_with_file_refs(
            messages, file_references, "gemini"
        )
        parts = result[0]["content"]
        self.assertEqual(parts[0].get("type"), "text")
        self.assertEqual(parts[1].get("type"), "file_data")
        self.assertEqual(parts[1].get("file_uri"), "gem-uri-1")
        self.assertEqual(parts[1].get("mime_type"), "application/pdf")

    # --- Provider format_request_body shape tests (plan item B) ---

    def test_openai_format_request_body_preserves_file_parts(self):
        """OpenAI format_request_body produces body with model and messages; file parts preserved."""
        from llm_eval.providers.openai_provider import OpenAIProvider

        messages = [{"role": "user", "content": "Summarize the attached file."}]
        file_references = [
            {"file_id": "file-oid-1", "filename": "doc.pdf", "provider": "openai"},
        ]
        formatted = ChatManager.format_messages_with_file_refs(
            messages, file_references, "openai"
        )
        provider = OpenAIProvider(api_key="sk-dummy", model="gpt-4o")
        body = provider.format_request_body(messages=formatted)
        self.assertIn("model", body)
        self.assertEqual(body["model"], "gpt-4o")
        self.assertIn("messages", body)
        msgs = body["messages"]
        self.assertEqual(len(msgs), 1)
        content = msgs[0].get("content")
        self.assertIsInstance(content, list)
        text_parts = [p for p in content if isinstance(p, dict) and p.get("type") == "text"]
        file_parts = [p for p in content if isinstance(p, dict) and p.get("type") == "file"]
        self.assertEqual(len(text_parts), 1)
        self.assertEqual(text_parts[0].get("text"), "Summarize the attached file.")
        self.assertEqual(len(file_parts), 1)
        self.assertEqual(file_parts[0].get("file", {}).get("file_id"), "file-oid-1")

    def test_anthropic_format_request_body_preserves_document_parts(self):
        """Anthropic format_request_body produces body with model, messages; document parts in user content."""
        from llm_eval.providers.claude_provider import ClaudeProvider

        messages = [{"role": "user", "content": "Review this document."}]
        file_references = [
            {"file_id": "ant-doc-1", "filename": "report.pdf", "provider": "anthropic"},
        ]
        formatted = ChatManager.format_messages_with_file_refs(
            messages, file_references, "anthropic"
        )
        provider = ClaudeProvider(api_key="dummy", model="claude-3-sonnet-20240229")
        body = provider.format_request_body(messages=formatted)
        self.assertIn("model", body)
        self.assertIn("messages", body)
        msgs = body["messages"]
        self.assertEqual(len(msgs), 1)
        content = msgs[0].get("content")
        self.assertIsInstance(content, list)
        doc_parts = [p for p in content if isinstance(p, dict) and p.get("type") == "document"]
        self.assertGreaterEqual(len(doc_parts), 1)
        self.assertEqual(doc_parts[0].get("source", {}).get("file_id"), "ant-doc-1")

    def test_gemini_format_request_body_has_contents_with_file_data(self):
        """Gemini format_request_body produces body with contents; parts include fileData."""
        from llm_eval.providers.gemini_provider import GeminiProvider

        messages = [{"role": "user", "content": "Analyze the PDF."}]
        file_references = [
            {"file_id": "gem-uri-1", "filename": "y.pdf", "file_type": "application/pdf"},
        ]
        formatted = ChatManager.format_messages_with_file_refs(
            messages, file_references, "gemini"
        )
        provider = GeminiProvider(api_key="dummy", model="gemini-1.5-flash")
        body = provider.format_request_body(messages=formatted)
        self.assertIn("contents", body)
        contents = body["contents"]
        self.assertGreaterEqual(len(contents), 1)
        parts = contents[0].get("parts", [])
        text_parts = [p for p in parts if "text" in p]
        file_parts = [p for p in parts if "fileData" in p]
        self.assertGreaterEqual(len(text_parts), 1)
        self.assertEqual(len(file_parts), 1)
        self.assertEqual(file_parts[0]["fileData"].get("fileUri"), "gem-uri-1")
        self.assertEqual(file_parts[0]["fileData"].get("mimeType"), "application/pdf")


if __name__ == "__main__":
    unittest.main()
