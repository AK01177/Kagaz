# Kagaz backend

FastAPI backend with a public health check, authenticated PDF uploads, and PDF text extraction. Requires Python 3.10 or newer.

## Setup

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend\.env.example backend\.env
# Edit backend\.env with your database and Supabase project values.
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Interactive documentation: http://127.0.0.1:8000/docs. `GET /api/health` is public.

| Environment variable | Meaning | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL | `postgresql+psycopg2://postgres:postgres@localhost:5432/kagaz` |
| `SUPABASE_URL` | Supabase project URL | Required for authenticated requests |
| `SUPABASE_ANON_KEY` | Supabase publishable/anon API key | Required for authenticated requests |
| `OPENROUTER_API_KEY` | OpenRouter key for classification and structured extraction | Optional; required to run AI processing |
| `DOCUMENT_STORAGE_DIR` | Local storage directory | `storage_data`, relative to working directory |
| `CORS_ALLOWED_ORIGINS` | Comma-separated browser origins allowed to call this API | Localhost ports 3000/3001 |

Export variables or create a `.env` file (see `backend/.env.example`). Kagaz roles and organization memberships remain in its relational database; Supabase Auth owns credentials and user authentication.


## Upload API (BE-02)

`POST /api/documents` accepts a multipart field named `file` and an `Authorization: Bearer <token>` header. HTTP 201 returns `document_id`, `filename`, `file_type`, processing `status`, and UTC `uploaded_at`.

Supports readable PDFs and PNG/JPG/JPEG images up to 10 MiB. Embedded PDF text is read directly; scanned PDFs and images use local OCR. Classification and structured field extraction run when `OPENROUTER_API_KEY` is configured. Without that key, the file is still stored and classification is skipped.

The entire upload request is limited to 10 MiB plus 64 KiB for multipart headers,
boundaries and other fields. Incoming bytes are counted before reaching the
multipart parser, including when Content-Length is missing or inaccurate.
Oversized requests return 413 and partial parser files are closed. The separate
10 MiB file check remains in place after parsing.

Documents use generated IDs as filenames. Metadata is persisted in `storage_data/metadata/<document_id>.json`, including file size, OCR text length, storage path, submitter and organization. When the database is configured, document records, extracted fields, and audit events are written in one database transaction; a persistence failure rejects the upload and removes its local file and metadata. Identity comes from the verified token. S3 storage is optional and currently applies to policy source files, not these document uploads.

Errors use `{"error": {"code": "...", "message": "..."}}`: invalid/missing files return 400, missing/invalid tokens 401, forbidden uploads 403, oversized files 413, unsupported types 415, malformed fields 422, storage failures 500, and missing authentication configuration 503.

## Supabase Auth integration

The backend validates each Supabase access token against the Supabase Auth user endpoint. Kagaz resolves that identity to a local profile and active organization membership; roles and permissions come from Kagaz membership records. Passwords are not stored in the Kagaz database.

Existing Kagaz profiles are linked to Supabase identities by confirmed email on first authenticated request. New Supabase accounts need a corresponding Kagaz profile and organization membership before using protected workspace features. Existing users should use Supabase password reset to establish their new credential.

After configuring PostgreSQL, apply migrations from the repository root with `.venv/bin/alembic -c backend/alembic.ini upgrade head` (PowerShell: `..\.venv\Scripts\alembic.exe -c alembic.ini upgrade head` from `backend`). The latest migration removes stored local password hashes.

For local testing, sign in through the frontend and use the resulting Supabase access token for API requests:

```powershell
curl.exe -H "Authorization: Bearer $token" -F "file=@invoice.pdf" http://127.0.0.1:8000/api/documents
```

## Tests

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Covers health, extraction, upload persistence, extraction compatibility, file validation, rollback, identity attribution and authentication rejection paths.

## Database Migrations

Alembic manages migrations for PostgreSQL:

```bash
# View migration history
alembic history

# Apply migrations
alembic upgrade head

# Roll back last migration
alembic downgrade -1

# Generate SQL offline without live database
alembic upgrade head --sql
```

For complete database documentation, schema details, and setup instructions, see `database/db.md`.
