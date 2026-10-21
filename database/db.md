# Kagaz Database Architecture & Migration Guide

## 1. Overview

Kagaz uses **PostgreSQL** for relational persistence of multi-tenant document metadata and extracted structured fields, managed through **SQLAlchemy** (ORM) and **Alembic** (schema migrations). Unit tests run against an in-memory **SQLite** database with foreign key enforcement enabled (`PRAGMA foreign_keys=ON`).

### Database Responsibilities

| Table | Model | Responsibility | Tenant Isolation |
|---|---|---|---|
| `documents` | `Document` (`app/models/document.py`) | Tracks document identity, tenant ownership, upload details, file size, storage path, status lifecycle, and classification results | Scoped by `organization_id` (indexed) |
| `extractions` | `Extraction` (`app/models/extraction.py`) | Stores granular structured key-value extractions per document with confidence scores | References `documents.id` via foreign key with `ON DELETE CASCADE` |

---

## 2. Table Schemas & Constraints

### `documents` Table
- `id`: `VARCHAR(36)` (UUID string), Primary Key.
- `organization_id`: `VARCHAR(36)`, Not Null, Indexed (multi-tenant boundary).
- `uploaded_by`: `VARCHAR(36)`, Not Null (user UUID).
- `filename`: `VARCHAR`, Not Null.
- `file_type`: `VARCHAR`, Not Null (e.g. `application/pdf`).
- `file_size`: `INTEGER`, Not Null (bytes).
- `storage_path`: `VARCHAR`, Not Null (e.g. `uploads/doc.pdf`).
- `status`: `documentstatus` Enum (`UPLOADED`, `PROCESSING`, `CLASSIFIED`, `FAILED`), Not Null, Indexed.
- `upload_timestamp`: `TIMESTAMP WITH TIME ZONE`, Not Null.
- `classification`: `VARCHAR`, Nullable (e.g. `invoice`, `transcript`).
- `classification_confidence`: `FLOAT`, Nullable, Check Constraint: `classification_confidence IS NULL OR (classification_confidence >= 0.0 AND classification_confidence <= 1.0)`.

### `extractions` Table
- `id`: `VARCHAR(36)` (UUID string), Primary Key.
- `document_id`: `VARCHAR(36)`, Foreign Key to `documents.id` with `ON DELETE CASCADE`, Not Null, Indexed.
- `field_name`: `VARCHAR`, Not Null.
- `value`: `TEXT`, Not Null.
- `confidence`: `FLOAT`, Not Null.
- `created_at`: `TIMESTAMP WITH TIME ZONE`, Not Null.
- `updated_at`: `TIMESTAMP WITH TIME ZONE`, Not Null (auto-updated on record changes).

### Extraction Constraints
1. **Confidence Range**:
   - Database constraint: `ck_extractions_confidence_range` enforcing `confidence >= 0.0 AND confidence <= 1.0`.
   - Pydantic schema validation: `Field(ge=0.0, le=1.0)`.
2. **One-Record-Per-Field Unique Constraint**:
   - Constraint: `uq_extractions_document_field` on `(document_id, field_name)`.
   - **Policy & Rationale**: Each document stores exactly one extraction record per field name. This aligns with the planned API summary shape in `docs/api-design.md` (`GET /api/documents/{id}/extract`), which represents extracted fields and confidence as dictionary mappings (`{field_name: value}` and `{field_name: confidence}`). Disallowing duplicate field names at the database level eliminates silent overwrites, guarantees dictionary conversion determinism, and maintains clean auditability.
   - Different documents can independently use the same field names.
3. **Foreign Key Lifecycle**:
   - `extractions.document_id` references `documents.id` with `ON DELETE CASCADE`.
   - When a document is deleted, all linked extraction records are automatically removed.

---

## 3. Technology Stack & Dependencies

- **Database Engine**: PostgreSQL 14+ (production/local)
- **Driver**: `psycopg2-binary` (declared in `backend/requirements.txt`)
- **ORM**: `SQLAlchemy >= 2.0`
- **Migration Tool**: `Alembic >= 1.13`
- **Testing**: `pytest` with SQLite in-memory engine (`sqlite:///:memory:`)
- **Configuration**: `python-dotenv`

---

## 4. Database URL Configuration

The database connection string is read from the `DATABASE_URL` environment variable.

### Format

```text
postgresql+psycopg2://<username>:<password>@<host>:<port>/<database_name>
```

### Local Development Default

```text
postgresql+psycopg2://postgres:postgres@localhost:5432/kagaz
```

A template configuration file is available at `backend/.env.example`. Copy this to `backend/.env` for local execution:

```bash
cp backend/.env.example backend/.env
```

`backend/.env` is ignored by Git and will never be committed.

---

## 5. PostgreSQL Setup Prerequisites

### Step 1: Install PostgreSQL

On macOS (via Homebrew):
```bash
brew install postgresql@16
brew services start postgresql@16
```

### Step 2: Create Database User and Database

```bash
# Connect to Postgres default CLI
psql postgres

# Run SQL commands:
CREATE USER postgres WITH PASSWORD 'postgres';
CREATE DATABASE kagaz OWNER postgres;
GRANT ALL PRIVILEGES ON DATABASE kagaz TO postgres;
\q
```

### Step 3: Verify Connection

```bash
psql -h localhost -U postgres -d kagaz -c "SELECT current_database();"
```

---

## 6. Alembic Migrations

Migrations are stored in `backend/migrations/versions/`.

### Migration Ordering & History

```text
<base>
  │
  ▼
06961ad088b5: create documents table (status enum, check constraints, organization index)
  │
  ▼
49eecc4be46a: create extractions table (foreign key to documents.id, confidence check constraint, uq_extractions_document_field) [head]
```

### Applying Migrations

Navigate to the `backend/` directory or run from root:

```bash
# From backend directory:
cd backend
alembic upgrade head

# Or from repository root:
.venv/bin/alembic -c backend/alembic.ini upgrade head
```

### Rolling Back Migrations

Roll back the last migration:
```bash
cd backend
alembic downgrade -1
```

Roll back all migrations to base:
```bash
cd backend
alembic downgrade base
```

### Inspecting Migration History

View current applied version:
```bash
cd backend
alembic current
```

View all migration versions:
```bash
cd backend
alembic history --verbose
```

### Generating SQL Offline (Dry Run)

Generate upgrade SQL without connecting to a live database:
```bash
cd backend
alembic upgrade head --sql
```

Generate downgrade SQL:
```bash
cd backend
alembic downgrade 49eecc4be46a:base --sql
```

---

## 7. Running Tests

Database unit tests run with SQLite in-memory engines and do not require a running PostgreSQL instance. Foreign keys are explicitly enforced via SQLite PRAGMA triggers.

### Run Extraction and Persistence Tests

```bash
python -m pytest backend/tests/test_extraction.py -v
```

### Run Document Metadata Tests

```bash
python -m pytest backend/tests/test_document_metadata.py -v
```

### Run All Database Tests

```bash
python -m pytest backend/tests/test_document_metadata.py backend/tests/test_extraction.py -v
```

### Run Whitespace / Formatting Check

```bash
git diff --check
```

---

## 8. Current Architecture: PostgreSQL vs. JSON Files

| Data | Current Storage Mechanism | Target PostgreSQL Table | Migration Status |
|---|---|---|---|
| Uploaded binary files (PDF) | Local filesystem under `storage_data/<document_id>.pdf` (S3 in production) | S3 / Blob store (referenced by `documents.storage_path`) | Filesystem active |
| Upload metadata | JSON files under `storage_data/metadata/<document_id>.json` | `documents` table | JSON active; PostgreSQL model, CRUD, and migrations ready |
| Document classification | Recorded in JSON metadata (`category`, `confidence`, `status`) | `documents.classification`, `documents.classification_confidence` | JSON active; PostgreSQL schema ready |
| Extracted structured fields | Model and persistence layer (`Extraction`) | `extractions` table | PostgreSQL schema, Alembic migrations, and persistence CRUD implemented |

---

## 9. Remaining Limitations & Follow-Up Work

1. **Local PostgreSQL Service Verification**:
   - A local PostgreSQL server was not running during development in this environment (port 5432 closed).
   - Migrations were validated via Alembic offline SQL generation (`--sql`) and against an isolated SQLite test database.
   - Live PostgreSQL migration (`alembic upgrade head`) should be run once a PostgreSQL service is provisioned or in the staging CI/CD pipeline.
2. **Full Ingestion Pipeline Integration**:
   - Document upload currently persists file metadata to JSON files to preserve the existing BE-02 API contract and file storage behavior.
   - Future sprints will wire the `DocumentStorage` or upload handler to persist concurrently into PostgreSQL using `create_document_metadata`.
3. **Field Extraction Service**:
   - The extraction model, table (`extractions`), unique constraint, and persistence CRUD functions are fully implemented and tested.
   - In later sprints, background workers (Celery/PaddleOCR/LLM) will invoke `app.crud.extraction.create_extractions_bulk` upon completing structured entity extraction.
