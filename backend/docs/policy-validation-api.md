# Policy validation API

`POST /api/documents/{document_id}/validate-policy` evaluates persisted extraction fields against the applicable policy clauses of the authenticated user's organization. A document belonging to another organization is refused.

Each call creates and persists a new validation run. It does not alter the document lifecycle or approval state. The run records its requester, status, retrieval outcome, timestamp, and the policy/version identities it used. Findings retain their explanations and source references, including source document, version, page, section, excerpt, and a supporting quote copied from that excerpt.

## Result shape

The response contains `id`, `document_id`, `status`, `summary`, `retrieval_outcome`, `policy_versions`, `findings`, and `created_at`. Each finding contains `id`, `status`, `requirement`, `explanation`, optional `field_name`, `document_value`, and `confidence`, plus a `sources` array. Policy source entries include `supporting_quote`, which is verified against the stored clause text.

Overall statuses are `PASS`, `FLAG`, `FAIL`, and `NEEDS_HUMAN_REVIEW`. Finding statuses also include `MISSING_INFORMATION`. Missing or low-confidence extracted information is not by itself a confirmed violation. Precedence of the overall status: any item needing human review wins, then `FAIL`, then `FLAG`, then `PASS`. The result is never an approval or rejection: people decide.

## Which policies apply

Only active policies the caller's role may read, for the document's organization, are considered, and only a policy's ACTIVE version. A policy applies when its `document_type` matches the document's classification, or when it has no `document_type` (it applies to every type). Types are the classifier's four categories (`academics`, `hr_documents`, `financial`, `general_confidential`); policies may be written with any spelling the classifier understands ("Invoice", "HR Forms", "hr-documents") and are stored in canonical form. An unclassified document is checked only against policies for every type and always needs review.

## How the clauses are chosen (`retrieval_outcome`)

| Value | Meaning |
|---|---|
| `full_scope` | Every applicable clause fits (25 or fewer), so the model saw all of them. |
| `relevant_subset` | The applicable policies are larger, so the model saw the (at most 30) clauses most relevant to this document, found with one search per extracted field. The summary says so. |
| `no_applicable_policies` | No active policy applies to the document's type. |
| `unindexed_policy_evidence` | Policies apply but none is searchable yet. |
| `no_extractions` | The document has no extracted fields. |
| `unavailable` | The embedding service could not be reached. |

An applicable policy that cannot be searched (not indexed, or indexed with an older embedding model) is reported as its own `NEEDS_HUMAN_REVIEW` finding named "Policy not checked: ..." and listed in `policy_versions` with `index_status: NOT_SEARCHABLE`. The other policies are still checked and their findings kept.

## What is verified in code

The language model proposes findings; the service decides what to trust.

* A citation counts only if every cited clause was supplied, has a quote, and the quote appears verbatim (ignoring case and spacing) in that clause. Otherwise the finding becomes `NEEDS_HUMAN_REVIEW`.
* A `FAIL` must name a stored field and its value (compared as text or as numbers, so `740` equals `740.00`), and the extracted value must be at or above the confidence threshold.
* The same requirement judged both `PASS` and `FAIL` is sent to review.
* Every supplied clause must be either cited by a finding or declared irrelevant to this document by the model; otherwise a coverage finding blocks `PASS`. Dismissed clauses are counted in the summary.
* A model that returns no checks cannot imply `PASS`. If the model is unavailable or answers unusably, the run is `NEEDS_HUMAN_REVIEW` and the retrieved clauses are still shown.

## Configuration

`GEMINI_API_KEY` is used for both embeddings and the model (`GEMINI_EMBEDDING_MODEL`, `GEMINI_CHAT_MODEL`). The confidence review threshold defaults to `0.7` (`POLICY_VALIDATION_CONFIDENCE_THRESHOLD`). Rate limits and outages are retried automatically.

Validation runs are persisted for audit, but this release does not expose run-history retrieval.
