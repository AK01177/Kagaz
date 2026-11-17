"""Run the policy-validation quality corpus against a live Kagaz API."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_CASES = ROOT / "docs" / "policy_validation_evaluation_cases.json"
DEFAULT_REPORT = ROOT / "docs" / "policy_validation_evaluation_report.json"


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validate_dataset(cases: list[dict[str, Any]]) -> None:
    ids = [case.get("case_id") for case in cases]
    if not cases or any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Cases must have unique, non-empty case_id values")
    valid = {"PASS", "FLAG", "FAIL", "NEEDS_HUMAN_REVIEW"}
    category_status = {
        "compliant": "PASS",
        "supported_concern": "FLAG",
        "non_compliant": "FAIL",
        "incomplete": "NEEDS_HUMAN_REVIEW",
        "ambiguous": "NEEDS_HUMAN_REVIEW",
    }
    policy_text_by_identity: dict[tuple[str, str | None], str] = {}
    for case in cases:
        if case.get("expected_status") not in valid:
            raise ValueError(f"Invalid expected_status in {case['case_id']}")
        expected_category_status = category_status.get(case.get("category"))
        if expected_category_status is None:
            raise ValueError(f"Invalid category in {case['case_id']}")
        if case["expected_status"] != expected_category_status:
            raise ValueError(f"Expected status does not match category in {case['case_id']}")
        if not isinstance(case.get("expected_violation"), bool):
            raise ValueError(f"expected_violation must be boolean in {case['case_id']}")
        if case["expected_violation"] != (case["category"] == "non_compliant"):
            raise ValueError(f"expected_violation does not match category in {case['case_id']}")
        for key in ("rationale", "expected_evidence", "policy", "document"):
            if not case.get(key):
                raise ValueError(f"Missing {key} in {case['case_id']}")
        policy = case["policy"]
        document = case["document"]
        if not isinstance(policy.get("name"), str) or not isinstance(policy.get("text"), str):
            raise ValueError(f"Policy name and text must be strings in {case['case_id']}")
        if not isinstance(document.get("extractions"), dict):
            raise ValueError(f"Document extractions must be an object in {case['case_id']}")
        if not isinstance(case["expected_evidence"], list) or not case["expected_evidence"]:
            raise ValueError(f"Expected evidence must be a non-empty list in {case['case_id']}")
        if policy.get("document_type") not in (None, document.get("document_type")):
            raise ValueError(f"Policy document_type does not match document in {case['case_id']}")
        identity = (policy["name"], policy.get("document_type"))
        previous_text = policy_text_by_identity.setdefault(identity, policy["text"])
        if previous_text != policy["text"]:
            raise ValueError(f"Policy text conflicts for policy identity {identity}")


def _call_validation(base_url: str, token: str, document_id: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/documents/{document_id}/validate-policy"
    request = urllib.request.Request(
        url,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _assess_grounding(result: dict[str, Any]) -> dict[str, Any]:
    citations = []
    for finding in result.get("findings", []):
        for source in finding.get("sources", []):
            quote = source.get("supporting_quote")
            excerpt = source.get("excerpt", "")
            verifiable = bool(quote and _normalized(quote) in _normalized(excerpt))
            citations.append({
                "finding_requirement": finding.get("requirement"),
                "status": finding.get("status"),
                "source": source,
                "quote_verifiable": verifiable,
            })
    verified = sum(citation["quote_verifiable"] for citation in citations)
    return {
        "source_count": len(citations),
        "verified_quote_count": verified,
        "grounding_rate": verified / len(citations) if citations else None,
        "citations": citations,
    }


def _evaluate_case(case: dict[str, Any], document_id: str, result: dict[str, Any]) -> dict[str, Any]:
    actual = result.get("status", "UNKNOWN")
    grounding = _assess_grounding(result)
    retrieved_text = _normalized(" ".join(
        source.get("excerpt", "")
        for finding in result.get("findings", [])
        for source in finding.get("sources", [])
    ))
    matched_evidence = [
        quote for quote in case["expected_evidence"]
        if _normalized(quote) in retrieved_text
    ]
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "document_id": document_id,
        "expected_status": case["expected_status"],
        "actual_status": actual,
        "outcome_correct": actual == case["expected_status"],
        "expected_violation": case["expected_violation"],
        "predicted_violation": actual == "FAIL",
        "false_positive": actual == "FAIL" and not case["expected_violation"],
        "false_negative": actual != "FAIL" and case["expected_violation"],
        "human_review_escalated": actual == "NEEDS_HUMAN_REVIEW",
        "rationale": case["rationale"],
        "expected_evidence": case["expected_evidence"],
        "matched_expected_evidence": matched_evidence,
        "missing_expected_evidence": [q for q in case["expected_evidence"] if q not in matched_evidence],
        "expected_evidence_recall": len(matched_evidence) / len(case["expected_evidence"]) if case["expected_evidence"] else None,
        "review_status": "PENDING",
        "reviewer_disposition": None,
        "resolution_or_limitation": None,
        "summary": result.get("summary"),
        "retrieval_outcome": result.get("retrieval_outcome"),
        "policy_versions": result.get("policy_versions", []),
        "findings": result.get("findings", []),
        "grounding": grounding,
        "execution_error": None,
    }


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(results)
    if not count:
        return {"case_count": 0}
    source_count = sum(item["grounding"]["source_count"] for item in results)
    verified_count = sum(item["grounding"]["verified_quote_count"] for item in results)
    return {
        "case_count": count,
        "outcome_correct": sum(item["outcome_correct"] for item in results),
        "outcome_accuracy": sum(item["outcome_correct"] for item in results) / count,
        "false_positives": sum(item["false_positive"] for item in results),
        "false_negatives": sum(item["false_negative"] for item in results),
        "human_review_escalations": sum(item["human_review_escalated"] for item in results),
        "human_review_escalation_rate": sum(item["human_review_escalated"] for item in results) / count,
        "source_citations": source_count,
        "verified_source_quotes": verified_count,
        "source_grounding_rate": verified_count / source_count if source_count else None,
        "expected_evidence_recall": (
            sum(len(item["matched_expected_evidence"]) for item in results)
            / sum(len(item["expected_evidence"]) for item in results)
            if sum(len(item["expected_evidence"]) for item in results) else None
        ),
        "execution_errors": sum(item["execution_error"] is not None for item in results),
    }


def _markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Policy validation evaluation report", "",
        f"- Dataset version: `{report['dataset_version']}`",
        f"- Run timestamp (UTC): `{report['run_timestamp']}`",
        f"- API base URL: `{report['api_base_url']}`",
        f"- Model: `{report['model']}`", "",
        "## Metrics", "",
        "| Measure | Result |", "|---|---:|",
        f"| Outcome accuracy | {metrics.get('outcome_correct', 0)}/{metrics['case_count']} ({_percent(metrics.get('outcome_accuracy'))}) |",
        f"| False positives | {metrics.get('false_positives', 0)} |",
        f"| False negatives | {metrics.get('false_negatives', 0)} |",
        f"| Human-review escalations | {metrics.get('human_review_escalations', 0)}/{metrics['case_count']} ({_percent(metrics.get('human_review_escalation_rate'))}) |",
        f"| Verified source quotes | {metrics.get('verified_source_quotes', 0)}/{metrics.get('source_citations', 0)} ({_percent(metrics.get('source_grounding_rate'))}) |",
        f"| Expected evidence retrieved | {_percent(metrics.get('expected_evidence_recall'))} |",
        f"| Execution errors | {metrics.get('execution_errors', 0)} |", "",
        "## Cases", "",
        "| Case | Expected | Actual | Correct | Retrieval | Review | Grounding |", "|---|---|---|---|---|---|---:|",
    ]
    for item in report["results"]:
        grounding = item["grounding"]["grounding_rate"]
        lines.append(
            f"| `{item['case_id']}` | {item['expected_status']} | {item['actual_status']} | "
            f"{'yes' if item['outcome_correct'] else 'NO'} | {item.get('retrieval_outcome') or 'error'} | "
            f"{'yes' if item['human_review_escalated'] else 'no'} | {_percent(grounding)} |"
        )
    lines.extend(["", "## Review notes", ""])
    errors = [item for item in report["results"] if item["execution_error"]]
    mismatches = [item for item in report["results"] if not item["outcome_correct"] and not item["execution_error"]]
    ungrounded = [
        item for item in report["results"]
        if item["grounding"]["source_count"] and item["grounding"]["grounding_rate"] != 1
    ]
    for heading, items, label in (("Execution errors", errors, "execution_error"), ("Outcome mismatches", mismatches, "actual_status"), ("Unverified citations", ungrounded, None)):
        lines.extend([f"### {heading}", ""])
        if not items:
            lines.extend(["None.", ""])
            continue
        for item in items:
            detail = item.get(label) if label else f"{item['grounding']['verified_quote_count']}/{item['grounding']['source_count']} citations verified"
            lines.append(f"- `{item['case_id']}`: {detail}")
        lines.append("")
    lines.extend(["## Detailed actual results", "", "Full findings, retrieved source excerpts, and verified supporting quotes are recorded in the adjacent JSON report.", ""])
    return "\n".join(lines)


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / ".env")
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("POLICY_EVAL_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--document-map", type=Path, required=True, help="JSON object mapping case_id to seeded document ID")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="JSON report path; Markdown is written beside it")
    parser.add_argument(
        "--model-label",
        default=os.getenv("POLICY_EVAL_MODEL_LABEL", "unspecified"),
        help="Model used by the API server, for recording in the report",
    )
    parser.add_argument("--local-dev-token", action="store_true", help="Create a reviewer token from backend/.env for local evaluation")
    parser.add_argument("--organization-id", default=os.getenv("POLICY_EVAL_ORGANIZATION_ID", "policy-validation-evaluation"))
    args = parser.parse_args()

    token = os.getenv("POLICY_EVAL_TOKEN")
    if not token and args.local_dev_token:
        try:
            from dotenv import load_dotenv

            load_dotenv(BACKEND / ".env")
            if str(BACKEND) not in sys.path:
                sys.path.insert(0, str(BACKEND))
            if str(ROOT / "scripts") not in sys.path:
                sys.path.insert(0, str(ROOT / "scripts"))
            from api.auth import create_access_token
            from seed_policy_validation_evaluation import evaluation_user_id

            token = create_access_token(
                evaluation_user_id(args.organization_id),
                role="REVIEWER",
                organization_id=args.organization_id,
            )
        except Exception as exc:
            parser.error(f"Could not create a local reviewer token: {exc}")
    if not token:
        parser.error("Set POLICY_EVAL_TOKEN or use --local-dev-token with a valid backend/.env JWT_SECRET")
    try:
        dataset = json.loads(args.cases.read_text(encoding="utf-8"))
        mapping = json.loads(args.document_map.read_text(encoding="utf-8"))
        cases = dataset["cases"]
        _validate_dataset(cases)
        missing = [case["case_id"] for case in cases if not mapping.get(case["case_id"])]
        if missing:
            raise ValueError("Missing document IDs for: " + ", ".join(missing))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Evaluation setup error: {exc}", file=sys.stderr)
        return 2

    results = []
    for case in cases:
        case_id = case["case_id"]
        document_id = mapping[case_id]
        print(f"Evaluating {case_id} ({document_id})...", flush=True)
        try:
            actual = _call_validation(args.base_url, token, document_id)
            results.append(_evaluate_case(case, document_id, actual))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            results.append({
                "case_id": case_id, "category": case["category"], "document_id": document_id,
                "expected_status": case["expected_status"], "actual_status": "ERROR",
                "outcome_correct": False, "expected_violation": case["expected_violation"],
                "predicted_violation": False, "false_positive": False,
                "false_negative": False, "human_review_escalated": False,
                "rationale": case["rationale"], "expected_evidence": case["expected_evidence"],
                "matched_expected_evidence": [], "missing_expected_evidence": case["expected_evidence"],
                "expected_evidence_recall": 0.0,
                "review_status": "PENDING", "reviewer_disposition": None,
                "resolution_or_limitation": None,
                "summary": None, "retrieval_outcome": None, "policy_versions": [], "findings": [],
                "grounding": {"source_count": 0, "verified_quote_count": 0, "grounding_rate": None, "citations": []},
                "execution_error": str(exc),
            })

    report = {
        "dataset_version": dataset.get("dataset_version"),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "api_base_url": args.base_url,
        "model": args.model_label,
        "metrics": _metrics(results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(f"JSON report: {args.output}")
    print(f"Markdown report: {markdown_path}")
    print(json.dumps(report["metrics"], indent=2))
    needs_attention = (
        report["metrics"].get("execution_errors")
        or report["metrics"].get("false_positives")
        or report["metrics"].get("false_negatives")
        or any(not item["outcome_correct"] for item in results)
        or any(
            item["grounding"]["source_count"]
            and item["grounding"]["grounding_rate"] != 1
            for item in results
        )
        or any(
            item.get("expected_evidence_recall") is not None
            and item["expected_evidence_recall"] < 1
            for item in results
        )
    )
    return 1 if needs_attention else 0


if __name__ == "__main__":
    raise SystemExit(main())
