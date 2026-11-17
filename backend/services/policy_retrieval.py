import os
import re
from dataclasses import dataclass, field

from sqlalchemy import case, func, literal, or_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.policy import (
    Policy,
    PolicyClassification,
    PolicyChunk,
    PolicyVersion,
    PolicyVersionStatus,
)
from services.document_types import document_type_spellings
from services.embeddings import (  # noqa: F401  (re-exported: callers import them from here)
    EMBEDDING_MODEL,
    EmbeddingServiceError,
    create_embeddings,
    create_query_embedding,
)


# Minimum cosine similarity for a chunk to count as evidence. Calibrated on the evaluation set
# (tests/rag_eval): unrelated questions score up to 0.53 and genuine answers start at 0.65, so
# 0.55 rejects off-topic questions while keeping every real answer with a safety margin.
# Questions that are on-topic but not covered (0.61) pass the floor on purpose: deciding
# "the policy does not say" is the answering model's job, which must see the nearest clauses.
RELEVANCE_THRESHOLD = float(os.getenv("POLICY_RELEVANCE_THRESHOLD", "0.55"))
REVIEWER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"}
# Roles allowed to read each classification; None means every authenticated role.
CLASSIFICATION_ROLES = {
    PolicyClassification.PUBLIC: None,
    PolicyClassification.INTERNAL: None,
    PolicyClassification.REVIEWER_ONLY: REVIEWER_ROLES,
    PolicyClassification.CONFIDENTIAL: {"ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"},
    PolicyClassification.RESTRICTED: {"ORG_ADMIN", "SYSTEM_ADMIN"},
}
MAX_KEYWORDS = 5
CANDIDATE_FACTOR = 4  # candidates fetched per requested result, before de-duplication and ranking
EXACT_TERM_BOOST = 0.1  # similarity bonus per distinct figure of the question found in a chunk
MAX_BOOSTED_TERMS = 2
# Validation reads policies completely when they are small; above this it reads the most relevant clauses.
FULL_SCOPE_MAX_CHUNKS = 25
SUBSET_MAX_CHUNKS = 30  # the model never sees more than this (30 x 1200 characters fits comfortably)
CHUNKS_PER_QUERY = 6  # clauses taken for each field of the document when choosing a subset
# Figures worth matching literally: 30, 2.3, $1,000, 12/05, 5%.
_FIGURE = re.compile(r"[$€£]?\d[\d.,/:-]*\d%?|[$€£]?\d%?")


@dataclass(frozen=True)
class RetrievalResult:
    outcome: str
    rows: list  # (Policy, PolicyVersion, PolicyChunk, score, Document | None)
    incomplete_policies: list[dict] = field(default_factory=list)


def readable_classifications(role: str) -> list[PolicyClassification]:
    """Policy classifications the given role may read."""
    normalized_role = (role or "").strip().upper()
    return [
        classification
        for classification, roles in CLASSIFICATION_ROLES.items()
        if roles is None or normalized_role in roles
    ]


@dataclass(frozen=True)
class PolicyScope:
    """Which policy content a caller may see.

    Every search path (vector, keyword, validation) builds its filters here, so a
    new search path cannot forget the organization or role checks.
    """

    organization_id: str
    role: str
    domain: str | None = None
    document_type: str | None = None  # any spelling; resolved to the classifier's category
    version: str | None = None  # None means the ACTIVE version of each policy
    strict_untyped: bool = False  # no document_type given: only policies for every type apply
    embedding_model: str | None = None  # set for vector search: only versions embedded with it

    def policy_conditions(self) -> list:
        """Conditions on the policy itself: tenant, state, role, domain and document type."""
        conditions = [
            Policy.organization_id == self.organization_id,
            Policy.is_active.is_(True),
            Policy.classification.in_(readable_classifications(self.role)),
        ]
        if self.domain is not None:
            conditions.append(func.lower(Policy.domain) == self.domain.strip().lower())
        if (type_condition := self._document_type_condition()) is not None:
            conditions.append(type_condition)
        return conditions

    def _document_type_condition(self):
        """Policies for this document's type, plus policies that apply to every type.

        Matching goes through the classifier's alias table, so "Invoice", "invoice" and
        "financial" are one type. A policy with no document_type applies to all documents.
        """
        wanted = document_type_spellings(self.document_type)
        if not wanted:
            return Policy.document_type.is_(None) if self.strict_untyped else None
        stored = func.replace(func.lower(func.trim(Policy.document_type)), "-", "_")
        return or_(Policy.document_type.is_(None), stored.in_(wanted))

    def chunk_conditions(self) -> list:
        """Policy conditions plus version state and source-document tenancy."""
        conditions = self.policy_conditions()
        # A policy created from text has no source document; if one exists it must be ours.
        conditions.append(or_(Document.id.is_(None), Document.organization_id == self.organization_id))
        if self.version is None:
            conditions.append(PolicyVersion.status == PolicyVersionStatus.ACTIVE)
        else:
            conditions.append(PolicyVersion.version == self.version.strip())
            conditions.append(
                PolicyVersion.status.in_([PolicyVersionStatus.ACTIVE, PolicyVersionStatus.ARCHIVED])
            )
        if self.embedding_model is not None:
            conditions.append(PolicyVersion.embedding_model == self.embedding_model)
        return conditions


def _chunk_query(db: Session, scope: PolicyScope, *entities):
    """Chunks the scope allows, joined to their version, policy and optional source document."""
    return (
        db.query(*entities)
        .select_from(PolicyChunk)
        .join(PolicyVersion, PolicyVersion.id == PolicyChunk.policy_version_id)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .outerjoin(Document, Document.id == PolicyVersion.source_document_id)
        .filter(*scope.chunk_conditions())
    )


def retrieve_policy_evidence(
    db: Session,
    organization_id: str,
    role: str,
    embedding: list[float],
    domain: str | None,
    document_type: str | None,
    policy_version: str | None,
    limit: int,
    query_text: str | None = None,
) -> RetrievalResult:
    """Search the policy content the caller is allowed to read.

    Ranking is by embedding similarity. Embeddings are weak at exact figures, so when the
    question contains numbers (an amount, a clause number, "Net 30") the chunks that contain
    those exact figures are also considered and ranked first. The relevance floor applies to
    every candidate, so a number alone never drags in an unrelated clause.
    """
    scope = PolicyScope(
        organization_id, role, domain, document_type, policy_version, embedding_model=EMBEDDING_MODEL
    )
    distance = PolicyChunk.embedding.cosine_distance(embedding)
    entities = (Policy, PolicyVersion, PolicyChunk, (1 - distance).label("score"), Document)
    relevant = _chunk_query(db, scope, *entities).filter(distance <= (1 - RELEVANCE_THRESHOLD))
    pool_size = limit * CANDIDATE_FACTOR

    rows = relevant.order_by(distance).limit(pool_size).all()
    terms = exact_terms(query_text or "")
    if terms:
        containing_terms = relevant.filter(_content_contains_any(terms)).order_by(distance).limit(pool_size)
        rows = _rank_by_exact_terms(_merge_rows(rows, containing_terms.all()), terms)
    rows = _distinct_by_content(rows)[:limit]
    if rows:
        return RetrievalResult("results", rows)
    # Tell "nothing readable is indexed" apart from "indexed but not relevant enough".
    has_readable_content = _chunk_query(db, scope, PolicyChunk.id).first() is not None
    return RetrievalResult("low_relevance" if has_readable_content else "no_results", [])


def exact_terms(question: str) -> list[str]:
    """Figures in a question worth matching literally: 30, 2.3, $1,000, 12/05, 5%."""
    seen = dict.fromkeys(_normalize_term(match) for match in _FIGURE.findall(question))
    return [term for term in seen if term]


def _normalize_term(match: str) -> str:
    return match.strip(".,:;/-").lstrip("$€£")


def _term_pattern(term: str) -> re.Pattern:
    """The figure as a whole token: "2.3" must not match inside "12.3" or "2.30"."""
    return re.compile(r"(?<![\w.,])" + re.escape(term) + r"(?!\w|[.,]\d)")


def _content_contains_any(terms: list[str]):
    return or_(*(PolicyChunk.content.ilike(f"%{_escape_like(term)}%", escape="\\") for term in terms))


def _merge_rows(first: list, second: list) -> list:
    """Union of two result lists by chunk, keeping the first occurrence."""
    merged = {row[2].id: row for row in first}
    for row in second:
        merged.setdefault(row[2].id, row)
    return list(merged.values())


def _rank_by_exact_terms(rows: list, terms: list[str]) -> list:
    """Order by similarity plus a boost for each distinct figure the chunk contains."""
    patterns = [_term_pattern(term) for term in terms]

    def boosted(row) -> float:
        matched = sum(1 for pattern in patterns if pattern.search(row[2].content))
        return float(row[3]) + EXACT_TERM_BOOST * min(matched, MAX_BOOSTED_TERMS)

    return sorted(rows, key=boosted, reverse=True)


def _distinct_by_content(rows: list) -> list:
    """Keep the best-ranked copy when the same clause appears in several policies."""
    seen: set[str] = set()
    unique = []
    for row in rows:
        key = " ".join(row[2].content.split()).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards so user words match literally ('_' and '%' are wildcards)."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_policies_by_keywords(
    db: Session,
    organization_id: str,
    role: str,
    keywords: list[str],
    document_type: str | None,
    limit: int,
) -> list:
    """Keyword fallback for when embeddings are unavailable; same access rules as vector search."""
    terms = list(dict.fromkeys(word.lower() for word in keywords if word))[:MAX_KEYWORDS]
    if not terms:
        return []
    scope = PolicyScope(organization_id, role, document_type=document_type)
    matches = []
    for term in terms:
        pattern = f"%{_escape_like(term)}%"
        matches.append(PolicyChunk.content.ilike(pattern, escape="\\"))
        matches.append(Policy.name.ilike(pattern, escape="\\"))
    matched_terms = sum((case((match, 1), else_=0) for match in matches), literal(0))
    return (
        _chunk_query(db, scope, Policy, PolicyVersion, PolicyChunk, literal(0.0).label("score"), Document)
        .filter(or_(*matches))
        .order_by(matched_terms.desc(), PolicyChunk.chunk_index)
        .limit(limit)
        .all()
    )


def retrieve_policy_validation_evidence(
    db: Session,
    organization_id: str,
    role: str,
    document_type: str | None,
    query_embeddings: list[list[float]],
) -> RetrievalResult:
    """The policy clauses a document must be checked against.

    Outcomes:
    * `full_scope`: every applicable clause fits, so the model sees all of them.
    * `relevant_subset`: the applicable policies are larger than the model should read, so it
      sees the clauses most relevant to this document (one search per query embedding).
    * `no_applicable_policies`: nothing applies to this document type.
    * `unindexed_policy_evidence`: policies apply but none of them is searchable yet.

    `incomplete_policies` lists applicable policies that cannot be searched (not indexed, or
    indexed with another embedding model); callers must report them, never skip them silently.
    """
    scope = PolicyScope(
        organization_id,
        role,
        document_type=document_type,
        strict_untyped=True,
        embedding_model=EMBEDDING_MODEL,
    )
    applicable = db.query(Policy.id, Policy.name, Policy.current_version).filter(*scope.policy_conditions()).all()
    searchable_ids = {row[0] for row in _chunk_query(db, scope, Policy.id).distinct().all()}
    incomplete = [
        {"policy_id": policy_id, "policy_name": name, "version": version}
        for policy_id, name, version in applicable
        if policy_id not in searchable_ids
    ]
    if not searchable_ids:
        return RetrievalResult("unindexed_policy_evidence" if incomplete else "no_applicable_policies", [], incomplete)

    if _chunk_query(db, scope, func.count(PolicyChunk.id)).scalar() <= FULL_SCOPE_MAX_CHUNKS:
        rows = _closest_chunks(db, scope, query_embeddings[0], limit=FULL_SCOPE_MAX_CHUNKS)
        return RetrievalResult("full_scope", rows, incomplete)

    best_by_chunk: dict[str, tuple] = {}
    for embedding in query_embeddings:
        for row in _closest_chunks(db, scope, embedding, limit=CHUNKS_PER_QUERY):
            known = best_by_chunk.get(row[2].id)
            if known is None or row[3] > known[3]:
                best_by_chunk[row[2].id] = row
    ranked = sorted(best_by_chunk.values(), key=lambda row: row[3], reverse=True)
    return RetrievalResult("relevant_subset", ranked[:SUBSET_MAX_CHUNKS], incomplete)


def _closest_chunks(db: Session, scope: PolicyScope, embedding: list[float], limit: int) -> list:
    distance = PolicyChunk.embedding.cosine_distance(embedding)
    entities = (Policy, PolicyVersion, PolicyChunk, (1 - distance).label("score"), Document)
    return _chunk_query(db, scope, *entities).order_by(distance).limit(limit).all()
