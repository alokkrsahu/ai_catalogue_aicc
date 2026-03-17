# Deployment / Chat Limitations

This document describes known limitations of the deployed workflow chat (embed chat) and public chat endpoints.

## Access control (no authentication)

The deploy chat endpoints (`POST /api/workflow-deploy/{project_id}/`, stream, and submit-input) are **unauthenticated**. They are intended for public or embed use. Access control is enforced as follows:

- **Allowed origins:** The deployment CORS middleware checks each request’s `Origin` header against the project’s **allowed origins** list (configured in the Deploy UI). Only requests from an allowed origin receive CORS headers; browsers will block embed pages on other origins from reading the response.
- **Rate limiting:** Each allowed origin has a configurable rate limit (requests per minute). Requests that exceed the limit receive `429` and a `retry_after` value; the user message is still saved so it is not lost.

Direct server-to-server or tool calls (e.g. Postman, curl) that do not send `Origin` do not get CORS headers and are not blocked by the middleware; they are still subject to rate limiting. If you need to restrict non-browser callers, you would need to add an optional API key or other server-side check and document it.

## No user file upload in embed chat

The deploy chat API accepts only `user_query` and `session_id`. End-users cannot attach or upload files (e.g. a PDF) from the embed UI. File attachments in deployment come only from workflow configuration (node-level `inline_file_attachments` or project-level selected documents). Supporting end-user file upload would require extending the stream/chat API and embed HTML.

## Simulated streaming

The streaming endpoint runs the workflow to completion and then streams the full response word-by-word with a small delay. Latency is that of the full LLM completion, not true token-by-token streaming. True LLM streaming would require the workflow executor to use a streaming response API and the deployment to forward SSE chunks from the provider.

## Concurrent requests with same session_id

Two requests with the same `session_id` can run in parallel. Both load the same session, append their user message, run the workflow, and save. The last save wins, so one user message (and possibly one assistant response) can be overwritten. There is no per-session locking or append-only merge. The embed UI should disable send while a request is in flight to avoid this in normal use.
