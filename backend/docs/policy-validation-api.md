# Policy validation API

`POST /api/documents/{document_id}/validate-policy` evaluates persisted extraction fields against relevant active policy evidence for the authenticated user's organization. It requires a bearer token accepted by the policy-reader role dependency. A document belonging to another organization is returned as not found.

Each call creates and persists a new validation run. It does not alter the document lifecycle or approval state. The run records its requester, status, retrieval outcome, timestamp, and the policy/version identities retrieved. Findings retain their explanations and source chunk references, including source document, version, page, section, excerpt, and a supporting quote copied from that excerpt.

## Result shape

The response contains `id`, `document_id`, `status`, `summary`, `retrieval_outcome`, `policy_versions`, `findings`, and `created_at`. Each finding contains `id`, `status`, `requirement`, `explanation`, optional `field_name`, `document_value`, and `confidence`, plus a `sources` array. Policy source entries include `supporting_quote`, which is checked against the stored chunk excerpt.

Overall statuses are `PASS`, `FLAG`, `FAIL`, and `NEEDS_HUMAN_REVIEW`. Finding statuses also include `MISSING_INFORMATION`. Missing or low-confidence extracted information is not by itself a confirmed violation. A confirmed `FAIL` requires policy-supported evidence. Ambiguous, conflicting, unavailable, or unverified cases require human review.

Validation considers active, role-accessible, AI-11 chunk-indexed policies for the document's organization. A policy with no `document_type` applies generally and is included alongside matching document-type policies. Policies created or edited through the separate policy CRUD API must be ingested/indexed into AI-11 before this validator can use them. The complete accessible chunk scope is evaluated when it fits within the configured limits; if it is too large, the endpoint returns `NEEDS_HUMAN_REVIEW` instead of silently evaluating only a partial top-k result. The defaults are 40 chunks and 50,000 characters, configurable with `POLICY_VALIDATION_MAX_CHUNKS` and `POLICY_VALIDATION_MAX_CONTEXT_CHARS`.

If an active applicable policy lacks indexed chunks, relevant evidence cannot be retrieved or interpreted, any retrieved chunk is not covered by a quoted check, findings conflict, or the document classification is missing, the endpoint returns a persisted `NEEDS_HUMAN_REVIEW` run and does not infer a final decision. A `FAIL` must identify a persisted field/value and a verified policy quote. Confidence review threshold defaults to `0.7` and can be configured with `POLICY_VALIDATION_CONFIDENCE_THRESHOLD`. The interpretation model uses `POLICY_VALIDATION_MODEL`, falling back to `EXTRACTION_MODEL`; credentials use `OPENROUTER_API_KEY`, `JEV_API_KEY`, or `TYPESAFE_API_KEY`.

Validation runs are persisted for audit, but this release does not expose run-history retrieval.
