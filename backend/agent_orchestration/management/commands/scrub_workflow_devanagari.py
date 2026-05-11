"""
Idempotent management command that finds and removes Devanagari (Hindi/Nepali
script) text from ``AgentWorkflow.graph_json`` fields.

Two contamination patterns are handled:

  1. **Start Node prompt** — multilingual few-shot conversations that
     explicitly demonstrate Hindi responses (e.g., "User: in hindi pleaes /
     Assistant: <Devanagari>"). These prime every downstream LLM call to
     produce non-English output. Surgically replaced with a neutral
     English greeting.

  2. **Other string fields** (system_message, instructions, category
     descriptions, etc.) — single Devanagari words embedded mid-prompt,
     usually copy-paste typos like "Priority स्तर". Stripped in place;
     adjacent double-spaces collapsed.

Always dry-run by default — the command lists every workflow field that
would change with a before/after preview. Pass ``--apply`` to actually
mutate the rows inside a single transaction.

Run on production after deploying the LANGUAGE-rule code fixes. Pair with
``scrub_devanagari_sessions`` to also clear the downstream conversation
history that accumulated while the contaminated workflows were running.
"""
import copy
import re

from django.core.management.base import BaseCommand
from django.db import transaction


HINDI = re.compile(r'[ऀ-ॿ]')


def _walk_strings(obj, path=''):
    """Yield (path, str) for every string nested anywhere inside obj."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f'{path}.{k}' if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f'{path}[{i}]')


def _set_path(obj, dotted_path, new_value):
    """Set the value at a dotted/bracketed path inside obj (in-place)."""
    parts = re.split(r'\.|\[|\]', dotted_path)
    parts = [p for p in parts if p]
    cursor = obj
    for p in parts[:-1]:
        cursor = cursor[int(p)] if p.isdigit() else cursor[p]
    last = parts[-1]
    if last.isdigit():
        cursor[int(last)] = new_value
    else:
        cursor[last] = new_value


def _scrub(path: str, value: str) -> str:
    """Compute the cleaned replacement value for one contaminated field."""
    if path.endswith('.prompt'):
        # Start Node prompts are seed conversations — replace wholesale with
        # a neutral English greeting rather than trying to surgically extract
        # the few-shot.
        return 'Hi! I am your AI assistant.'
    # Otherwise, strip Devanagari characters in place; collapse the
    # double-spaces that often result from mid-word removal.
    cleaned = HINDI.sub('', value)
    cleaned = re.sub(r' {2,}', ' ', cleaned).strip()
    return cleaned


class Command(BaseCommand):
    help = (
        "Find and remove Devanagari (Hindi/Nepali script) from "
        "AgentWorkflow.graph_json. Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually mutate the database. Default is dry-run.',
        )
        parser.add_argument(
            '--workflow-id',
            type=int,
            default=None,
            help='Restrict to a single workflow id.',
        )

    def handle(self, *args, **opts):
        from users.models import AgentWorkflow

        apply_flag = opts.get('apply', False)
        workflow_id = opts.get('workflow_id')

        qs = AgentWorkflow.objects.all()
        if workflow_id is not None:
            qs = qs.filter(id=workflow_id)

        hits = []
        for w in qs:
            g = w.graph_json or {}
            if not isinstance(g, dict):
                continue
            for path, val in _walk_strings(g):
                if HINDI.search(val):
                    hits.append({
                        'workflow_id': w.id,
                        'workflow_name': w.name,
                        'path': path,
                        'before': val,
                        'after': _scrub(path, val),
                    })

        self.stdout.write(self.style.NOTICE(
            f"Found {len(hits)} Devanagari-bearing workflow field(s)."
        ))
        for h in hits:
            self.stdout.write("")
            self.stdout.write(
                f"  workflow id={h['workflow_id']} name={h['workflow_name']!r}"
            )
            self.stdout.write(f"  path:   {h['path']}")
            self.stdout.write(f"  before: {h['before']!r}")
            self.stdout.write(f"  after:  {h['after']!r}")

        if not hits:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ No contamination found. Nothing to do."
            ))
            return

        if not apply_flag:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "DRY-RUN. Re-run with --apply to actually mutate."
            ))
            return

        # Apply in a single transaction; group hits by workflow to minimise saves.
        per_wf = {}
        for h in hits:
            per_wf.setdefault(h['workflow_id'], []).append(h)

        with transaction.atomic():
            for wf_id, wf_hits in per_wf.items():
                wf = AgentWorkflow.objects.select_for_update().get(id=wf_id)
                g2 = copy.deepcopy(wf.graph_json or {})
                for h in wf_hits:
                    _set_path(g2, h['path'], h['after'])
                wf.graph_json = g2
                wf.save(update_fields=['graph_json'])
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ workflow id={wf_id} — updated "
                    f"{len(wf_hits)} field(s)"
                ))

        # Verify
        self.stdout.write("\nRe-scanning after apply …")
        remaining = []
        for w in AgentWorkflow.objects.all():
            g = w.graph_json or {}
            if not isinstance(g, dict):
                continue
            for path, val in _walk_strings(g):
                if HINDI.search(val):
                    remaining.append((w.id, w.name, path))

        if remaining:
            self.stdout.write(self.style.ERROR(
                f"⚠️  {len(remaining)} field(s) still contain Devanagari:"
            ))
            for r in remaining:
                self.stdout.write(f"    {r}")
        else:
            self.stdout.write(self.style.SUCCESS(
                "✅ Verification clean: no Devanagari remains in any AgentWorkflow.graph_json."
            ))
