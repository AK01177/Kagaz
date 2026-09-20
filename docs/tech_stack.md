### STACK Decisions

### Frontend — Next.js + TypeScript

Type safety and component structure fit a multi-role UI (submitter, reviewer, approver, admin); built-in routing covers the dashboard and approval screens without extra tooling.

### Backend — Python + FastAPI

Async support keeps the API responsive while OCR/LLM work runs in the background. Python gives direct access to the OCR/LangChain ecosystem with no cross-language bridge.

### Database — PostgreSQL

Core entities (documents, policies, approvals, audit logs) are relational and need ACID guarantees. Mature, well-indexed, and extendable with pgvector instead of adding a second database.

### AI / LLM — Llama / Groq (or equivalent), behind an abstraction layer

Kept behind an internal abstraction so the provider can change without touching business logic — model pricing/availability shifts quickly, and the workflow is the product, not the model.

### OCR — PaddleOCR

Chosen over Tesseract, EasyOCR, and cloud OCR APIs: self-hostable (no per-page cost), strong on tables/complex layouts, multilingual — fits transcripts, invoices, offer letters. Tesseract kept only as an optional fallback.

### RAG — LangChain + pgvector, scoped by `organization_id + domain + policy_version`

LangChain handles embeddings/retrieval so the team isn't building RAG orchestration by hand. pgvector avoids standing up a separate vector database before scale justifies it. The `organization_id + domain + policy_version` scope is a correctness requirement — it's what stops one org's documents being validated against another org's policy.

### Deployment — Docker + Docker Compose, Modular Monolith + Workers, GitHub Actions

A modular monolith (`frontend`, `backend`, `worker`, `postgres`, `redis`) is faster for a student team to build and debug than microservices, with clear module boundaries (`ocr/`, `ai/`, `rag/`, `workflows/`) that leave room to split later. Celery workers scale independently of the API, which is where OCR/LLM load will actually bite first. GitHub Actions runs test/lint/build/deploy on every push.

---

## Summary Table

| Component  | Decision                                                            |
| ---------- | ------------------------------------------------------------------- |
| Frontend   | Next.js + TypeScript                                                |
| Backend    | Python + FastAPI                                                    |
| Database   | PostgreSQL                                                          |
| AI/LLM     | Llama / Groq (or equivalent), via abstraction layer                 |
| OCR        | PaddleOCR                                                           |
| RAG        | LangChain + pgvector                                                |
| Deployment | Docker + Docker Compose, Modular Monolith + Workers, GitHub Actions |
