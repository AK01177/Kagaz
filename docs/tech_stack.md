# Technology stack

This describes dependencies and services used by the current code. The architecture page separates implemented parts from longer-term plans.

| Area | Current implementation |
|---|---|
| Frontend | Next.js, React, TypeScript, and ESLint. |
| API | Python, FastAPI, and Uvicorn. |
| Data access | SQLAlchemy ORM and Alembic migrations. |
| Database | PostgreSQL; pgvector stores policy embeddings. |
| Authentication | Supabase Auth for credentials and access tokens; Kagaz database memberships and roles for workspace authorization. |
| File storage | Local disk for document uploads. Policy source files use local disk by default and can use AWS S3 when `S3_POLICY_BUCKET` is configured. |
| OCR | RapidOCR ONNX Runtime, with optional PaddleOCR compatibility. Scanned PDF rendering uses `pdf2image` and the host's Poppler installation. |
| Document AI | OpenRouter API calls for classification (using the `~typesafe/jev-latest` decision model) and structured field extraction when configured. |
| Policy AI | Gemini API for embeddings and policy question answering when `GEMINI_API_KEY` is set. |
| CI | GitHub Actions compiles Python, generates offline migration SQL, runs a configured subset of backend tests, then lints and builds the frontend. |

## Not currently part of the runtime

The code does not currently start Redis, Celery workers, LangChain, or use the TypeSafe SDK. Classification sends a request to OpenRouter's decision API with a Jev model identifier. Other proposed infrastructure in older documents should not be treated as running until it is implemented.
