# Kagaz Database Architecture & Migration Guide

## 1. Overview

Kagaz uses **PostgreSQL** as the authoritative source of truth for multi-tenant document metadata, processing status, and extracted structured fields, managed through **SQLAlchemy** (ORM) and **Alembic** (schema migrations). File binaries remain stored in object storage (local filesystem directory or S3 in cloud deployments).

Unit and integration tests run against an in-memory **SQLite** database with foreign key enforcement enabled (`PRAGMA foreign_keys=ON`) and connection pooling configured for thread safety (`StaticPool`).

### Database Responsibilities

| Table | Model | Responsibility | Tenant Isolation |
|---|---|---|---|
| `documents` | `Document` (`app/models/document.py`) | Tracks document identity, tenant ownership, upload details, file size, storage object key, status lifecycle (`UPLOADED` -> `PROCESSING` -> `CLASSIFIED` -> `EXTRACTED` / `FAILED`), classification results, and timestamps (`upload_timestamp`, `updated_at`, `processed_at`) | Scoped by `organization_id` (indexed) |
| `extraction_runs` | `ExtractionRun` (`app/models/extraction.py`) | Tracks discrete extraction attempts per document, extraction status (`PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`), model version, error messages, and execution timestamps | Linked to `documents.id` via foreign key with `ON DELETE CASCADE` |
| `extractions` | `Extraction` (`app/models/extraction.py`) | Stores granular structured key-value extractions per document with confidence scores and link to specific extraction run | References `documents.id` and `extraction_runs.id` via foreign key with `ON DELETE CASCADE` |
| `organizations` | `Organization` (`app/models/organization.py`) | Multi-tenant organization boundaries (DB-02) | Primary tenant entity |
| `users` | `User` (`app/models/user.py`) | System users and submitters (DB-02) | Belongs to organizations via memberships |

---

## 2. Table Schemas & Constraints (DB-01, DB-02, DB-03)

### `documents` Table
- `id`: `VARCHAR(36)` (UUID string), Primary Key.
- `organization_id`: `VARCHAR(36)`, Not Null, Indexed (multi-tenant boundary).
- `uploaded_by`: `VARCHAR(36)`, Not Null (user UUID).
- `filename`: `VARCHAR`, Not Null.
- `file_type`: `VARCHAR`, Not Null (e.g. `application/pdf`).
- `file_size`: `INTEGER`, Not Null (bytes).
- `storage_path`: `VARCHAR`, Not Null (object storage key, e.g. `doc_<uuid>.pdf`).
- `status`: `documentstatus` Enum (`UPLOADED`, `PROCESSING`, `CLASSIFIED`, `EXTRACTED`, `FAILED`), Not Null, Indexed.
- `upload_timestamp`: `TIMESTAMP WITH TIME ZONE`, Not Null.
- `updated_at`: `TIMESTAMP WITH TIME ZONE`, Not Null (auto-updated on record changes).
- `processed_at`: `TIMESTAMP WITH TIME ZONE`, Nullable (set when classification/extraction completes).
- `classification`: `VARCHAR`, Nullable (e.g. `invoice`, `receipt`, `bill_of_lading`).
- `classification_confidence`: `FLOAT`, Nullable, Check Constraint: `classification_confidence IS NULL OR (classification_confidence >= 0.0 AND classification_confidence <= 1.0)`.

### `extraction_runs` Table (DB-03)
- `id`: `VARCHAR(36)` (UUID string), Primary Key.
- `document_id`: `VARCHAR(36)`, Foreign Key to `documents.id` with `ON DELETE CASCADE`, Not Null, Indexed.
- `status`: `extractionstatus` Enum (`PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`), Not Null, default `SUCCESS`.
- `model_version`: `VARCHAR`, Nullable.
- `error_message`: `TEXT`, Nullable (stores error details on failed extraction attempts).
- `created_at`: `TIMESTAMP WITH TIME ZONE`, Not Null.
- `completed_at`: `TIMESTAMP WITH TIME ZONE`, Nullable.

### `extractions` Table
- `id`: `VARCHAR(36)` (UUID string), Primary Key.
- `document_id`: `VARCHAR(36)`, Foreign Key to `documents.id` with `ON DELETE CASCADE`, Not Null, Indexed.
- `extraction_run_id`: `VARCHAR(36)`, Foreign Key to `extraction_runs.id` with `ON DELETE CASCADE`, Nullable, Indexed.
- `field_name`: `VARCHAR`, Not Null.
- `value`: `TEXT`, Not Null.
- `confidence`: `FLOAT`, Not Null.
- `created_at`: `TIMESTAMP WITH TIME ZONE`, Not Null.
- `updated_at`: `TIMESTAMP WITH TIME ZONE`, Not Null.

### Relational Hierarchy: Document → Extraction Run → Extracted Fields
```text
Document (1)
   │
   ├── (1..N) ExtractionRun (tracks run status, model version, timestamp, error if failed)
   │               │
   │               └── (0..N) Extraction (links to run via extraction_run_id)
   │
   └── (0..N) Extraction (scoped to document, unique per field_name)
```

### Extraction Constraints
1. **Confidence Range**:
   - Database constraint: `ck_extractions_confidence_range` enforcing `confidence >= 0.0 AND confidence <= 1.0`.
   - Pydantic schema validation: `Field(ge=0.0, le=1.0)`.
2. **One-Record-Per-Field Unique Constraint**:
   - Constraint: `uq_extractions_document_field` on `(document_id, field_name)`.
   - Each document stores authoritative extraction records per field name. When re-extracting with `ExtractionRun`, new runs capture run history while the latest authoritative field values are upserted into `extractions`.
3. **Foreign Key Lifecycle**:
   - Deleting a `Document` cascades delete to all associated `extraction_runs` and `extractions`.
   - Deleting an `ExtractionRun` cascades delete to run-linked records.

---

## 3. Technology Stack & Dependencies

- **Database Engine**: PostgreSQL 14+ (production/staging)
- **Driver**: `psycopg2-binary` (declared in `backend/requirements.txt`)
- **ORM**: `SQLAlchemy >= 2.0`
- **Migration Tool**: `Alembic >= 1.13`
- **Testing**: `pytest` with SQLite in-memory engine (`sqlite:///:memory:` with `StaticPool`)
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
49eecc4be46a: create extractions table (foreign key to documents.id, confidence check constraint, uq_extractions_document_field)
  │
  ▼
b83f09a12c44: add organization and user models (DB-02)
  │
  ▼
c74d89e21f10: integrate document extraction persistence (DB-03)
               - add extraction_runs table
               - add EXTRACTED to documentstatus enum
               - add updated_at and processed_at to documents
               - add extraction_run_id FK to extractions table [head]
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

Roll back the DB-03 migration:
```bash
cd backend
alembic downgrade b83f09a12c44
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
alembic downgrade c74d89e21f10:b83f09a12c44 --sql
```

---

## 7. JSON Metadata Migration Tool (DB-03)

To migrate historical or demo JSON metadata files from `storage_data/metadata/*.json` into PostgreSQL, Kagaz provides an idempotent CLI migration tool:

```bash
# Preview records to be migrated (dry-run mode):
python backend/scripts/migrate_json_metadata.py --dry-run

# Run migration with custom defaults:
python backend/scripts/migrate_json_metadata.py \
    --storage-dir storage_data \
    --default-org dev_org \
    --default-user dev_user
```

### Migration Script Features & Safety Guarantees:
1. **Authoritative Insertion**: Reads legacy JSON metadata files, validates document attributes, and writes records into `documents`, `extraction_runs`, and `extractions` tables.
2. **Preservation of Files**: Never modifies or deletes original JSON or binary files on disk.
3. **Idempotence**: Detects if a document ID already exists in the database and skips it without duplicating records or throwing constraint errors.
4. **Relational Linking**: Creates an initial `ExtractionRun` for legacy extraction data, linking every extracted field to the run and document.
5. **Dry-Run Capability**: `--dry-run` reports exact counts of documents and extractions to migrate without writing to the database.

---

## 8. Running Tests

Database unit tests run with SQLite in-memory engines (`PRAGMA foreign_keys=ON`) and do not require a running PostgreSQL instance. When running against PostgreSQL, provide `DATABASE_URL` in the environment.

### Run DB-03 Persistence Test Suite:

```bash
python -m pytest backend/tests/test_db03_postgresql_persistence.py -v
```

### Run All Database Tests:

```bash
python -m pytest backend/tests/test_document_metadata.py backend/tests/test_extraction.py backend/tests/test_db03_postgresql_persistence.py -v
```

### Run Full Test Suite:

```bash
python -m pytest backend/tests -v
```

---

## 9. PostgreSQL vs. Storage Responsibilities

| Data | Storage Mechanism | Target PostgreSQL Table | Status |
|---|---|---|---|
| Uploaded binary files (PDF) | Local filesystem under `storage_data/<document_id>.pdf` (S3 in production) | Referenced by `documents.storage_path` | Binaries in storage |
| Authoritative metadata | PostgreSQL | `documents` table | Fully integrated |
| Document processing & status | PostgreSQL | `documents.status`, `documents.processed_at` | Fully integrated (`UPLOADED`, `CLASSIFIED`, `EXTRACTED`, `FAILED`) |
| Extraction runs & history | PostgreSQL | `extraction_runs` table | Fully integrated |
| Extracted structured fields | PostgreSQL | `extractions` table | Fully integrated |
| JSON metadata sidecar | Local filesystem under `storage_data/metadata/<document_id>.json` | Deprecated / secondary sync | Retained for backward-compatible dev reads |
