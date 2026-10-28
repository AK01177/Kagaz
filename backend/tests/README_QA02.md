# QA-02 — Backend Unit Tests (Merged Into Existing Suite)

Issue: [#33 — QA-02: Unit Tests](https://github.com/AK01177/Kagaz/issues/33)

## Goal

Add isolated unit-test coverage for core backend functions without duplicating or replacing existing test modules. All additions are inside the established `backend/tests/` directory. No application source code was changed.

## Updated test files

| Existing module | New unit-test coverage |
|---|---|
| `test_upload.py` | Direct upload-service persistence, filename and format validation, upload limits, classification/extraction failure behavior, metadata rollback |
| `test_extraction.py` | Pure text normalization, mocked PDF pages, scanned-PDF OCR fallback, OCR failure translation, storage path lookup and ID isolation |
| `test_classification.py` | Nested and flat classification response parsing, malformed payloads, confidence precedence/boundaries, category normalization |
| `test_document_metadata.py` | Required metadata fields, UUID validation, positive file size, status and confidence bounds |

The API-level and database-level tests already in those modules remain in place. The QA-02 tests exercise individual functions using `pytest` fixtures and mocks, without live AI requests or a PostgreSQL server.

## Run tests

From the repository root:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest tests/test_upload.py tests/test_extraction.py tests/test_classification.py tests/test_document_metadata.py -v
python -m pytest tests/ -v
```

Existing API/integration failures may still require independent investigation; adding unit tests does not repair application code.

## QA-02 acceptance criteria

- **Core components covered:** upload, storage, extraction, classification parsing, and document metadata.
- **Success and failure scenarios:** valid inputs, malformed files, out-of-range values, missing resources, and simulated service failures.
- **Independent execution:** temporary directories, mocked dependencies, and parametrized validation tests.
- **Clear failure identification:** descriptive `test_...` names within each existing component's test module.
- **Included in project suite:** all changes are in the existing `backend/tests/` directory and discovered by `pytest`.

## Verification

The 70 new QA-02 test cases were run in an isolated local validation environment: **70 passed**. The original Kagaz full backend test suite has **not** been run as part of preparing this merge. Record full-suite results before marking the issue completed.

## Commit

```bash
git add backend/tests/test_upload.py backend/tests/test_extraction.py backend/tests/test_classification.py backend/tests/test_document_metadata.py backend/tests/README_QA02.md
git commit -m "test: add backend unit tests"
```
