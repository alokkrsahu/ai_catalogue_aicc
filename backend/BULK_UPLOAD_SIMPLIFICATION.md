# Public Knowledge Base — Bulk Document Upload

**Module:** `backend/public_chatbot/`
**Surface:** Django admin only — there is no REST endpoint for this.

This file describes how bulk upload works today. It previously contained a before/after changelog of a 2025 refactor, which had drifted from the code (among other things it stated that the custom `MultipleFileField` had been removed, when the current form uses exactly that). It has been replaced with a description of current behaviour.

---

## Where it lives

| Piece | Location |
|---|---|
| Admin view | `PublicKnowledgeDocumentAdmin.bulk_upload_view` — `public_chatbot/admin.py` |
| URL | `/admin/public_chatbot/publicknowledgedocument/bulk-upload/`, registered via `get_urls()` and wrapped in `admin_site.admin_view` (staff only) |
| Form | `BulkDocumentUploadForm` — `public_chatbot/forms.py` |
| Template | `public_chatbot/templates/admin/public_chatbot/bulk_upload.html` |
| Processing | `PublicKnowledgeDocumentAdmin._process_simple_bulk_upload`, wrapped in `@transaction.atomic` |
| Target model | `PublicKnowledgeDocument` — `public_chatbot/models.py` |

Access requires `has_add_permission`; otherwise the view raises `PermissionDenied`.

---

## The form

`BulkDocumentUploadForm` has two fields:

- **`files`** — a custom `MultipleFileField` paired with a `MultipleFileInput` widget whose `accept` attribute advertises `.txt, .pdf, .docx, .html, .md, .csv, .json`. Required.
- **`category`** — free-text `CharField` (max 50), default `general`, applied to every document in the batch.

The form also takes a `user` keyword argument, which the admin view supplies so the uploader can be attributed.

`accept` is a browser hint only and does not enforce anything server-side; what actually succeeds depends on what `_extract_simple_content` can read.

---

## Processing

For each file in `request.FILES.getlist('files')`:

1. Extract text via `_extract_simple_content`.
2. **Skip** the file if the result is empty or under 10 characters, recording a per-file error.
3. Create a `PublicKnowledgeDocument` with:
   - `title` — derived from the filename: extension stripped, underscores replaced with spaces, title-cased.
   - `content` — the extracted text.
   - `category` — from the form.
   - the uploader recorded via `get_user_identifier(request.user)` as a username string (`PublicKnowledgeDocument` deliberately has no user foreign keys).

The batch runs in one transaction; per-file failures are collected and shown as admin messages rather than aborting the run.

`PublicKnowledgeDocument.save()` computes `document_id`, `content_preview` and a SHA-256 `content_hash` automatically, and calls `full_clean()` on every write.

---

## What upload does *not* do

New documents are **not** live to the chatbot. Two further steps are required:

1. **Approval** — `is_approved` and `security_reviewed` both default to false. Set them from the admin list view.
2. **Sync to ChromaDB** — run `python manage.py sync_public_knowledge`, which pushes documents that are both approved and security-reviewed into the vector store and sets `synced_to_chromadb` / `chromadb_id`. Use `--force-sync` to re-push already-synced rows, `--dry-run` to preview, `--category` / `--limit` to narrow the batch.

Deletion removes the row from ChromaDB via the pre/post-delete signals in `public_chatbot/signals.py`.

The `quality_score` field (0–100) exists for filtering but is not populated by bulk upload.

---

## Related management commands

| Command | Purpose |
|---|---|
| `sync_public_knowledge` | Push approved documents into ChromaDB |
| `init_sample_knowledge` | Insert ~6 pre-approved seed documents (`--clear-existing` to reset) |
| `test_bulk_upload` | Diagnostics: `--create-samples` writes fixture files, `--test-security` exercises `DocumentSecurityValidator`, `--test-formats` exercises `DocumentProcessor`. With no flags it only prints banners. |

For how the chatbot consumes this knowledge base — and why it is isolated from the Milvus-backed project system — see [`public_chatbot/ARCHITECTURE.md`](public_chatbot/ARCHITECTURE.md).
