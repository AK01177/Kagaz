# Kagaz

Kagaz is an AI-assisted document workflow automation platform under active development. It is being built to help organizations process documents consistently, reduce repetitive manual work, and involve the right people in review and approval decisions.

## Purpose and planned workflow

The long-term workflow is:

**Upload → Text extraction → Classification → Field extraction → Policy validation → Issue detection → Review and approval**

Kagaz is designed to support Academic, HR, and Finance document workflows. Planned capabilities include:

- Upload documents and associate them with an organization and submitter.
- Classify documents such as invoices, contracts, HR forms, and academic records.
- Extract useful text and key fields from supported documents.
- Validate information against organization-specific policies and flag missing or inconsistent details.
- Route documents to reviewers and approvers, with human review when needed.
- Provide document summaries and question answering.
- Maintain access controls and an auditable record of workflow decisions.

These are project goals, not a claim that every feature is already implemented.

## Current implementation

The current implementation includes:

- A FastAPI backend with a public health check at `GET /api/health`.
- PDF and image upload at `POST /api/documents`, with a 10 MiB file limit, file validation, local file storage, and JSON metadata.
- Document metadata lookup at `GET /api/documents/{document_id}`.
- Text extraction for text-based PDFs and local OCR for scanned PDFs and images.
- An AI classification and structured field extraction service. Both require `OPENROUTER_API_KEY` when called.
- Initial Next.js screens for the landing page, login, dashboard, documents, document details, review, approvals, and user administration.
- Supabase Auth email/password login and registration. Kagaz validates Supabase sessions and continues to enforce workspace roles and memberships in its backend database.

Uploads run text extraction, classification, and structured extraction when the required OCR dependencies and `OPENROUTER_API_KEY` are available. Kagaz also includes database-backed document/workspace records and review workflows. Policy validation, summaries/chat, and some frontend workflows remain under active development.

## Technology

| Area | Technology / status |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Current file support | PDF, PNG, JPG, and JPEG |
| OCR | RapidOCR/PaddleOCR local processing; scanned-PDF rendering uses Poppler |
| AI classification and field extraction | OpenRouter; `OPENROUTER_API_KEY` required when used |
| Planned data and infrastructure | PostgreSQL, background workers, policy retrieval, and supporting services |

See [docs/tech_stack.md](docs/tech_stack.md), [docs/architecture.md](docs/architecture.md), and [docs/api-design.md](docs/api-design.md) for design details.

## Run Sprint 1 locally

The following steps use PowerShell on Windows. Open two terminals in the repository root. Python 3.10+ and Node.js 24+ with npm are required.

Create a Supabase project, enable email/password auth, and configure `backend/.env` and `frontend/.env.local` from the example files. Registration creates the Supabase Auth identity. Kagaz workspace access still requires a matching Kagaz profile and active organization membership; existing profiles are linked by confirmed email. Existing users should use Supabase password reset to set a new password.

### Backend

In the first terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
# Edit backend\.env and set DATABASE_URL, SUPABASE_URL, and SUPABASE_ANON_KEY.
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
```

This checkout was verified at `http://127.0.0.1:8001`. Open `http://127.0.0.1:8001/api/health` for the health check and `http://127.0.0.1:8001/docs` for interactive API documentation. The standard backend port is 8000; use `--port 8000` if it is available.

The backend validates Supabase access tokens and resolves Kagaz organization memberships from its relational database. Set these values in `backend/.env` for persistent local use. `OPENROUTER_API_KEY` is only needed when calling the classification service; it is not required to start the API.

### Frontend

In the second terminal, from the repository root:

```powershell
Set-Location frontend
npm ci
# Copy .env.example to .env.local and set your Supabase publishable/anon key.
npm run dev -- --port 3001
```

This checkout was verified at `http://localhost:3001`. The standard frontend port is 3000; Next.js may select another available port if 3000 is occupied.

### Run the tests and checks

Run backend tests from the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

Run frontend checks from `frontend`:

```powershell
npm run lint
npm run build
```

## Local verification status

The backend and frontend development servers started successfully in this checkout. The health endpoint, API docs, and frontend routes (`/`, `/login`, `/dashboard`, `/documents`, `/review`, `/approvals`, and `/admin/users`) returned HTTP 200. The production frontend build completed successfully.

The current backend test run reports **34 passed and 9 failed**. Failures include classifier tests expecting the older `TYPESAFE_API_KEY` configuration and upload tests whose expected response/authentication behavior does not match the current implementation. Frontend lint currently reports a `react-hooks/set-state-in-effect` error in `frontend/app/documents/[id]/page.tsx`. Resolve these existing test and lint failures before treating the checks as clean.

## Repository structure

```text
backend/    FastAPI API, document services, local storage, and tests
frontend/   Next.js application and initial screens
docs/       Requirements, architecture, API design, and testing documentation
sample/     Sample documents for development and testing
scripts/    Evaluation and other project scripts
database/   Database documentation
```

## Documentation

- [Functional requirements](docs/Functional_Requirement.md)
- [Non-functional requirements](docs/Non_Functional_Requirements.md)
- [User stories](docs/user-stories.md)
- [Architecture](docs/architecture.md)
- [API design](docs/api-design.md)
- [Technology stack](docs/tech_stack.md)
- [Testing strategy](docs/testing-strategy.md)
- [Backend setup and API details](backend/README.md)
- [Frontend setup](frontend/README.md)

## Team and project status

Kagaz is developed by a 10-member team for IT314 – Software Engineering using Agile/Scrum. The project is under construction; deployment details, production configuration, and upcoming sprint scope will be documented as they are confirmed.
