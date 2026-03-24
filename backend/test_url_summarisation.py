"""
Integration test for the URL summarisation feature.

Run from within the backend container:
  docker exec -it ai_catalogue_backend python test_url_summarisation.py

Requires an existing project with a valid OpenAI API key configured.
Edit PROJECT_ID, WORKFLOW_ID, and AUTH_TOKEN below before running.

How to get AUTH_TOKEN:
  In the browser, open DevTools → Application → Local Storage → auth → token
How to get PROJECT_ID / WORKFLOW_ID:
  Copy from the URL bar while viewing a project/workflow.
"""
import os
import sys
import django
import json
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/app')
django.setup()

from users.models import IntelliDocProject, AgentWorkflow, WebSearchUrlSummary

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURE BEFORE RUNNING
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ID  = 'YOUR-PROJECT-UUID-HERE'   # paste from URL bar
WORKFLOW_ID = 'YOUR-WORKFLOW-UUID-HERE'  # must have a URL-mode node
BASE_URL    = 'http://localhost:8000'    # adjust if needed
AUTH_TOKEN  = 'YOUR-JWT-TOKEN-HERE'     # from localStorage → auth → token
# ─────────────────────────────────────────────────────────────────────────────

TEST_URLS = [
    'https://httpbin.org/html',
    'https://httpbin.org/json',
]
EXTRA_URL = 'https://httpbin.org/xml'
ALL_TEST_URLS = TEST_URLS + [EXTRA_URL]

HEADERS = {'Authorization': f'Bearer {AUTH_TOKEN}', 'Content-Type': 'application/json'}


def section(title: str):
    print(f'\n{"=" * 60}\n{title}\n{"=" * 60}')


def summarise(urls, force=False):
    r = requests.post(
        f'{BASE_URL}/api/agent-orchestration/projects/{PROJECT_ID}/summarize-urls/',
        headers=HEADERS,
        json={
            'urls': urls,
            'llm_provider': 'openai',
            'llm_model': 'gpt-4o-mini',
            'force': force,
        },
    )
    assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'
    return r.json()


# ─── TEST 1: Summarise two fresh URLs ────────────────────────────────────────
section('TEST 1 — Summarise two fresh URLs')
WebSearchUrlSummary.objects.filter(
    project__project_id=PROJECT_ID, url__in=ALL_TEST_URLS
).delete()
print('Cleared any pre-existing summaries for test URLs.')

data = summarise(TEST_URLS, force=False)
print(f'Response: {json.dumps(data, indent=2)}')
assert data['summarized'] == 2, f'Expected 2 summarised, got {data["summarized"]}'
assert data['failed'] == 0, f'Expected 0 failed, got {data["failed"]}'
print('✅ TEST 1 PASSED')


# ─── TEST 2: No duplicate on second call (force=False) ───────────────────────
section('TEST 2 — No duplicate on second call (force=False)')
data = summarise(TEST_URLS, force=False)
print(f'Response: {json.dumps(data, indent=2)}')
assert data['summarized'] == 0, f'Expected 0 summarised (all skipped), got {data["summarized"]}'
assert data.get('skipped') == 2, f'Expected skipped=2, got {data.get("skipped")}'
print('✅ TEST 2 PASSED')


# ─── TEST 3: Adding a 3rd URL only summarises the new one ────────────────────
section('TEST 3 — Add a 3rd URL, only it gets summarised')
WebSearchUrlSummary.objects.filter(
    project__project_id=PROJECT_ID, url=EXTRA_URL
).delete()

data = summarise(ALL_TEST_URLS, force=False)
print(f'Response: {json.dumps(data, indent=2)}')
assert data['summarized'] == 1, f'Expected 1 summarised (only EXTRA_URL), got {data["summarized"]}'
assert data.get('skipped') == 2, f'Expected skipped=2, got {data.get("skipped")}'
print('✅ TEST 3 PASSED')


# ─── TEST 4: DB has exactly 3 rows ───────────────────────────────────────────
section('TEST 4 — Database has exactly 3 summary rows')
rows = WebSearchUrlSummary.objects.filter(
    project__project_id=PROJECT_ID, url__in=ALL_TEST_URLS
)
print(f'Found {rows.count()} rows:')
for row in rows:
    print(f'  {row.url[:60]}')
    print(f'    short_summary: {row.short_summary[:100]}...')
assert rows.count() == 3, f'Expected 3 rows, got {rows.count()}'
print('✅ TEST 4 PASSED')


# ─── TEST 5: Orphan cleanup on workflow save ──────────────────────────────────
section('TEST 5 — Orphan cleanup when URL removed from workflow save')
project = IntelliDocProject.objects.get(project_id=PROJECT_ID)
pre_count = WebSearchUrlSummary.objects.filter(project=project).count()
print(f'Pre-cleanup summary count for project: {pre_count}')

workflow = AgentWorkflow.objects.get(workflow_id=WORKFLOW_ID)
graph = workflow.graph_json or {'nodes': [], 'edges': []}

# Find the URL-mode node and remove EXTRA_URL from its list
patched = False
for node in graph.get('nodes', []):
    data = node.get('data', {})
    if data.get('web_search_mode') == 'urls':
        original = list(data.get('web_search_urls', []))
        # Ensure all 3 test URLs are in the node before patching
        data['web_search_urls'] = list(set(original) | set(ALL_TEST_URLS))
        workflow.graph_json = graph
        workflow.save()
        print(f'  Set node {node["id"]} to {len(data["web_search_urls"])} URLs (added test URLs)')
        # Now save again with only TEST_URLS (removing EXTRA_URL)
        data['web_search_urls'] = TEST_URLS
        patched = True
        break

if not patched:
    print('  WARNING: No URL-mode node found — creating inline test via API patch')

r = requests.patch(
    f'{BASE_URL}/api/projects/{PROJECT_ID}/workflows/{WORKFLOW_ID}/',
    headers=HEADERS,
    json={'graph_json': graph, 'status': 'draft'},
)
assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'

post_count = WebSearchUrlSummary.objects.filter(project=project).count()
extra_exists = WebSearchUrlSummary.objects.filter(project=project, url=EXTRA_URL).exists()
print(f'Post-cleanup summary count: {post_count}')
assert not extra_exists, 'EXTRA_URL summary should have been deleted but still exists!'
assert post_count < pre_count, f'Expected count to decrease: {pre_count} → {post_count}'
print('✅ TEST 5 PASSED')


# ─── TEST 6: Tool-building uses summaries ─────────────────────────────────────
section('TEST 6 — build_websearch_url_tools_with_summaries returns per-URL tools')
import asyncio
from agent_orchestration.websearch_handler import WebSearchHandler

# Ensure TEST_URLS have summaries
WebSearchUrlSummary.objects.filter(project=project, url__in=TEST_URLS).delete()
summarise(TEST_URLS, force=False)

handler = WebSearchHandler()
fake_node = {
    'data': {
        'web_search_enabled': True,
        'web_search_mode': 'urls',
        'web_search_urls': TEST_URLS,
    }
}

tools, url_tool_map = asyncio.run(
    handler.build_websearch_url_tools_with_summaries(fake_node, PROJECT_ID)
)
print(f'Built {len(tools)} tools:')
for t in tools:
    fn = t['function']
    print(f'  {fn["name"]}: {fn["description"][:80]}...')
    assert fn['name'].startswith('wsurl_'), f'Expected wsurl_ prefix, got {fn["name"]}'
    assert fn['description'], 'Description should not be empty'

assert len(tools) == len(TEST_URLS), f'Expected {len(TEST_URLS)} tools, got {len(tools)}'
assert set(url_tool_map.values()) == set(TEST_URLS), 'url_tool_map URLs mismatch'
print('✅ TEST 6 PASSED')


# ─── TEST 7: Fallback when no summaries ──────────────────────────────────────
section('TEST 7 — Fallback to legacy single tool when no summaries exist')
WebSearchUrlSummary.objects.filter(project=project, url__in=TEST_URLS).delete()

tools, url_tool_map = asyncio.run(
    handler.build_websearch_url_tools_with_summaries(fake_node, PROJECT_ID)
)
print(f'Built {len(tools)} tools (should be 0 → caller falls back to legacy single tool)')
assert len(tools) == 0, f'Expected 0 tools (fallback path), got {len(tools)}'
assert url_tool_map == {}, 'Expected empty url_tool_map'
print('✅ TEST 7 PASSED')


# ─────────────────────────────────────────────────────────────────────────────
print('\n' + '=' * 60)
print('ALL 7 TESTS PASSED ✅')
print('=' * 60)
print('\nManual UI checks to complete separately:')
print('  1. Add URLs in URL-mode node → wait 3s → check Network tab for POST to summarize-urls')
print('  2. Remove a URL → check: docker logs ai_catalogue_backend | grep "URL SUMMARY CLEANUP"')
print('  3. Run the workflow → check logs for "WEBSEARCH URL TOOLS: Built N per-URL tools"')
print('  4. Confirm LLM calls wsurl_<hash> tool (not web_search) in logs')
