"""Unit coverage for the policy-validation evaluation corpus and scoring."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIRECTORY = REPOSITORY_ROOT / "scripts"
for import_path in (str(REPOSITORY_ROOT), str(SCRIPT_DIRECTORY)):
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)

from evaluate_policy_validation import (  # noqa: E402
    _evaluate_case,
    _metrics,
    _validate_dataset,
)
from seed_policy_validation_evaluation import (  # noqa: E402
    _collect_policy_specs,
    _evaluation_identity,
    evaluation_user_id,
)


def test_corpus_covers_required_categories_and_validates() -> None:
    corpus_path = REPOSITORY_ROOT / "docs" / "policy_validation_evaluation_cases.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))

    _validate_dataset(corpus["cases"])

    assert {case["category"] for case in corpus["cases"]} == {
        "compliant", "non_compliant", "incomplete", "ambiguous", "supported_concern"
    }
    assert all(case["rationale"] and case["expected_evidence"] for case in corpus["cases"])
    assert len(_collect_policy_specs(corpus["cases"])) == 3
    reviewer_id = evaluation_user_id("policy-validation-evaluation")
    assert str(uuid.UUID(reviewer_id)) == reviewer_id
    assert reviewer_id != evaluation_user_id("another-evaluation-org")
    assert _evaluation_identity("policy-validation-evaluation")[0] == reviewer_id


def test_outcome_and_citation_scoring() -> None:
    case = {
        "case_id": "test-fail", "category": "non_compliant", "expected_status": "FAIL",
        "expected_violation": True, "rationale": "A policy limit is exceeded.",
        "expected_evidence": ["Amount must not exceed USD 100"],
    }
    actual = {
        "status": "FAIL", "summary": "Limit exceeded.", "retrieval_outcome": "results",
        "policy_versions": [{"version": "v1"}],
        "findings": [{
            "status": "FAIL", "requirement": "Amount limit", "explanation": "Over limit.",
            "sources": [{
                "excerpt": "Expenses: Amount must not exceed USD 100.",
                "supporting_quote": "Amount must not exceed USD 100",
            }],
        }],
    }

    assessed = _evaluate_case(case, "doc-1", actual)

    assert assessed["outcome_correct"] is True
    assert assessed["false_positive"] is False
    assert assessed["false_negative"] is False
    assert assessed["grounding"]["grounding_rate"] == 1.0
    assert assessed["expected_evidence_recall"] == 1.0
    assert assessed["review_status"] == "PENDING"


def test_metrics_count_false_positive_false_negative_and_escalation() -> None:
    cases = [
        {"case_id": "fp", "category": "compliant", "expected_status": "PASS", "expected_violation": False,
         "rationale": "Complies.", "expected_evidence": ["Rule" ]},
        {"case_id": "fn", "category": "non_compliant", "expected_status": "FAIL", "expected_violation": True,
         "rationale": "Violates.", "expected_evidence": ["Rule"]},
        {"case_id": "review", "category": "incomplete", "expected_status": "NEEDS_HUMAN_REVIEW", "expected_violation": False,
         "rationale": "Incomplete.", "expected_evidence": ["Rule"]},
    ]
    actual_statuses = ["FAIL", "PASS", "NEEDS_HUMAN_REVIEW"]
    results = []
    for case, status in zip(cases, actual_statuses):
        results.append(_evaluate_case(case, case["case_id"], {"status": status, "findings": []}))

    metrics = _metrics(results)

    assert metrics["case_count"] == 3
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["human_review_escalations"] == 1
    assert metrics["outcome_correct"] == 1


def test_dataset_rejects_duplicate_case_ids() -> None:
    case = {
        "case_id": "duplicate", "category": "compliant", "expected_status": "PASS",
        "expected_violation": False, "rationale": "ok",
        "expected_evidence": ["Policy"], "policy": {"name": "p"}, "document": {"document_type": "invoice"},
    }

    try:
        _validate_dataset([case, case])
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate case IDs should be rejected")
