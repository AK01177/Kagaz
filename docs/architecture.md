# Architecture

This page describes the code in this repository today. The project is a web application with a FastAPI backend and a Next.js frontend. It is not currently a worker-based or microservice system.

## Implemented parts

| Part | What the code currently does |
|---|---|
| Frontend | Next.js pages for sign-in, documents, document details, review, approvals, policies, assistant, and admin screens. |
| API | FastAPI routes for authentication, document intake, policies, workflow, audit, notifications, and policy questions/validation. |
| Authentication | Supabase Auth provides sign-in tokens. The backend checks tokens and uses Kagaz database profiles and memberships for organization and role permissions. |
| Database | SQLAlchemy and Alembic manage PostgreSQL records, including organizations, documents, extractions, policies, validation, workflow, and audit events. Policy vectors use pgvector. |
| Document files | Uploaded documents use local disk storage by default (`DOCUMENT_STORAGE_DIR`). Policy source files can use local disk or optional S3 storage (`S3_POLICY_BUCKET`). |
| OCR and extraction | Text is read from PDFs when present; scanned PDFs and images use local OCR. Optional OpenRouter calls classify documents and extract structured fields. |
| Policy knowledge base | Policy text is split into clauses, embedded with Gemini, and stored in PostgreSQL/pgvector. Validation and question answering retrieve policy evidence scoped to the organization. |
| Workflow | API actions move documents through review and approval states and write related audit events. |

## Current document flow

```text
Browser
  → Next.js UI
  → FastAPI API
      → validate and store uploaded file on local disk
      → extract PDF text or run local OCR
      → optionally call OpenRouter for classification and field extraction
      → write metadata and, when configured, document/extraction/audit rows to PostgreSQL
      → run policy validation or workflow actions when requested
```

Document uploads are not sent to S3 by the current upload path. S3 is used only by policy-source ingestion/retrieval when `S3_POLICY_BUCKET` is configured. Without that setting, policy sources are also local.

## Policy flow

```text
Policy source (PDF, DOCX, TXT, or entered text)
  → local disk or optional S3 policy storage
  → parse and split into clauses
  → Gemini embeddings stored in pgvector
  → organization-scoped retrieval for validation or assistant answers
```

## Planned work is not running infrastructure

The repository does not currently configure Redis, Celery workers, a job queue, a separate worker service, LangChain, or the TypeSafe SDK. Classification does call the OpenRouter decision API using its `~typesafe/jev-latest` model identifier. OCR, classification, and structured extraction run during the upload request; policy ingestion and workflow actions also run through API requests. Other technologies appear in older planning material, but are not part of the runtime described by the code above.
