"""
Idempotent management command that clears Devanagari (Hindi/Nepali script)
text from persisted conversation state.

Two scopes:

  1. ``DeploymentSession.conversation_history`` — the live JSON-list state
     that gets replayed into the prompt on every follow-up turn. Rows
     containing Devanagari are reset to an empty history so the cookie
     remains valid but the contaminated context is gone.

  2. ``WorkflowExecution.messages_data`` / ``conversation_history`` —
     historical run records. Optional with ``--include-executions``.
     These are not active conversation state but accumulate Devanagari
     traces from prior runs of contaminated workflows.

Always dry-run by default — pass ``--apply`` to actually mutate. The dry-run
output lists every row that would be modified plus a 200-character preview
of the offending content.

Run on production after applying ``scrub_workflow_devanagari`` so the
post-fix workflows write Hindi-free history while old contaminated rows
get cleared from the data layer too.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction


HINDI = re.compile(r'[ऀ-ॿ]')


class Command(BaseCommand):
    help = (
        "Clear Devanagari content from persisted conversation history "
        "(DeploymentSession + optionally WorkflowExecution). Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually mutate the database. Default is dry-run.',
        )
        parser.add_argument(
            '--include-executions',
            action='store_true',
            help=(
                'Also scrub WorkflowExecution.messages_data and '
                'conversation_history (historical run logs). Off by default.'
            ),
        )

    def _has_devanagari(self, value):
        if isinstance(value, str):
            return bool(HINDI.search(value))
        if isinstance(value, list):
            return any(self._has_devanagari(v) for v in value)
        if isinstance(value, dict):
            return any(self._has_devanagari(v) for v in value.values())
        return False

    def handle(self, *args, **opts):
        apply_flag = opts.get('apply', False)
        include_executions = opts.get('include_executions', False)

        from agent_orchestration.models import DeploymentSession

        self.stdout.write(self.style.NOTICE(
            "Scanning DeploymentSession.conversation_history …"
        ))
        ds_hits = []
        for ds in DeploymentSession.objects.all():
            hist = ds.conversation_history or []
            if any(
                isinstance(m, dict) and self._has_devanagari(m.get('content', ''))
                for m in hist
            ):
                preview = next(
                    (m.get('content', '')[:200] for m in hist
                     if isinstance(m, dict) and self._has_devanagari(m.get('content', ''))),
                    '',
                )
                ds_hits.append((ds.id, str(ds.session_id)[:12], preview))

        self.stdout.write(f"  hits: {len(ds_hits)}")
        for h in ds_hits[:20]:
            self.stdout.write(f"    session id={h[0]} session_id={h[1]} preview={h[2]!r}")

        we_hits = []
        if include_executions:
            self.stdout.write(self.style.NOTICE(
                "Scanning WorkflowExecution …"
            ))
            try:
                from users.models import WorkflowExecution
                for we in WorkflowExecution.objects.all():
                    contaminated_field = None
                    for fname in ('messages_data', 'conversation_history'):
                        data = getattr(we, fname, None)
                        if data and self._has_devanagari(data):
                            contaminated_field = fname
                            break
                    if contaminated_field:
                        we_hits.append((we.id, str(getattr(we, 'execution_id', '?'))[:12], contaminated_field))
                self.stdout.write(f"  hits: {len(we_hits)}")
                for h in we_hits[:20]:
                    self.stdout.write(f"    execution id={h[0]} execution_id={h[1]} field={h[2]}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  WorkflowExecution scan skipped: {e}"))

        if not apply_flag:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "DRY-RUN. Re-run with --apply to actually clear these rows."
            ))
            return

        # Apply
        with transaction.atomic():
            for ds_id, _sid, _prev in ds_hits:
                ds = DeploymentSession.objects.select_for_update().get(id=ds_id)
                ds.conversation_history = []
                ds.message_count = 0
                ds.save(update_fields=['conversation_history', 'message_count'])
            if include_executions and we_hits:
                from users.models import WorkflowExecution
                for we_id, _eid, fname in we_hits:
                    we = WorkflowExecution.objects.select_for_update().get(id=we_id)
                    setattr(we, fname, [] if isinstance(getattr(we, fname, None), list) else '')
                    we.save(update_fields=[fname])

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Applied. Cleared {len(ds_hits)} session row(s)"
            + (f" and {len(we_hits)} execution row(s)." if include_executions else ".")
        ))
