# Kagaz backend

FastAPI backend with PostgreSQL relational persistence, multi-tenant document management, authenticated PDF uploads, and structured document extraction. Requires Python 3.10 or newer.

## Setup

From the repository root:

```bash
# Set up virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate   # On Windows: .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Update DATABASE_URL and JWT_SECRET as needed

# Run database migrations
cd backend
alembic upgrade head

# Start API server
uvicorn main:app --reload
```

Interactive documentation: http://127.0.0.1:8000/docs. `GET /api/health` is public.

## Environment Variables

| Environment variable | Meaning | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL | `postgresql+psycopg2://postgres:postgres@localhost:5432/kagaz` |
| `JWT_SECRET` | Shared HS256 signing secret, at least 32 bytes | Required for authenticated requests |
| `JWT_ISSUER` | Trusted token issuer | `kagaz` |
| `JWT_AUDIENCE` | Expected token audience | `kagaz-api` |
| `DOCUMENT_STORAGE_DIR` | Local binary storage directory | `storage_data`, relative to working directory |

Export variables or create a `.env` file (see `backend/.env.example`). Use a persistent secret shared with the trusted token issuer outside local testing.

## Database Migrations & Persistence (DB-01, DB-02, DB-03)

PostgreSQL is the **authoritative source of truth** for all document metadata, processing status, and structured extraction results. File binaries remain stored in object storage (local filesystem or cloud S3/blob store).

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

## Demo JSON Metadata Migration

To migrate historical or demo JSON metadata from `storage_data/metadata/` into PostgreSQL:

```bash
# Dry run preview:
python backend/scripts/migrate_json_metadata.py --dry-run

# Run migration:
python backend/scripts/migrate_json_metadata.py --storage-dir storage_data
```

The migration is idempotent, non-destructive, and links imported documents to an initial `ExtractionRun` record.

## API Endpoints

All document endpoints enforce multi-tenant isolation based on the verified JWT's `organization_id`.

- `POST /api/documents`: Uploads a PDF, saves binary to object storage, persists metadata to PostgreSQL (`Document`), and schedules initial pipeline processing.
- `GET /api/documents`: Lists documents belonging to the authenticated user's organization from PostgreSQL with pagination support.
- `GET /api/documents/{id}`: Retrieves authoritative document metadata and processing state from PostgreSQL.
- `GET /api/documents/{id}/file`: Streams the original binary file from object storage.
- `PATCH /api/documents/{id}/classification`: Updates document category and confidence in PostgreSQL and re-runs entity extraction.
- `POST /api/documents/{id}/classify`: Manually triggers classification re-evaluation and updates PostgreSQL.
- `GET /api/documents/{id}/extract`: Retrieves authoritative extraction results from PostgreSQL `extractions` table.
- `POST /api/documents/{id}/extract`: Re-runs entity extraction, logs an `ExtractionRun`, and persists extracted fields to PostgreSQL.
- `DELETE /api/documents/{id}`: Removes the document from PostgreSQL (cascading extraction runs and extractions) and deletes the binary from storage.

## JWT Integration

Upload and document management verify HS256 signature, expiry, issuer and audience. Required claims: `sub`, `exp`, `iat`, `iss`, `aud`, `role`, `organization_id`, `active`.

For local testing:

```bash
export JWT_SECRET="your-32-byte-secret-here-for-local-testing"
python -c "import os,time,jwt; now=int(time.time()); print(jwt.encode({'sub':'local-user','organization_id':'local-org','role':'SUBMITTER','active':True,'iss':'kagaz','aud':'kagaz-api','iat':now,'exp':now+3600}, os.environ['JWT_SECRET'], algorithm='HS256'))"
```

## Running Tests

From the repository root:

```bash
# Run all tests
pytest backend/tests -v

# Run DB-03 persistence test suite
pytest backend/tests/test_db03_postgresql_persistence.py -v
```
