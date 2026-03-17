"""
Tests for DocAware content filter expression building.
Covers folder_ and file_ filters and edge cases (empty path, escaping).
Uses filter_expr module. Run with: python manage.py test agent_orchestration.test_docaware_content_filter
"""
import unittest

from agent_orchestration.docaware.filter_expr import build_content_filter_expression_impl


class TestDocAwareContentFilter(unittest.TestCase):
    """Test content filter expression building (pure impl)."""

    def test_folder_filter_basic(self):
        """folder_ prefix produces hierarchical_path like 'path%'."""
        expr = build_content_filter_expression_impl("folder_Reports/Financial")
        self.assertIn("hierarchical_path", expr)
        self.assertIn("like", expr)
        self.assertIn("Reports", expr)
        self.assertIn("Financial", expr)
        self.assertIn("%", expr)

    def test_folder_filter_normalizes_slashes(self):
        """Folder path is normalized (strip, collapse slashes)."""
        expr = build_content_filter_expression_impl("folder_/Reports/")
        self.assertNotEqual(expr, "")
        self.assertIn("Reports", expr)

    def test_folder_filter_empty_after_normalize_returns_empty(self):
        """folder_ with only slashes/spaces returns empty."""
        self.assertEqual(build_content_filter_expression_impl("folder_/"), "")
        self.assertEqual(build_content_filter_expression_impl("folder_   "), "")

    def test_file_filter_basic(self):
        """file_ prefix produces document_id == 'id'."""
        expr = build_content_filter_expression_impl("file_doc-uuid-123")
        self.assertIn("document_id", expr)
        self.assertIn("doc-uuid-123", expr)
        self.assertIn("==", expr)

    def test_file_filter_empty_id_returns_empty(self):
        """file_ with no id (e.g. 'file_' or 'file_  ') returns empty."""
        self.assertEqual(build_content_filter_expression_impl("file_"), "")
        self.assertEqual(build_content_filter_expression_impl("file_   "), "")

    def test_file_filter_escapes_quotes(self):
        """Single quotes in document_id are escaped for Milvus."""
        expr = build_content_filter_expression_impl("file_doc'id")
        self.assertIn("''", expr)
        self.assertIn("document_id", expr)

    def test_empty_filter_returns_empty(self):
        """Empty or None content_filter returns empty string."""
        self.assertEqual(build_content_filter_expression_impl(""), "")
        self.assertEqual(build_content_filter_expression_impl(None), "")

    def test_unknown_format_returns_empty(self):
        """Unknown prefix returns empty and does not crash."""
        self.assertEqual(build_content_filter_expression_impl("unknown_xyz"), "")
