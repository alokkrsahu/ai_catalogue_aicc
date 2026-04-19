"""
Tests for the detached / 202-Accepted contract of summarize_urls.

Covers the three paths the frontend depends on:
  1. Happy path  → 202 Accepted + Redis flag set + thread dispatched.
  2. No work     → 200 OK + status=noop (all URLs already have summaries,
                   force=false).
  3. Double-start → 409 Conflict (flag already alive).
"""
import threading
from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import User, IntelliDocProject, WebSearchUrlSummary
from agent_orchestration.deployment_views import DeploymentViewSet
from agent_orchestration.websearch import WebSearchCacheService


@override_settings(WEBSEARCH_CONFIG={'MAX_URLS_PER_AGENT': 50})
class SummarizeUrlsDetachTests(TestCase):
    """The view must detach work onto a thread, never block the caller."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='detach-test@example.com',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.project = IntelliDocProject.objects.create(
            name='Detach Test',
            description='',
            created_by=self.user,
            template_name='',
            template_type='custom',
            instructions='',
            analysis_focus='',
            icon_class='',
            color_theme='',
        )
        self.factory = APIRequestFactory()
        self.view = DeploymentViewSet.as_view({'post': 'summarize_urls'})
        self.cache_svc = WebSearchCacheService()
        self.flag_key = (
            f"{self.cache_svc.SUMMARY_GEN_PREFIX}"
            f"{str(self.project.project_id).replace('-', '_')}"
        )

    def _post(self, urls, force=False):
        req = self.factory.post(
            f'/api/agent-orchestration/projects/{self.project.project_id}/summarize-urls/',
            {'urls': urls, 'llm_provider': 'openai', 'force': force},
            format='json',
        )
        force_authenticate(req, user=self.user)
        return self.view(req, project_id=str(self.project.project_id))

    _UNSET = object()

    def _stub_llm_manager(self, provider=_UNSET):
        """Return a patch context that makes LLMProviderManager hand back a stub.

        Pass `provider=None` to exercise the "no API key" 400 path.
        """
        if provider is self._UNSET:
            provider = MagicMock()  # default: non-None → view treats as valid
        async def fake_get_llm_provider(agent_config, project=None):
            return provider
        mgr_cls = MagicMock()
        mgr_cls.return_value.get_llm_provider = fake_get_llm_provider
        return patch('agent_orchestration.llm_provider_manager.LLMProviderManager', mgr_cls)

    def test_happy_path_returns_202_and_dispatches_thread(self):
        started = threading.Event()

        # Replace the heavy work with a no-op that signals it ran.
        async def fake_summarize(*args, **kwargs):
            started.set()
            return {'summarized': 1, 'skipped': 0, 'failed': 0, 'results': []}

        with self._stub_llm_manager(), \
             patch(
                 'agent_orchestration.websearch_handler.WebSearchHandler.summarize_urls_for_project',
                 side_effect=fake_summarize,
             ):
            resp = self._post(['https://a.example/'])

        self.assertEqual(resp.status_code, 202)
        body = resp.data
        self.assertEqual(body['status'], 'started')
        self.assertEqual(body['urls_queued'], 1)

        # Flag was set; thread eventually runs and clears it.
        self.assertTrue(started.wait(timeout=5), 'background thread never ran')
        # Give the thread's `finally` a moment to clear the flag.
        for _ in range(50):
            if not cache.get(self.flag_key):
                break
            threading.Event().wait(0.05)
        self.assertIsNone(cache.get(self.flag_key), 'flag should be cleared after thread completes')

    def test_noop_when_all_urls_already_have_summaries(self):
        WebSearchUrlSummary.objects.create(
            project=self.project,
            url='https://a.example/',
            short_summary='existing',
            long_summary='',
            llm_provider='openai',
        )

        with self._stub_llm_manager():
            resp = self._post(['https://a.example/'], force=False)

        # force=false + all existing → early 200 OK, no thread, no flag set.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'noop')
        self.assertIsNone(cache.get(self.flag_key))

    def test_double_start_returns_409(self):
        # Pre-set the flag to simulate a concurrent job.
        cache.set(self.flag_key, True, timeout=900)

        with self._stub_llm_manager():
            resp = self._post(['https://a.example/'], force=True)

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['error'], 'generation_in_progress')

    def test_missing_llm_provider_returns_400_without_thread(self):
        # LLMProviderManager returns None → 400 before any thread spawn.
        with self._stub_llm_manager(provider=None):
            resp = self._post(['https://a.example/'], force=True)

        self.assertEqual(resp.status_code, 400)
        self.assertIn('No openai API key', resp.data['error'])
        self.assertIsNone(cache.get(self.flag_key))
