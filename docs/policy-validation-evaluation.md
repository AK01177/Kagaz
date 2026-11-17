# Policy validation quality evaluation

The versioned corpus in [`policy_validation_evaluation_cases.json`](policy_validation_evaluation_cases.json)
contains nine synthetic policy/document pairs. It covers compliant, non-compliant,
incomplete, ambiguous, and supported-concern cases, including all four overall
API statuses (`PASS`, `FLAG`, `FAIL`, and `NEEDS_HUMAN_REVIEW`) plus
`MISSING_INFORMATION` findings for incomplete checks.
Each case states whether a policy violation is established, its rationale, and
policy evidence that retrieval should return. No real customer information is
used.

## Run against the live validator

Run the local corpus and scoring checks from the repository root with:

```powershell
python -m pytest backend/tests/test_policy_validation_evaluation.py -q
```

These checks validate the evaluation data and metric calculations. They do not
call the model or prove that retrieval and policy interpretation are accurate.

The evaluator calls `POST /api/documents/{document_id}/validate-policy`. The
seeder creates an isolated evaluation organization, reviewer membership,
synthetic document metadata, extracted values, active policy versions, and
policy chunks directly in the configured local database. It calls the OpenAI
embedding service for real policy vectors. The source documents are synthetic
metadata records; the validator reads the indexed chunk excerpts and does not
need a physical PDF for these cases. The default seed organization is
`policy-validation-evaluation`. If the requested organization ID already belongs
to a different organization, the seeder stops without changing that organization.

Configure `DATABASE_URL`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and
`JWT_SECRET` in `backend/.env`. `JWT_SECRET` must match the local API server and
be at least 32 bytes. Apply migrations and seed from the repository root:

```powershell
Set-Location backend
python -m alembic upgrade head
Set-Location ..
python scripts/seed_policy_validation_evaluation.py
```

Start the API in one terminal:

```powershell
Set-Location backend
python -m uvicorn main:app --reload --port 8000
```

In another terminal, run the evaluation. `--local-dev-token` creates a reviewer
token from `backend/.env` without printing it. It is intended only for local use.

```powershell
python scripts/evaluate_policy_validation.py `
  --base-url http://127.0.0.1:8000 `
  --document-map .\backend\storage_data\policy-validation-evaluation-document-map.json `
  --model-label "<model configured on API server>" `
  --local-dev-token
```

To preserve multiple runs, pass a unique `--output` path for each run.

For an existing environment, provide a reviewer bearer token in
`POLICY_EVAL_TOKEN` and a document map to use those records instead of the local
seed data. Do not commit credentials or production document IDs.

The generated document map looks like:

```json
{
  "invoice-compliant": "<seeded-document-id>",
  "invoice-advisory-review": "<seeded-document-id>",
  "invoice-noncompliant": "<seeded-document-id>",
  "invoice-incomplete": "<seeded-document-id>",
  "invoice-ambiguous-currency": "<seeded-document-id>",
  "expense-compliant": "<seeded-document-id>",
  "expense-noncompliant": "<seeded-document-id>",
  "expense-incomplete": "<seeded-document-id>",
  "expense-ambiguous-receipt-availability": "<seeded-document-id>"
}
```

For a separately seeded environment, set `POLICY_EVAL_TOKEN` to a reviewer
bearer token and provide its document map:

```powershell
$env:POLICY_EVAL_TOKEN = "<reviewer-token>"
python scripts/evaluate_policy_validation.py `
  --base-url http://127.0.0.1:8000 `
  --document-map .\policy-validation-document-map.local.json
```

The runner writes a detailed JSON report and a Markdown summary next to the
configured output path. Use `--output` to preserve a run under a distinct name.
Set `--model-label` to the model configured on the API server so each report
records the model actually used; the runner cannot infer that from its own
environment.
The JSON report retains every raw validation response: status, summary, findings,
policy/version identities, retrieval outcome, source excerpts, and supporting
quotes. It also records the dataset version, run time, API URL, and configured
model label. API and setup errors are reported as errors, not as successful
evaluations.

## Metrics

- **Outcome accuracy:** exact match between expected and actual overall status.
- **False positive:** the validator returns `FAIL` for a case not labeled as a
  confirmed violation.
- **False negative:** a confirmed violation case returns any status other than
  `FAIL`.
- **Human-review escalation:** share of cases with overall status
  `NEEDS_HUMAN_REVIEW`.
- **Source-quote grounding:** share of returned source citations whose supporting
  quote is present in that source excerpt after whitespace/case normalization.
- **Expected evidence recall:** share of case-specific expected evidence phrases
  present in excerpts returned with findings. This is a simple lexical check and
  should be reviewed when equivalent wording is used.

Review every status mismatch, false positive, false negative, and unverified
quote in the JSON report. Record the reviewer disposition and any prompt, model,
policy-index, or retrieval change alongside the report when comparing runs.

## Limitations

This is a small, synthetic, English-language regression set. It does not measure
real-world distribution, policy authoring quality, OCR/extraction accuracy, or
human reviewer agreement. The API runner measures the complete live path only
when the mapped documents and active policy versions accurately reproduce the
corpus. Expected-evidence recall uses literal phrase matching; source-quote
verification checks citation containment but does not establish that the model's
interpretation is logically correct. Expand and periodically adjudicate the set
with domain reviewers before using metrics as a release gate.
