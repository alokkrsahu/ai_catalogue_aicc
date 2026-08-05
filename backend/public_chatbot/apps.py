import os

from django.apps import AppConfig


class PublicChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'public_chatbot'
    verbose_name = 'Public Chatbot API (retired)'

    def ready(self):
        """Register signals and, when a vector backend is configured, warm the
        knowledge service.

        This app was retired on 2026-08-05 together with its ChromaDB service.
        Warming the singleton with no server reachable made every startup wait on
        connection timeouts and logged errors on each worker reload, so the warm-up
        is now opt-in: set PUBLIC_CHATBOT_ENABLED=true (and run a ChromaDB
        instance) to restore the old behaviour. Signals are always registered so
        that admin deletes stay consistent if a backend is later reinstated.
        """
        try:
            from . import signals  # noqa: F401  (import registers the receivers)
        except Exception as exc:
            import logging
            logging.getLogger('public_chatbot').warning(
                f"public_chatbot signals not registered: {exc}"
            )

        if os.getenv('PUBLIC_CHATBOT_ENABLED', 'false').lower() != 'true':
            return

        try:
            from .services import PublicKnowledgeService
            PublicKnowledgeService.get_instance()
        except Exception as e:
            import logging
            logging.getLogger('public_chatbot').warning(
                f"ChromaDB service initialization deferred: {e}"
            )