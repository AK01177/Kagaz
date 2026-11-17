# Policy knowledge base and RAG

How Kagaz turns an organization's policies into evidence for validation and for the assistant. This is the design as built; the code is in `backend/services/`.

```
policy file (PDF / DOCX / TXT)  or  text entered through the policy API
        │  policy_text.py      read, validate, keep page numbers
        ▼
   clauses ── policy_chunking.py   one chunk per numbered clause, labelled with its section and page
        │  embeddings.py       Gemini embedding, 1536 dimensions, normalised
        ▼
 policy_chunks (Postgres + pgvector, per policy version, per organization)
        │  policy_retrieval.py   one access rule for every search path
        ├──► policy_validation.py   judge a document against its clauses, verify in code
        └──► assistant.py           answer a question, verify the citations
```

## Ingestion

* **Formats.** PDF (with OCR for scanned files), DOCX (headings and tables are kept) and TXT. Each file is checked to be what its extension claims; unsupported or fake files are rejected before anything is stored.
* **Chunking.** A policy is a list of clauses, so one numbered clause (`2.3 ...`) is one chunk, prefixed by its section heading (`2. Expense Claims: 2.3 ...`). Prose is packed up to 900 characters, a longer piece is split on sentences, repeated page headers/footers are removed, and nothing is dropped. On the evaluation set this kept 100% of correct answers above the relevance floor, against 84% for fixed 1200-character windows.
* **Versions.** A version becomes ACTIVE only after every step succeeded, in one transaction; the previous version then becomes ARCHIVED. If indexing fails the version is FAILED with a short message and the previous version keeps serving. A failed version can be retried without uploading again.
* **Text policies.** Policies created or edited through `POST/PUT /api/policies` are chunked and embedded immediately, through the same code as uploaded files. A provider outage does not fail the request; the version is marked FAILED and can be retried.
* **Reuse.** A new version re-embeds only clauses whose text changed (matched by SHA-256 within the same policy and embedding model).
* **Embedding model.** Each version records the model that produced its vectors. Retrieval ignores versions embedded with another model. After changing `GEMINI_EMBEDDING_MODEL` run `python -m scripts.reindex_policies` from `backend/`.

## Which policies apply

A search only sees policies that are active, belong to the caller's organization, have a classification the caller's role may read, and are in their ACTIVE version. Every search path (vector, keyword fallback, validation) builds these rules from one class, `PolicyScope`, so a new path cannot forget them.

**Document types.** There are no new types: a policy's "applies to" is one of the classifier's four categories (`academics`, `hr_documents`, `financial`, `general_confidential`), or empty for every type. People type these in many spellings, so every spelling is resolved through the classifier's own alias table (`CATEGORY_ALIASES`): "Invoice", "INVOICES", "expense-claim" and "financial" are one type, "HR Forms" and "hr-documents" are another. Values are stored in canonical form and an unknown value is rejected with the list of valid ones, because it could never match a document. A document sees policies for its own type plus policies for every type. Domain matching ignores case.

## Retrieval

* **Floor.** A chunk must reach cosine similarity `POLICY_RELEVANCE_THRESHOLD` (default 0.55). Calibrated on `backend/tests/rag_eval`: off-topic questions score up to about 0.53, genuine answers start at about 0.65. On-topic questions the policies do not cover score about 0.61, so no floor can separate them; the answering model must decide "the policy does not say this".
* **Exact figures.** Embeddings are weak at numbers, so chunks containing a figure of the question (`30`, `2.3`, `$1,000`, `5%`) are also considered and ranked first. The floor still applies to them.
* **Duplicates.** The same clause appearing in two policies is returned once.
* **Fallback.** If the embedding service is down the assistant searches by keywords, with exactly the same access rules. Any other error is raised, not hidden.

## Validation

`POST /api/documents/{id}/validate-policy`; full contract in `backend/docs/policy-validation-api.md`.

1. If all applicable clauses fit (25 or fewer) the model sees all of them. Otherwise it sees the 30 clauses most relevant to the document, found with one search per extracted field, and the result says so.
2. The model returns findings with exact quotes. **The model proposes; code decides.** A citation is trusted only if the clause was supplied and the quote appears verbatim in it; a FAIL needs a stored field, its value and enough extraction confidence; contradictory findings go to review; every clause must be cited or ruled out; a model that returns nothing cannot imply PASS.
3. Anything uncertain, unchecked or unavailable is `NEEDS_HUMAN_REVIEW`. An applicable policy that cannot be searched is reported by name, and the other policies are still checked.

## Assistant

`POST /api/documents/{id}/assistant/query`. The model is given keyed evidence (document fields `D1…`, policy clauses `P1…`) and must cite keys. A citation counts only if that key was supplied; "grounded" requires the model to say so and at least one verified citation; confidence is capped (0.95 grounded, 0.4 otherwise). Without the model, answers fall back to stored fields, and a policy clause is offered only as "the closest clause", never as a grounded answer. Workflow actions (approve, reject, ...) are refused.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | none | Embeddings and the language model (a free key works). |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Changing it needs a re-index. |
| `GEMINI_CHAT_MODEL` | `gemini-3.1-flash-lite` | Validation and assistant. |
| `POLICY_RELEVANCE_THRESHOLD` | `0.55` | Similarity floor. |
| `POLICY_VALIDATION_CONFIDENCE_THRESHOLD` | `0.7` | Below this an extracted value is never a confirmed violation. |

Rate limits (HTTP 429) and brief outages are retried with backoff. The API key is sent in a header and never logged or placed in a URL.

## Database

Needs PostgreSQL with the `vector` extension (Supabase: Database → Extensions → `vector`). Run `alembic upgrade head` from `backend/`. Migration `b2d5e8f1a306` also adds columns the policy models needed that no earlier migration had created, and makes `policy_versions.source_document_id` nullable (text policies have no source file).

## Testing

* **Unit and API tests** need no network or database: `cd backend && pytest`. The conftest removes the Gemini key so tests can never reach the provider.
* **Postgres retrieval tests** are skipped unless `QA10_TEST_DATABASE_URL` points at a database with the vector extension. They run in a throwaway schema inside a transaction that is rolled back, so an existing database is safe to use.
* **Real-stack evaluation** (real Gemini, real pgvector, rolled back, a few dozen API calls). Run from `backend/`:
  * `python -m tests.rag_eval.e2e_check` retrieval quality: natural and exact-term questions, off-topic and wrong-document-type questions, cross-organization leakage.
  * `python -m tests.rag_eval.e2e_validation` validation and assistant checks with the real model.
  * `python -m tests.rag_eval.calibrate` similarity distributions, for choosing the relevance floor. Re-run it on your own policies before trusting the default floor.
  * The policies and questions live in `backend/tests/rag_eval/`; add your own to evaluate real content.

## Known limits

* The evaluation set is small and synthetic; the floor should be re-checked on real policies.
* Validation cannot independently verify a clause the model rules irrelevant; the number of dismissed clauses is reported in the summary.
* In `relevant_subset` mode a clause that none of the field searches reaches is not seen by the model.
* The assistant's rate limiter is in memory (resets on restart, not shared between workers).
* Classification and field extraction still use OpenRouter; only the policy knowledge base uses Gemini.
