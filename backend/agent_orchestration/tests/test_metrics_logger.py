"""
Tests for agent_orchestration.metrics_logger — the tiny best-effort
helper used by splitter, classifier, websearch_index_batch, etc.
"""
import asyncio

from django.test import TransactionTestCase

from users.models import User, IntelliDocProject, ExperimentMetric
from agent_orchestration.metrics_logger import log_experiment_metric


# TransactionTestCase (not TestCase): the helper writes via sync_to_async
# which runs on a worker thread, and the default TestCase transaction
# isn't visible there — fixture rows would look missing to `save()`.
class MetricsLoggerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='metrics@example.com', password='x',
            is_staff=True, is_superuser=True,
        )
        self.project = IntelliDocProject.objects.create(
            name='Metrics Test', description='', created_by=self.user,
            template_name='', template_type='custom', instructions='',
            analysis_focus='', icon_class='', color_theme='',
        )

    def _run(self, coro):
        return asyncio.run(coro)

    def test_writes_row_with_execution_id(self):
        row_id = self._run(log_experiment_metric(
            project_id=str(self.project.project_id),
            experiment_type='splitter',
            metric_data={'duration_ms': 42, 'allocated_count': 3},
            configuration={'agent_name': 'Router'},
            execution_id='exec_test_001',
        ))
        self.assertIsNotNone(row_id)
        row = ExperimentMetric.objects.get(id=row_id)
        self.assertEqual(row.experiment_type, 'splitter')
        self.assertEqual(row.execution_id, 'exec_test_001')
        self.assertEqual(row.metric_data['duration_ms'], 42)
        self.assertEqual(row.configuration['agent_name'], 'Router')

    def test_missing_project_returns_none_but_does_not_raise(self):
        row_id = self._run(log_experiment_metric(
            project_id='00000000-0000-0000-0000-000000000000',
            experiment_type='splitter',
            metric_data={'x': 1},
        ))
        self.assertIsNone(row_id)

    def test_missing_project_id_is_noop(self):
        row_id = self._run(log_experiment_metric(
            project_id=None,
            experiment_type='splitter',
            metric_data={'x': 1},
        ))
        self.assertIsNone(row_id)

    def test_defaults_empty_configuration_and_execution_id(self):
        row_id = self._run(log_experiment_metric(
            project_id=str(self.project.project_id),
            experiment_type='classifier',
            metric_data={'duration_ms': 10},
        ))
        self.assertIsNotNone(row_id)
        row = ExperimentMetric.objects.get(id=row_id)
        self.assertEqual(row.configuration, {})
        self.assertEqual(row.execution_id, '')
        self.assertEqual(row.evaluation_id, '')
