"""
Tests for the three analytics API surfaces:

  GET /projects/<id>/experiment-metrics/
  GET /projects/<id>/analytics/
  GET /projects/<id>/recent-executions/

Focus: the new response shape and the execution_id filter introduced
for the "Workflow Performance" sub-tab.
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import (
    AgentWorkflow,
    ExperimentMetric,
    IntelliDocProject,
    User,
    WorkflowExecution,
    WorkflowExecutionStatus,
)


class AnalyticsEndpointBase(TestCase):
    """Shared fixture: a project with two WorkflowExecutions and a
    spread of ExperimentMetric rows covering every current type."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='analytics@example.com', password='x',
            is_staff=True, is_superuser=True,
        )
        self.project = IntelliDocProject.objects.create(
            name='Analytics', description='', created_by=self.user,
            template_name='', template_type='custom', instructions='',
            analysis_focus='', icon_class='', color_theme='',
        )
        self.workflow = AgentWorkflow.objects.create(
            project=self.project,
            name='WF A',
            description='',
            graph_json={},
            created_by=self.user,
        )

        # Two executions so we can verify filtering.
        now = timezone.now()
        self.execution_one = WorkflowExecution.objects.create(
            workflow=self.workflow, execution_id='exec_unit_001',
            status=WorkflowExecutionStatus.COMPLETED,
            start_time=now - timedelta(seconds=10), end_time=now,
            duration_seconds=10.0,
            executed_by=self.user,
        )
        self.execution_two = WorkflowExecution.objects.create(
            workflow=self.workflow, execution_id='exec_unit_002',
            status=WorkflowExecutionStatus.COMPLETED,
            start_time=now - timedelta(seconds=5), end_time=now,
            duration_seconds=5.0,
            executed_by=self.user,
        )

        # workflow_execution rows (one per execution, differentiated by
        # duration so sequential_vs_parallel has data to aggregate).
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='workflow_execution',
            metric_data={'duration_s': 10.0, 'parallel_batches': 0},
            configuration={'agent_count': 3, 'has_rag': False},
            execution_id='exec_unit_001',
        )
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='workflow_execution',
            metric_data={'duration_s': 5.0, 'parallel_batches': 2},
            configuration={'agent_count': 3, 'has_rag': False},
            execution_id='exec_unit_002',
        )

        # Splitter + classifier tied to exec_unit_001 only.
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='splitter',
            metric_data={
                'duration_ms': 120,
                'allocated_count': 2, 'pruned_count': 1,
                'allocated_agent_names': ['A', 'B'],
                'pruned_agent_names': ['C'],
                'overlap_allowed': False,
            },
            configuration={'agent_name': 'Router'},
            execution_id='exec_unit_001',
        )
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='classifier',
            metric_data={
                'duration_ms': 80,
                'category_name': 'finance', 'category_id': 'c1',
            },
            configuration={'agent_name': 'Gate'},
            execution_id='exec_unit_001',
        )

        # Websearch rows across tiers.
        for tier, ch in [('cold', False), ('content_hash', True), ('url_cache', True)]:
            ExperimentMetric.objects.create(
                project=self.project, experiment_type='websearch',
                metric_data={
                    'mode': 'urls', 'duration_ms': 123, 'context_length': 456,
                    'success': True, 'cache_hit': ch, 'cache_tier': tier,
                },
                configuration={'agent_name': 'A'},
                execution_id='exec_unit_002',
            )

        # Index-batch rows so cache_tier_breakdown has url-tier totals.
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='websearch_index_batch',
            metric_data={
                'n_urls': 10, 'indexed': 3, 'skipped': 7,
                'flag_alive_hits': 2, 'content_hash_hits': 4,
                'embed_cache_hits': 1, 'cold_count': 3,
                'duration_ms': 1200,
            },
            configuration={'cache_ttl': 3600},
        )

        # Summary-job rows for the health card.
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='summary_job',
            metric_data={
                'urls_queued': 5, 'summarized': 4, 'skipped': 1, 'failed': 0,
                'duration_ms': 90_000, 'status': 'ok',
                'llm_provider': 'openai', 'llm_model': 'gpt-4o-mini',
            },
        )
        ExperimentMetric.objects.create(
            project=self.project, experiment_type='summary_job',
            metric_data={
                'urls_queued': 3, 'summarized': 1, 'failed': 2,
                'duration_ms': 45_000, 'status': 'error',
                'error': 'No API key configured',
            },
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)


class RecentExecutionsEndpointTests(AnalyticsEndpointBase):
    def test_returns_both_executions_newest_first(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/recent-executions/?limit=10'
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn('executions', body)
        ids = [row['execution_id'] for row in body['executions']]
        # Newest first (exec_002 started 5s ago; exec_001 10s ago).
        self.assertEqual(ids, ['exec_unit_002', 'exec_unit_001'])

    def test_includes_summary_fields(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/recent-executions/'
        )
        self.assertEqual(resp.status_code, 200)
        row = resp.json()['executions'][0]
        for key in ('execution_id', 'workflow_id', 'workflow_name',
                    'started_at', 'duration_s', 'status',
                    'total_agents_involved', 'total_messages',
                    'executed_nodes_count'):
            self.assertIn(key, row, f'missing key: {key}')

    def test_limit_clamped(self):
        # limit=0 → clamp to 1; limit=999 → clamp to 200
        for raw, expected_max in [('0', 1), ('999', 200)]:
            resp = self.client.get(
                f'/api/projects/{self.project.project_id}/recent-executions/?limit={raw}'
            )
            self.assertEqual(resp.status_code, 200)
            # We only have 2 rows; clamping just means the backend didn't
            # choke on the boundary.
            self.assertLessEqual(len(resp.json()['executions']), expected_max)


class ExperimentMetricsFilterTests(AnalyticsEndpointBase):
    def test_project_wide_response_has_new_keys(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/experiment-metrics/'
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # splitter/classifier rows exist → the aggregate keys should be present.
        self.assertIn('splitter_stats', body)
        self.assertIn('classifier_stats', body)
        self.assertEqual(body['splitter_stats']['total_decisions'], 1)
        self.assertEqual(body['classifier_stats']['total_decisions'], 1)
        self.assertEqual(
            body['classifier_stats']['category_distribution'][0]['category_name'],
            'finance',
        )

    def test_execution_id_filter_scopes_splitter_and_classifier(self):
        # exec_unit_002 has NO splitter/classifier rows — they should disappear.
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/experiment-metrics/?execution_id=exec_unit_002'
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertNotIn('splitter_stats', body)
        self.assertNotIn('classifier_stats', body)

    def test_execution_id_filter_scopes_workflow_metrics(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/experiment-metrics/?execution_id=exec_unit_002'
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # exec_unit_002 was parallel (parallel_batches=2, duration_s=5.0)
        seq_vs_par = body.get('sequential_vs_parallel') or {}
        self.assertEqual(seq_vs_par.get('parallel_time_s'), 5.0)
        # No sequential metric for exec_unit_002 → sequential_time_s stays None.
        self.assertIsNone(seq_vs_par.get('sequential_time_s'))


class AnalyticsEndpointShapeTests(AnalyticsEndpointBase):
    def test_response_has_cache_tier_breakdown_and_summary_jobs(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/analytics/'
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn('cache_tier_breakdown', body)
        self.assertIn('summary_jobs', body)

    def test_cache_tier_breakdown_counts_calls_and_url_hits(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/analytics/'
        )
        body = resp.json()
        breakdown = body['cache_tier_breakdown']
        # 3 websearch calls, one per tier.
        self.assertEqual(breakdown['call_tier_counts'].get('cold'), 1)
        self.assertEqual(breakdown['call_tier_counts'].get('content_hash'), 1)
        self.assertEqual(breakdown['call_tier_counts'].get('url_cache'), 1)
        # Index-batch totals mirror the seeded row.
        totals = breakdown['url_tier_totals']
        self.assertEqual(totals['flag_alive_hits'], 2)
        self.assertEqual(totals['content_hash_hits'], 4)
        self.assertEqual(totals['embed_cache_hits'], 1)
        self.assertEqual(totals['cold_count'], 3)
        self.assertEqual(totals['sync_runs'], 1)

    def test_summary_jobs_counts_ok_and_error(self):
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/analytics/'
        )
        body = resp.json()
        jobs = body['summary_jobs']
        self.assertEqual(jobs['total_jobs'], 2)
        self.assertEqual(jobs['ok_count'], 1)
        self.assertEqual(jobs['error_count'], 1)

    def test_websearch_cache_hit_rate_now_populated(self):
        """Regression: the endpoint was reading a never-written type
        before commit 2; cache_hit_rate used to stay None forever."""
        resp = self.client.get(
            f'/api/projects/{self.project.project_id}/analytics/'
        )
        body = resp.json()
        ws = body['websearch']
        self.assertEqual(ws['sample_count'], 3)
        # 2 out of 3 calls had cache_hit=True in the fixture.
        self.assertAlmostEqual(ws['cache_hit_rate'], 66.7, places=0)
