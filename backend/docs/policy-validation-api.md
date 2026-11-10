# Policy validation API

`POST /api/documents/{document_id}/validate-policy` evaluates persisted extraction fields against relevant active policy evidence for the authenticated user's organization. It requires a bearer token accepted by the policy-reader role dependency. A document belonging to another organization is returned as not found.

Each call creates and persists a new validation run. It does not alter the document lifecycle or approval state. The run records its requester, status, retrieval outcome, timestamp, and the policy/version identities retrieved. Findings retain their explanations and source chunk references, including source document, version, page, section, and excerpt.

## Result shape

The response contains `id`, `document_id`, `status`, `summary`, `retrieval_outcome`, `policy_versions`, `findings`, and `created_at`. Each finding contains `id`, `status`, `requirement`, `explanation`, optional `field_name`, `document_value`, and `confidence`, plus a `sources` array.

Overall statuses are `PASS`, `FLAG`, `FAIL`, and `NEEDS_HUMAN_REVIEW`. Finding statuses also include `MISSING_INFORMATION`. Missing or low-confidence extracted information is not by itself a confirmed violation. A confirmed `FAIL` requires policy-supported evidence. Ambiguous, conflicting, unavailable, or unverified cases require human review.

If relevant policy evidence cannot be retrieved or interpreted, the endpoint returns a persisted `NEEDS_HUMAN_REVIEW` run and does not infer violations. Confidence review threshold defaults to `0.7` and can be configured with `POLICY_VALIDATION_CONFIDENCE_THRESHOLD`. The interpretation model uses `POLICY_VALIDATION_MODEL`, falling back to `EXTRACTION_MODEL`; credentials use `OPENROUTER_API_KEY`, `JEV_API_KEY`, or `TYPESAFE_API_KEY`.

Validation runs are persisted for audit, but this release does not expose run-history retrieval.
