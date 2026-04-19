"""
Centralised helper for writing `ExperimentMetric` rows from branching
executors (splitter, classifier, and future event types).

Keeps the per-call boilerplate — project lookup, sync_to_async wrapping,
swallow-and-log error handling — out of the executors so they stay
focused on the decision logic itself.

Usage:

    from .metrics_logger import log_experiment_metric
    await log_experiment_metric(
        project_id=project_id,
        experiment_type='splitter',
        metric_data={'duration_ms': 123, ...},
        configuration={'agent_name': 'Router'},
        execution_id=execution_id,
        log_tag='EXP_METRIC_SPLITTER',
    )

Never raises — on any failure the call is logged as a warning and
returns None so callers can stay on the happy path.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger('agent_orchestration')


async def log_experiment_metric(
    project_id: Optional[str],
    experiment_type: str,
    metric_data: Dict[str, Any],
    configuration: Optional[Dict[str, Any]] = None,
    execution_id: Optional[str] = None,
    evaluation_id: Optional[str] = None,
    log_tag: Optional[str] = None,
) -> Optional[int]:
    """
    Persist a single ExperimentMetric row. Always best-effort.

    Returns the created row's id, or None on any failure (including a
    missing project, missing project_id, DB error). Never raises.
    """
    if not project_id:
        return None

    tag = log_tag or f"EXP_METRIC_{experiment_type.upper()}"
    try:
        logger.info(f"{tag} | {json.dumps(metric_data, default=str)}")
    except Exception:
        # JSON-serialisation fallback — still try the DB write.
        logger.info(f"{tag} | <unserialisable payload>")

    try:
        from asgiref.sync import sync_to_async
        from users.models import IntelliDocProject, ExperimentMetric

        def save() -> Optional[int]:
            try:
                project_obj = IntelliDocProject.objects.get(project_id=project_id)
                row = ExperimentMetric.objects.create(
                    project=project_obj,
                    experiment_type=experiment_type,
                    metric_data=metric_data,
                    configuration=configuration or {},
                    execution_id=execution_id or '',
                    evaluation_id=evaluation_id or '',
                )
                return row.id
            except IntelliDocProject.DoesNotExist:
                logger.warning(
                    f"⚠️ {tag}: Project {project_id} not found — metric not persisted"
                )
                return None
            except Exception as exc:
                logger.error(f"❌ {tag}: DB write failed: {exc}")
                return None

        return await sync_to_async(save)()
    except Exception as exc:
        logger.error(f"❌ {tag}: Unexpected error: {exc}")
        return None
