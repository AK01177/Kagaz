"""
BE-14: Document and Policy Assistant Service.

Provides a protected question-answering assistant for accessible documents
and their applicable organization policies.

Core guarantees:
1. Strict authorization & tenant isolation: Only authorized users can query
   documents in their organization. Cross-org documents return 404.
2. Grounded answers & source citations: Every factual response cites specific
   document fields or policy clauses.
3. Unsupported questions: Questions outside document/policy context receive a
   clear limitation response.
4. No workflow side effects: The assistant is strictly read-only and cannot
   approve, reject, or transition document states.
5. Rate limiting: Enforces request limits per user/organization.
6. Provider resilience: Gracefully handles embedding or LLM service failures.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from typing import Any, List, Optional, Tuple

import httpx
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.extraction import Extraction
from app.models.policy import Policy, PolicyChunk, PolicyVersion, PolicyVersionStatus
from app.models.policy_validation import PolicyValidationRun
from app.schemas.assistant import AssistantQueryResponse, AssistantSourceReference
from services.policy_retrieval import (
    EmbeddingServiceError,
    create_query_embedding,
    retrieve_policy_evidence,
)

logger = logging.getLogger(__name__)

# Request rate limiting: max 30 requests per 60 seconds per user
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 30
_REQUEST_HISTORY: dict[str, deque[float]] = defaultdict(deque)

WORKFLOW_ACTION_PATTERNS = [
    re.compile(r"\b(approve|reject|accept|deny|sign off)\b.*\b(document|this|it)\b", re.IGNORECASE),
    re.compile(r"\b(change|transition|move|set)\b.*\b(status|state|workflow)\b", re.IGNORECASE),
    re.compile(r"\b(request changes|resubmit|assign reviewer)\b", re.IGNORECASE),
]


def _check_rate_limit(organization_id: str, user_id: str) -> None:
    """Sliding-window rate limiter per (organization_id, user_id)."""
    key = f"{organization_id}:{user_id}"
    now = time.time()
    if key not in _REQUEST_HISTORY or not isinstance(_REQUEST_HISTORY[key], deque):
        _REQUEST_HISTORY[key] = deque()
    queue = _REQUEST_HISTORY[key]

    while queue and queue[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        queue.popleft()

    if len(queue) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "ASSISTANT_RATE_LIMIT_EXCEEDED",
                "message": "Assistant request rate limit exceeded. Please wait a moment before asking again.",
            },
        )
    queue.append(now)


def check_document_access(document: Optional[Document], actor: dict) -> Document:
    """
    Verify document accessibility and role permissions.
    Cross-tenant documents return 404 to avoid leaking existence.
    """
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found."},
        )

    actor_org = str(actor.get("organization_id") or "").strip()
    if document.organization_id != actor_org:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found."},
        )

    if not actor.get("active", False):
        raise HTTPException(
            status_code=403,
            detail={"code": "ASSISTANT_FORBIDDEN", "message": "An active account is required."},
        )

    actor_id = str(actor.get("sub") or "").strip()
    actor_role = str(actor.get("role") or "").strip().upper()

    # Submitter may only ask questions about their own uploaded documents
    if actor_role == "SUBMITTER" and document.uploaded_by != actor_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ASSISTANT_FORBIDDEN",
                "message": "Submitters may only query documents they uploaded.",
            },
        )

    return document


def _detect_workflow_intent(question: str) -> bool:
    """Check if the user is asking the assistant to take workflow actions."""
    return any(pattern.search(question) for pattern in WORKFLOW_ACTION_PATTERNS)


def _lexical_policy_search(
    db: Session,
    organization_id: str,
    keywords: list[str],
    limit: int = 5,
) -> list[Tuple[Policy, PolicyVersion, PolicyChunk]]:
    """Fallback lexical keyword search for policy chunks when embedding service is unavailable."""
    if not keywords:
        return []

    conditions = []
    for kw in keywords[:5]:
        kw_pattern = f"%{kw}%"
        conditions.append(PolicyChunk.content.ilike(kw_pattern))
        conditions.append(Policy.name.ilike(kw_pattern))
        conditions.append(Policy.domain.ilike(kw_pattern))

    return (
        db.query(Policy, PolicyVersion, PolicyChunk)
        .join(PolicyVersion, PolicyVersion.policy_id == Policy.id)
        .join(PolicyChunk, PolicyChunk.policy_version_id == PolicyVersion.id)
        .filter(
            Policy.organization_id == organization_id,
            Policy.is_active.is_(True),
            PolicyVersion.status == PolicyVersionStatus.ACTIVE,
            or_(*conditions),
        )
        .limit(limit)
        .all()
    )


def query_document_assistant(
    db: Session,
    document_id: str,
    question: str,
    actor: dict,
) -> AssistantQueryResponse:
    """
    Process an assistant query about a document and its applicable policies.

    Enforces organization scope, role access, and request limits without any
    workflow side effects.
    """
    org_id = str(actor.get("organization_id") or "").strip()
    user_id = str(actor.get("sub") or "").strip()

    # Rate limiting
    _check_rate_limit(org_id, user_id)

    # Document retrieval and access check
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.organization_id == org_id)
        .first()
    )
    document = check_document_access(doc, actor)

    cleaned_question = question.strip()

    # Guard: workflow manipulation requests
    if _detect_workflow_intent(cleaned_question):
        return AssistantQueryResponse(
            document_id=document.id,
            question=cleaned_question,
            answer=(
                "The assistant is an advisory informational tool and cannot approve, "
                "reject, or modify document workflow status. Workflow decisions must be "
                "made through authorized review and approval actions."
            ),
            sources=[],
            is_grounded=False,
            limitation="Workflow state modifications are not permitted via the assistant.",
            confidence=1.0,
        )

    # 1. Fetch document extractions
    extractions = (
        db.query(Extraction)
        .filter(Extraction.document_id == document.id)
        .order_by(Extraction.field_name.asc())
        .all()
    )

    # 2. Fetch latest validation findings if any
    latest_val = (
        db.query(PolicyValidationRun)
        .filter(
            PolicyValidationRun.document_id == document.id,
            PolicyValidationRun.organization_id == org_id,
        )
        .order_by(PolicyValidationRun.created_at.desc())
        .first()
    )

    # 3. Retrieve relevant policies (semantic vector search with lexical fallback)
    policy_sources: list[AssistantSourceReference] = []
    policy_context_texts: list[str] = []

    try:
        embedding = create_query_embedding(cleaned_question)
        retrieval = retrieve_policy_evidence(
            db,
            organization_id=org_id,
            role=actor.get("role", "SUBMITTER"),
            embedding=embedding,
            domain=None,
            document_type=document.classification,
            policy_version=None,
            limit=5,
        )
        for policy, version, chunk, score, source_doc in retrieval.rows:
            policy_sources.append(
                AssistantSourceReference(
                    source_type="POLICY_CHUNK",
                    title=f"Policy: {policy.name} ({version.version})",
                    reference=f"{policy.name} - Section: {chunk.section or 'General'}",
                    excerpt=chunk.content[:400],
                    policy_id=policy.id,
                    policy_name=policy.name,
                    policy_version=version.version,
                    page_number=chunk.page_number,
                    section=chunk.section,
                )
            )
            policy_context_texts.append(f"[{policy.name} {version.version}] {chunk.content}")
    except (EmbeddingServiceError, Exception) as exc:
        logger.debug("Semantic policy retrieval skipped (%s); trying lexical fallback", exc)
        words = [w for w in re.findall(r"\b\w{3,}\b", cleaned_question.lower()) if w not in {"the", "and", "for", "with", "this", "what"}]
        lex_rows = _lexical_policy_search(db, org_id, words, limit=4)
        for policy, version, chunk in lex_rows:
            policy_sources.append(
                AssistantSourceReference(
                    source_type="POLICY_CHUNK",
                    title=f"Policy: {policy.name} ({version.version})",
                    reference=f"{policy.name} - Section: {chunk.section or 'General'}",
                    excerpt=chunk.content[:400],
                    policy_id=policy.id,
                    policy_name=policy.name,
                    policy_version=version.version,
                    page_number=chunk.page_number,
                    section=chunk.section,
                )
            )
            policy_context_texts.append(f"[{policy.name} {version.version}] {chunk.content}")

    # Document field sources
    doc_sources: list[AssistantSourceReference] = []
    doc_field_map: dict[str, str] = {}
    for ext in extractions:
        doc_field_map[ext.field_name] = ext.value
        doc_sources.append(
            AssistantSourceReference(
                source_type="DOCUMENT_FIELD",
                title=f"Document Field: {ext.field_name}",
                reference=f"Extracted field '{ext.field_name}'",
                excerpt=f"{ext.field_name}: {ext.value}",
            )
        )

    # 4. Try LLM answering if provider is configured
    api_key = (
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("JEV_API_KEY")
        or os.getenv("TYPESAFE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    if api_key:
        try:
            llm_response = _call_llm_assistant(
                api_key=api_key,
                question=cleaned_question,
                document=document,
                extractions=extractions,
                policy_context=policy_context_texts,
            )
            if llm_response:
                # Merge sources
                all_sources = doc_sources + policy_sources
                relevant_sources = _filter_relevant_sources(llm_response.get("cited_keys", []), all_sources)
                return AssistantQueryResponse(
                    document_id=document.id,
                    question=cleaned_question,
                    answer=llm_response["answer"],
                    sources=relevant_sources or all_sources[:4],
                    is_grounded=llm_response.get("is_grounded", True),
                    limitation=llm_response.get("limitation"),
                    confidence=llm_response.get("confidence", 0.9),
                )
        except Exception as exc:
            logger.warning("LLM assistant invocation failed (%s); using grounded fallback", exc)

    # 5. Deterministic Grounded Fallback
    return _grounded_heuristic_fallback(
        cleaned_question,
        document=document,
        extractions=extractions,
        doc_sources=doc_sources,
        policy_sources=policy_sources,
        validation_run=latest_val,
    )


def _call_llm_assistant(
    api_key: str,
    question: str,
    document: Document,
    extractions: list[Extraction],
    policy_context: list[str],
) -> Optional[dict[str, Any]]:
    """Invoke LLM for grounded document/policy reasoning."""
    context_data = {
        "document": {
            "filename": document.filename,
            "classification": document.classification,
            "status": document.status.value,
        },
        "extracted_fields": {ext.field_name: ext.value for ext in extractions},
        "policy_clauses": policy_context,
    }

    prompt = (
        "You are an assistant for a document and policy verification system. "
        "Answer the question based STRICTLY and ONLY on the provided document extractions and policy clauses. "
        "If the answer cannot be determined from the provided context, state that clearly and set is_grounded to false.\n"
        "Return valid JSON with keys:\n"
        "- answer: string (concise, factual answer)\n"
        "- is_grounded: boolean (true if answer is fully supported by context, false otherwise)\n"
        "- limitation: string or null (explanation if context was insufficient)\n"
        "- confidence: float between 0.0 and 1.0\n"
        "- cited_keys: list of strings (field names or policy names cited in the answer)\n"
    )

    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-OpenRouter-Title": "Kagaz Assistant",
        },
        json={
            "model": os.getenv("ASSISTANT_MODEL", os.getenv("EXTRACTION_MODEL", "meta-llama/llama-3.3-70b-instruct")),
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Context:\n{json.dumps(context_data)}\n\nQuestion: {question}",
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=15.0,
    )
    response.raise_for_status()
    raw_content = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw_content)


def _filter_relevant_sources(
    cited_keys: list[str],
    all_sources: list[AssistantSourceReference],
) -> list[AssistantSourceReference]:
    """Filter sources list to those cited by the LLM."""
    if not cited_keys:
        return []
    cited_lower = {k.lower() for k in cited_keys}
    matched = [
        s for s in all_sources
        if any(c in s.title.lower() or c in s.reference.lower() for c in cited_lower)
    ]
    return matched


def _grounded_heuristic_fallback(
    question: str,
    document: Document,
    extractions: list[Extraction],
    doc_sources: list[AssistantSourceReference],
    policy_sources: list[AssistantSourceReference],
    validation_run: Optional[PolicyValidationRun],
) -> AssistantQueryResponse:
    """
    Factual deterministic matcher when LLM is unavailable or for testing environments.
    Matches extracted fields, validation findings, and policy clauses.
    """
    q_lower = question.lower()

    # 1. Check document status / classification query
    if "status" in q_lower or "lifecycle" in q_lower:
        return AssistantQueryResponse(
            document_id=document.id,
            question=question,
            answer=f"The current status of document '{document.filename}' is {document.status.value}.",
            sources=[
                AssistantSourceReference(
                    source_type="DOCUMENT_FIELD",
                    title="Document Lifecycle Status",
                    reference="documents.status",
                    excerpt=f"status: {document.status.value}",
                )
            ],
            is_grounded=True,
            confidence=1.0,
        )

    if "classification" in q_lower or "type of document" in q_lower or "doc type" in q_lower:
        cls_val = document.classification or "Unclassified"
        return AssistantQueryResponse(
            document_id=document.id,
            question=question,
            answer=f"Document '{document.filename}' is classified as {cls_val}.",
            sources=[
                AssistantSourceReference(
                    source_type="DOCUMENT_FIELD",
                    title="Document Classification",
                    reference="documents.classification",
                    excerpt=f"classification: {cls_val}",
                )
            ],
            is_grounded=True,
            confidence=1.0,
        )

    # 2. Check for extracted field matches
    matched_extractions: list[Tuple[Extraction, AssistantSourceReference]] = []
    for ext, src in zip(extractions, doc_sources):
        field_tokens = ext.field_name.lower().replace("_", " ").split()
        if ext.field_name.lower() in q_lower or any(token in q_lower for token in field_tokens if len(token) > 2):
            matched_extractions.append((ext, src))

    if matched_extractions:
        field_answers = [f"• {ext.field_name.replace('_', ' ').title()}: {ext.value}" for ext, _ in matched_extractions]
        sources = [src for _, src in matched_extractions]
        return AssistantQueryResponse(
            document_id=document.id,
            question=question,
            answer=f"Based on the extracted document fields:\n" + "\n".join(field_answers),
            sources=sources,
            is_grounded=True,
            confidence=0.95,
        )

    # 3. Check for policy matches
    if policy_sources:
        best_policy_match = policy_sources[0]
        return AssistantQueryResponse(
            document_id=document.id,
            question=question,
            answer=(
                f"Applicable policy requirement from '{best_policy_match.title}': "
                f"{best_policy_match.excerpt}"
            ),
            sources=[best_policy_match],
            is_grounded=True,
            confidence=0.85,
        )

    # 4. Check validation findings
    if validation_run and validation_run.findings:
        finding = validation_run.findings[0]
        return AssistantQueryResponse(
            document_id=document.id,
            question=question,
            answer=(
                f"Validation findings for this document: Status is {validation_run.status}. "
                f"Finding: {finding.explanation}"
            ),
            sources=[
                AssistantSourceReference(
                    source_type="VALIDATION_FINDING",
                    title=f"Validation Check: {finding.requirement}",
                    reference="policy_validation_findings",
                    excerpt=f"Status: {finding.status}. {finding.explanation}",
                )
            ],
            is_grounded=True,
            confidence=0.9,
        )

    # 5. Unsupported question / insufficient context
    return AssistantQueryResponse(
        document_id=document.id,
        question=question,
        answer=(
            "I do not have sufficient information in this document or its applicable "
            "organization policies to answer your question. Please consult an authorized reviewer."
        ),
        sources=[],
        is_grounded=False,
        limitation="The question asks for information not present in the document extractions or applicable policies.",
        confidence=0.0,
    )
