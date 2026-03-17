"""
Tests for message_converter.parse_conversation_history_to_messages.
Deployment chat uses "User: ..." and "Assistant: ..." lines; these tests assert correct role mapping.
"""
import unittest

from .message_converter import parse_conversation_history_to_messages


class TestParseConversationHistoryToMessages(unittest.TestCase):
    """Test deployment-style 'User:' / 'Assistant:' conversation format."""

    def test_user_assistant_format_roles(self):
        """Deployment builds 'User: ...' and 'Assistant: ...'; parser should map to roles user and assistant."""
        history = "User: What is the capital of France?\nAssistant: The capital of France is Paris."
        messages = parse_conversation_history_to_messages(history, include_system=False)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "What is the capital of France?")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "The capital of France is Paris.")

    def test_user_only(self):
        """Single User: line maps to one user message."""
        history = "User: Hello"
        messages = parse_conversation_history_to_messages(history, include_system=False)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Hello")

    def test_multiple_turns(self):
        """Multiple User/Assistant turns preserve order and roles."""
        history = (
            "User: First question\n"
            "Assistant: First answer\n"
            "User: Second question\n"
            "Assistant: Second answer"
        )
        messages = parse_conversation_history_to_messages(history, include_system=False)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "First question")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "First answer")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[2]["content"], "Second question")
        self.assertEqual(messages[3]["role"], "assistant")
        self.assertEqual(messages[3]["content"], "Second answer")

    def test_with_system_message(self):
        """Optional system message is prepended when include_system=True."""
        history = "User: Hi\nAssistant: Hello"
        messages = parse_conversation_history_to_messages(
            history, system_message="You are helpful.", include_system=True
        )
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "You are helpful.")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "Hi")
        self.assertEqual(messages[2]["role"], "assistant")
        self.assertEqual(messages[2]["content"], "Hello")
