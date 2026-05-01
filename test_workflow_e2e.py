#!/usr/bin/env python3
"""
End-to-end test for the DAE AI Tools workflow.
Tests both the in-app path (JWT auth) and the public URL path (password auth).

Usage:
    python test_workflow_e2e.py <admin_email> <admin_password> <public_url_password>
"""
import sys
import json
import time
import requests

BASE_URL = "http://localhost"
PROJECT_ID = "318be11f-58a2-4343-bd23-8f41da859079"
TEST_PDF = "/home/alokkrsahu/ai_catalogue/backend/media/projects/627555d3-e8c7-44a5-bceb-a324aba7513a/documents/630b374b-1ad6-4357-8a41-cd6a981fc880_OccuTriage_Camera_Ready.pdf"
TEST_MESSAGE = "What are the main compliance concerns identified in this document? Please search the document for specific sections."

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
INFO = "\033[94m→\033[0m"


def step(label):
    print(f"\n{INFO} {label}")


def ok(msg):
    print(f"  {PASS} {msg}")


def fail(msg):
    print(f"  {FAIL} {msg}")
    sys.exit(1)


def stream_response(url, headers, payload, pdf_path, session_id):
    """Upload file, then POST to stream endpoint and collect SSE events."""
    # Upload file
    step("Uploading PDF...")
    with open(pdf_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/workflow-deploy/{PROJECT_ID}/upload-file/",
            headers=headers,
            files={"file": (pdf_path.split("/")[-1], f, "application/pdf")},
            data={"session_id": session_id},
        )
    if r.status_code not in (200, 201):
        fail(f"File upload failed: {r.status_code} — {r.text[:200]}")
    ok(f"File uploaded (status {r.status_code})")

    # Stream the workflow
    step("Streaming workflow execution...")
    payload["session_id"] = session_id
    start = time.time()

    with requests.post(
        f"{BASE_URL}/api/workflow-deploy/{PROJECT_ID}/stream/",
        headers={**headers, "Accept": "text/event-stream"},
        json=payload,
        stream=True,
        timeout=300,
    ) as r:
        if r.status_code != 200:
            fail(f"Stream POST failed: {r.status_code} — {r.text[:200]}")

        events = []
        for line in r.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8") if isinstance(line, bytes) else line
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    events.append(ev)
                    etype = ev.get("type", "?")
                    if etype == "content":
                        pass  # streaming chunks, skip printing
                    elif etype == "done":
                        elapsed = round(time.time() - start, 1)
                        ok(f"Stream complete in {elapsed}s — {len(events)} events total")
                    elif etype == "error":
                        fail(f"Workflow error event: {ev.get('error', ev)}")
                    elif etype in ("node_start", "node_complete", "status"):
                        print(f"    [{etype}] {ev.get('node_name', ev.get('message', ''))}")
                except json.JSONDecodeError:
                    pass

    content_events = [e for e in events if e.get("type") == "content"]
    done_events = [e for e in events if e.get("type") == "done"]
    error_events = [e for e in events if e.get("type") == "error"]

    if error_events:
        fail(f"Got error event: {error_events[0].get('error')}")
    if not content_events and not done_events:
        fail("No content or done events received — likely silent failure")

    total_chars = sum(len(e.get("content", "")) for e in content_events)
    ok(f"Received {total_chars} chars of content across {len(content_events)} chunks")
    return events


# ─── IN-APP TEST ────────────────────────────────────────────────────────────

def test_in_app(admin_email, admin_password):
    print("\n" + "="*60)
    print("  TEST 1: IN-APP (JWT auth)")
    print("="*60)

    step("Authenticating as admin...")
    r = requests.post(
        f"{BASE_URL}/api/token/",
        json={"email": admin_email, "password": admin_password},
    )
    if r.status_code != 200:
        fail(f"Login failed: {r.status_code} — {r.text[:200]}")
    token = r.json().get("access")
    ok(f"JWT token obtained")

    headers = {"Authorization": f"Bearer {token}"}
    session_id = f"test_inapp_{int(time.time())}"

    payload = {
        "message": TEST_MESSAGE,
        "conversation_history": [],
    }

    events = stream_response(BASE_URL, headers, payload, TEST_PDF, session_id)
    print(f"\n  {PASS} IN-APP TEST PASSED")
    return events


# ─── PUBLIC URL TEST ─────────────────────────────────────────────────────────

def test_public_url(public_password):
    print("\n" + "="*60)
    print("  TEST 2: PUBLIC URL (password auth)")
    print("="*60)

    step("Authenticating via public-auth endpoint...")
    r = requests.post(
        f"{BASE_URL}/api/workflow-deploy/{PROJECT_ID}/public-auth/",
        json={"password": public_password},
    )
    if r.status_code != 200:
        fail(f"Public auth failed: {r.status_code} — {r.text[:200]}")

    # Extract cookie from response
    cookies = r.cookies
    ok(f"Public auth OK — cookie set: {list(cookies.keys())}")

    session_id = f"test_public_{int(time.time())}"
    headers = {}

    # Use session cookie for subsequent requests
    s = requests.Session()
    s.cookies.update(cookies)

    step("Uploading PDF via public session...")
    with open(TEST_PDF, "rb") as f:
        r = s.post(
            f"{BASE_URL}/api/workflow-deploy/{PROJECT_ID}/upload-file/",
            files={"file": (TEST_PDF.split("/")[-1], f, "application/pdf")},
            data={"session_id": session_id},
        )
    if r.status_code not in (200, 201):
        fail(f"File upload failed: {r.status_code} — {r.text[:200]}")
    ok(f"File uploaded (status {r.status_code})")

    step("Streaming workflow execution via public URL...")
    payload = {
        "message": TEST_MESSAGE,
        "session_id": session_id,
        "conversation_history": [],
    }

    start = time.time()
    events = []
    with s.post(
        f"{BASE_URL}/api/workflow-deploy/{PROJECT_ID}/stream/",
        headers={"Accept": "text/event-stream"},
        json=payload,
        stream=True,
        timeout=300,
    ) as r:
        if r.status_code != 200:
            fail(f"Stream POST failed: {r.status_code} — {r.text[:200]}")

        for line in r.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8") if isinstance(line, bytes) else line
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    events.append(ev)
                    etype = ev.get("type", "?")
                    if etype == "done":
                        elapsed = round(time.time() - start, 1)
                        ok(f"Stream complete in {elapsed}s — {len(events)} events")
                    elif etype == "error":
                        fail(f"Workflow error event: {ev.get('error', ev)}")
                    elif etype in ("node_start", "node_complete", "status"):
                        print(f"    [{etype}] {ev.get('node_name', ev.get('message', ''))}")
                except json.JSONDecodeError:
                    pass

    content_events = [e for e in events if e.get("type") == "content"]
    error_events = [e for e in events if e.get("type") == "error"]

    if error_events:
        fail(f"Got error event: {error_events[0].get('error')}")
    if not content_events:
        fail("No content received")

    total_chars = sum(len(e.get("content", "")) for e in content_events)
    ok(f"Received {total_chars} chars of content")

    print(f"\n  {PASS} PUBLIC URL TEST PASSED")
    return events


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <admin_email> <admin_password> <public_url_password>")
        sys.exit(1)

    admin_email, admin_password, public_password = sys.argv[1], sys.argv[2], sys.argv[3]

    test_in_app(admin_email, admin_password)
    test_public_url(public_password)

    print("\n" + "="*60)
    print("  ALL TESTS PASSED")
    print("="*60 + "\n")
