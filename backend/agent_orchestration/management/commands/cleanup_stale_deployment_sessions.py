"""
Idempotent cleanup of stale ``DeploymentSession`` rows.

By default, sessions with ``last_activity`` older than the cutoff (default
30 days) are flipped to ``is_active=False`` and their ``conversation_history``
is trimmed to keep at most ``--keep-last`` recent messages (default 0 — full
trim). The session row is preserved so analytics and audit queries can still
reference it.

Use ``--purge`` to delete inactive rows entirely instead of soft-flipping.

Run this on a schedule (cron / Celery beat) — daily is a reasonable cadence.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Soft-deactivate (or purge) DeploymentSession rows older than N days."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=30,
            help='Sessions inactive >= this many days are eligible (default 30).',
        )
        parser.add_argument(
            '--keep-last', type=int, default=0,
            help='Keep N most-recent messages in conversation_history per soft-deactivated session (default 0 — wipe).',
        )
        parser.add_argument(
            '--purge', action='store_true',
            help='Delete eligible rows instead of soft-deactivating them.',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually mutate the database. Default is dry-run.',
        )

    def handle(self, *args, **opts):
        from agent_orchestration.models import DeploymentSession

        days = opts['days']
        keep_last = opts['keep_last']
        purge = opts['purge']
        apply_flag = opts['apply']

        cutoff = timezone.now() - timedelta(days=days)
        # Eligible = last_activity older than cutoff (or null) and currently is_active.
        # We don't touch is_active=False rows so re-runs are idempotent.
        qs = DeploymentSession.objects.filter(is_active=True).filter(
            last_activity__lt=cutoff
        ) | DeploymentSession.objects.filter(is_active=True, last_activity__isnull=True)

        eligible = list(qs.order_by('id'))
        self.stdout.write(self.style.NOTICE(
            f"Eligible sessions (>={days}d inactive, currently is_active=True): "
            f"{len(eligible)}"
        ))
        for ds in eligible[:20]:
            self.stdout.write(
                f"  id={ds.id} session={str(ds.session_id)[:12]} "
                f"last_activity={ds.last_activity} msgs={ds.message_count}"
            )
        if len(eligible) > 20:
            self.stdout.write(f"  … and {len(eligible) - 20} more")

        if not apply_flag:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"DRY-RUN. Re-run with --apply to actually "
                f"{'purge' if purge else 'soft-deactivate'}."
            ))
            return

        if not eligible:
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        with transaction.atomic():
            if purge:
                ids = [ds.id for ds in eligible]
                deleted, _ = DeploymentSession.objects.filter(id__in=ids).delete()
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Purged {deleted} session row(s) (cascade may include child rows)."
                ))
                return

            for ds in eligible:
                ds = DeploymentSession.objects.select_for_update().get(id=ds.id)
                if keep_last > 0 and ds.conversation_history:
                    ds.conversation_history = ds.conversation_history[-keep_last:]
                else:
                    ds.conversation_history = []
                ds.message_count = len(ds.conversation_history) if isinstance(ds.conversation_history, list) else 0
                ds.is_active = False
                ds.save(update_fields=['conversation_history', 'message_count', 'is_active'])

            self.stdout.write(self.style.SUCCESS(
                f"✅ Soft-deactivated {len(eligible)} session row(s) "
                f"(keep_last={keep_last})."
            ))
