"""
Django AppConfig for agent_orchestration.

Pre-warms the SentenceTransformer embedding model on server startup so the
first websearch / DocAware request doesn't pay the 2-5s lazy-load cost.

Gate: env var WEBSEARCH_PREWARM (default "1"). Set to "0" for short-lived
management commands, tests, or migrations where warming up is wasteful.
"""
import logging
import os
import sys
import threading

from django.apps import AppConfig

logger = logging.getLogger('agent_orchestration')


def _prewarm_embedding_model() -> None:
    """Load the embedding model and run one dummy encode. Runs in a background thread."""
    try:
        from .docaware.embedding_service import DocAwareEmbeddingService
        svc = DocAwareEmbeddingService()
        svc.encode_query("warmup")
        logger.info("✅ PREWARM: Embedding model ready (SentenceTransformer warmed)")
    except Exception as e:
        # Non-fatal: first real request will re-attempt via the lazy-load path.
        logger.warning(f"⚠️ PREWARM: Embedding model warm-up failed (will retry lazily): {e}")


class AgentOrchestrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agent_orchestration'

    def ready(self) -> None:
        # Skip warm-up for short-lived processes — management commands,
        # migrations, tests, and the autoreload parent process don't benefit.
        if os.environ.get('WEBSEARCH_PREWARM', '1') != '1':
            return

        argv_joined = ' '.join(sys.argv or [])
        short_lived = any(cmd in argv_joined for cmd in (
            'makemigrations', 'migrate', 'collectstatic', 'shell', 'test',
            'check', 'showmigrations', 'createsuperuser',
        ))
        if short_lived:
            return

        # Django's autoreloader spawns a child for the actual server — only
        # warm up in the child to avoid double work.
        if os.environ.get('RUN_MAIN') != 'true' and '--noreload' not in argv_joined:
            # On first (parent) invocation with the autoreloader, skip.
            # The child will set RUN_MAIN=true and run this again.
            is_runserver = 'runserver' in argv_joined
            if is_runserver:
                return

        threading.Thread(
            target=_prewarm_embedding_model,
            name='websearch-prewarm',
            daemon=True,
        ).start()
