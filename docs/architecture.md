# Architecture

Kagaz is a modular monolith with async background workers, not microservices. The API stays thin; OCR, LLM, RAG, and Jev decision work run through Celery workers off a Redis queue.

Kagaz is multi-tenant by design. Every organization-owned record and every RAG query is scoped by `organization_id`.

> **Jev status:** Proposed / under evaluation. Jev should become part of the production architecture only after Kagaz-specific evaluation.

---

## Components

| Component | Tech | Responsibility |
|---|---|---|
| Frontend | Next.js + TypeScript | Upload, dashboards, review/approval UI |
| Backend API | FastAPI | Auth, validation, enqueue jobs, workflow APIs |
| Database | PostgreSQL | Users, orgs, documents, policies, approvals, audit log |
| Vector store | pgvector | Policy embeddings and RAG similarity search |
| Queue | Redis | Job queue + status cache |
| Workers | Celery | OCR → AI processing → validation pipeline |
| OCR | PaddleOCR | Text + layout extraction |
| LLM | Llama/Groq (abstracted) | Field extraction, chatbot, summaries, explanations |
| **Decision Model** | **Jev (TypeSafe, abstracted)** | Classification, bounded decisions, routing/score candidates |
| RAG | LangChain + pgvector | Retrieves the applicable org/domain policy |
| Storage | AWS S3 | Original + processed files |
| Auth | JWT + RBAC | Role + organization-membership checks |

### Responsibility Split

- **LLM:** generate, extract, summarize, explain
- **Jev:** make bounded typed decisions
- **RAG:** retrieve organization-specific knowledge
- **Backend:** enforce rules, thresholds, authorization, and workflow actions
- **Human:** final review/approval where required

> **Rule:** Only the Backend touches PostgreSQL and S3 directly. Frontend only talks to the Backend. Workers call OCR/LLM/Jev/RAG and write results back through the same data layer.

---

## System Diagram

```text
                    Frontend (Next.js)
                           │
                        HTTPS/JWT
                           ▼
                   Backend API (FastAPI)
                    │       │       │
                    ▼       ▼       ▼
                Postgres   Redis     S3
                +pgvector           (files)
                    │       │
                    └───────┼──────────────┐
                            ▼              │
                       Celery Workers      │
                            │              │
              ┌─────────────┼─────────────┐│
              ▼             ▼             ▼│
         PaddleOCR         LLM           RAG
                            │              │
                            ▼              ▼
                         Jev          pgvector
                            │
                            ▼
                    Policy Validation
                            │
                            ▼
                   Workflow / Routing
                            │
                            ▼
                    Review / Approval
                            │
                            ▼
                       Audit Log
```

---

## AI Responsibility Flow

```text
Document
    │
    ▼
PaddleOCR / Text Extraction
    │
    ▼
┌─────────────────────────────────────┐
│              AI Layer               │
│                                     │
│  LLM  → field extraction            │
│  Jev  → bounded decisions           │
│  RAG  → policy retrieval            │
│  LLM  → explanation / summary       │
└──────────────────┬──────────────────┘
                   ▼
             Workflow Engine
                   │
             ┌─────┴─────┐
             ▼           ▼
          Reviewer    Approver
             │           │
             └─────┬─────┘
                   ▼
               Audit Log
```

---

## Document Flow

```text
Upload
  ↓
Store in S3
  ↓
Queue job
  ↓
OCR / text extraction
  ↓
Document classification
  ├── Jev candidate
  └── LLM fallback / comparison
  ↓
Field extraction
  └── LLM
  ↓
Retrieve policy
  └── RAG, scoped by organization_id + domain + policy_version
  ↓
Policy validation
  └── Jev candidate for bounded decisions
  ↓
Issue / confidence checks
  └── Jev candidate + deterministic rules
  ↓
Workflow routing
  └── Jev candidate → Backend executes route
  ↓
Review / Approval
  ↓
Decision
  ↓
Audit Log
```

---

## Jev Decision Layer

Jev is intended for decisions where the possible output can be defined in advance.

| Decision | Example |
|---|---|
| Classification | `Invoice`, `Resume`, `Transcript` |
| Review gate | `Human review required?` |
| Policy result | `PASS`, `FAIL`, `REVIEW` |
| Routing | `Finance Reviewer`, `HR Reviewer`, `Compliance` |
| Priority | `1–5` review priority |
| Risk | Low / Medium / High |

The backend remains responsible for converting model output into actual system actions.

```text
Jev → Decision
       ↓
Backend → Rule / Threshold
       ↓
Action
```

Jev must not directly bypass authorization, workflow rules, or human approval.

---

## Policy Validation Flow

```text
Document
    ↓
LLM extracts relevant fields
    ↓
RAG retrieves applicable policy
    ↓
Jev evaluates bounded policy question
    ↓
PASS / FAIL / REVIEW
    ↓
LLM generates explanation
    ↓
Workflow / Human Review
```

The policy decision must retain the applicable `organization_id` and `policy_version`.

---

## Fallback Strategy

```text
                 Jev
                  │
          ┌───────┴────────┐
          ▼                ▼
      Confident          Uncertain /
       result             failure
          │                │
          ▼          ┌─────┴─────┐
      Continue       LLM       Human Review
```

The exact fallback path is configured per use case and must be evaluated.

---

## Organization Isolation

```text
Authenticated User
       ↓
organization_id
       ↓
Authorized Document
       ↓
Authorized Policy / Context
       ↓
LLM / Jev / RAG
```

RAG retrieval remains scoped by:

```text
organization_id + domain + policy_version
```

Jev does not replace or weaken this isolation.

---

## Auditability

For Jev decisions, the audit record should include where applicable:

```text
decision_id
document_id
organization_id
decision type
result
probability / confidence
model version
timestamp
downstream action
fallback used
policy_version
```

Do not store sensitive raw model input unnecessarily.

---

## Provider Abstraction

```text
AI Services
├── llm/
├── jev/
├── ocr/
└── rag/
```

LLM and Jev integrations should remain behind internal service interfaces so providers can be replaced without changing core workflow logic.

---

## Why This Architecture

- **Async by default:** OCR and AI calls do not block the API.
- **Modular monolith:** appropriate for the student team.
- **PostgreSQL + pgvector:** avoids an unnecessary separate vector database.
- **LLM abstraction:** provider can change without changing business logic.
- **Jev abstraction:** Jev can be evaluated or replaced without coupling workflow code to it.
- **Organization isolation:** enforced in backend/data access.
- **Human-in-the-loop:** uncertain AI results can be reviewed.
- **Auditability:** important AI and workflow decisions remain traceable.

---

## Assumptions

- Jev is an experimental candidate and requires Kagaz-specific evaluation before permanent adoption.
- Single LLM provider for now; multi-provider fallback is out of scope.
- Jev provider fallback is not assumed until evaluated.
- Current volume does not justify a dedicated vector DB or microservices.
- Reviewer/approver assignment rules are configuration, not hardcoded.
- Final approval remains human-controlled where required.

---

## Evaluation Gate for Jev

The first evaluation target is **document classification**.

```text
Same Kagaz dataset
       ↓
┌──────────────┐    ┌──────────────┐
│ Current LLM  │ vs │     Jev      │
└──────────────┘    └──────────────┘
       ↓                  ↓
       └────────┬─────────┘
                ▼
       Accuracy / confidence
       latency / cost / failures
```

Only after successful evaluation should Jev be adopted for additional decisions such as policy validation or routing.
