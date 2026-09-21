# Architecture

Kagaz is a modular monolith with async background workers, not microservices. The API stays thin; OCR, LLM, and RAG work all run in Celery workers off a Redis queue.

Multi-tenant by design — every table and every RAG query is scoped by `organization_id`.

---

## Components

| Component    | Tech                    | Responsibility                                         |
| ------------ | ----------------------- | ------------------------------------------------------ |
| Frontend     | Next.js + TS            | Upload, dashboards, review/approval UI                 |
| Backend API  | FastAPI                 | Auth, validation, enqueue jobs — no heavy work inline |
| Database     | PostgreSQL              | Users, orgs, documents, policies, approvals, audit log |
| Vector store | pgvector                | Policy embeddings, RAG similarity search               |
| Queue        | Redis                   | Job queue + status cache                               |
| Workers      | Celery                  | OCR → classify → extract → validate pipeline        |
| OCR          | PaddleOCR               | Text + layout extraction                               |
| LLM          | Llama/Groq (abstracted) | Classification, extraction, chatbot                    |
| RAG          | LangChain + pgvector    | Retrieves the right org/policy chunk                   |
| Storage      | AWS S3                  | Original + processed files                             |
| Auth         | JWT + RBAC              | Role + org-membership checks per request               |

**Rule:** only the Backend touches PostgreSQL and S3 directly. Frontend only talks to the Backend. Workers talk to OCR/LLM/RAG and write results back through the same data layer.

---

## System Diagram

```
Frontend (Next.js)
       │  HTTPS/JWT
       ▼
Backend API (FastAPI)
   │        │        │
   ▼        ▼        ▼
Postgres  Redis     S3
+pgvector  │      (files)
           ▼
     Celery Workers
      │     │     │
      ▼     ▼     ▼
  PaddleOCR LLM   RAG ──▶ pgvector
      │     │     │
      └─────┼─────┘
            ▼
   Policy Validation
            │
            ▼
   Workflow → Review → Approval
            │
            ▼
       Audit Log
```

---

## Document Flow

```
Upload ──▶ Store in S3 ──▶ Queue job
                                │
                                ▼
                    OCR (PaddleOCR)
                                │
                                ▼
              Classify domain + doc type (LLM)
                                │
                                ▼
                    Extract fields (LLM)
                                │
                                ▼
              Retrieve policy (RAG, scoped by
              org_id + domain + policy_version)
                                │
                                ▼
                  Validate against policy
                                │
                                ▼
                  Route to Reviewer/Approver
                                │
                                ▼
                  Decision ──▶ Audit log
```

Policy onboarding (feeds the RAG step above):

```
Org uploads policy ──▶ S3 + DB record ──▶ chunk + embed ──▶ store in pgvector
```

---

## Why this shape

- **Async by default** — OCR/LLM calls are slow; the API only enqueues, never blocks on them.
- **pgvector, not a separate vector DB** — one less moving part until scale demands otherwise.
- **LLM behind an abstraction** — swappable provider, isolated to `ai/`.
- **`organization_id` scoping is enforced in code, not just the UI** — it's the tenant-isolation guarantee, not an optimization.
- **Modular monolith** — faster for a 9–10 person student team to ship and debug; module boundaries (`ocr/`, `ai/`, `rag/`, `workflows/`) leave room to split into services later.

## Assumptions

- Single LLM provider for now; multi-provider fallback is out of scope.
- Current volume doesn't justify a dedicated vector DB or microservices — revisit if that changes.
- Reviewer/approver assignment rules are config, not hardcoded.
