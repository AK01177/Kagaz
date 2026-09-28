# Kagaz backend

FastAPI backend with a public health check, authenticated PDF uploads, and PDF text extraction. Requires Python 3.10 or newer.

## Setup

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:JWT_SECRET = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))")
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Interactive documentation: http://127.0.0.1:8000/docs. `GET /api/health` is public.

| Environment variable | Meaning | Default |
|---|---|---|
| `JWT_SECRET` | Shared HS256 signing secret, at least 32 bytes | Required for authenticated requests |
| `JWT_ISSUER` | Trusted token issuer | `kagaz` |
| `JWT_AUDIENCE` | Expected token audience | `kagaz-api` |
| `DOCUMENT_STORAGE_DIR` | Local storage directory | `storage_data`, relative to working directory |

Export variables before starting the server. `.env` files are not automatically loaded. Use a persistent secret shared with the trusted token issuer outside local testing.

## Upload API (BE-02)

`POST /api/documents` accepts a multipart field named `file` and an `Authorization: Bearer <token>` header. HTTP 201 returns `document_id`, `filename`, `file_type`, `status` (`UPLOADED`), and UTC `uploaded_at`.

Supports readable, unencrypted PDFs with at least one page, up to 10 MiB. DOCX and images from the broader requirements remain pending; the existing extraction service supports PDF only. Upload does not run extraction or classification.

The entire upload request is limited to 10 MiB plus 64 KiB for multipart headers,
boundaries and other fields. Incoming bytes are counted before reaching the
multipart parser, including when Content-Length is missing or inaccurate.
Oversized requests return 413 and partial parser files are closed. The separate
10 MiB file check remains in place after parsing.

Documents use generated IDs as filenames. Basic metadata is persisted in `storage_data/metadata/<document_id>.json`, including file size, storage path, submitter and organization. Identity comes from the verified token. Database integration and the document retrieval endpoint remain separate work.

Errors use `{"error": {"code": "...", "message": "..."}}`: invalid/missing files return 400, missing/invalid tokens 401, forbidden uploads 403, oversized files 413, unsupported types 415, malformed fields 422, storage failures 500, and missing authentication configuration 503.

## JWT integration

Upload verifies HS256 signature, expiry, issuer and audience. Required claims: `sub`, `exp`, `iat`, `iss`, `aud`, `role`, `organization_id`, `active`. Only `role: SUBMITTER` and `active: true` may upload. A trusted signing service must obtain these values from user records.

Login and the user database are not implemented. Active status comes from the signed claim, not a live database check; immediate account revocation needs future session/user integration. Use short-lived tokens. Never distribute the signing secret to frontend clients.

For local testing, open another PowerShell terminal in `backend` and set the same `JWT_SECRET` as the server. Generate a five-minute token and upload a PDF:

```powershell
$token = (..\.venv\Scripts\python.exe -c "import os,time,jwt; now=int(time.time()); print(jwt.encode({'sub':'local-user','organization_id':'local-org','role':'SUBMITTER','active':True,'iss':os.getenv('JWT_ISSUER','kagaz'),'aud':os.getenv('JWT_AUDIENCE','kagaz-api'),'iat':now,'exp':now+300},os.environ['JWT_SECRET'],algorithm='HS256'))")
curl.exe -H "Authorization: Bearer $token" -F "file=@invoice.pdf" http://127.0.0.1:8000/api/documents
```

## Tests

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Covers health, extraction, upload persistence, extraction compatibility, file validation, rollback, identity attribution and JWT rejection paths.
