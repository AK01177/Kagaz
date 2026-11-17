"""Measure retrieval quality and calibrate the relevance floor (RAG Phase 0).

Run from `backend/`:
    ..\\.venv\\Scripts\\python.exe -m tests.rag_eval.calibrate

Embeds the policies in `policies/` with Gemini, scores every query in
`queries.json`, and reports, per chunking strategy and per embedding task type:
  * recall@k  - is the chunk holding the answer inside the top-k results?
  * the score distribution of correct answers vs off-topic / near-miss queries
  * the best similarity floor (the cut-off that separates the two groups)

Embeddings are cached in `.cache/` so re-runs cost no API quota. Needs
GEMINI_API_KEY in backend/.env. No database is touched.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).parent
CACHE = HERE / ".cache"
API = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "gemini-embedding-001"
DIM = 1536
BATCH = 100  # API limit per batchEmbedContents call
TOP_K = (1, 3, 5)

load_dotenv(HERE.parent.parent / ".env")


# --------------------------------------------------------------------------- embeddings
def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _post_with_backoff(url: str, key: str, payload: dict, attempts: int = 6) -> httpx.Response:
    """POST with the key in a header (never in the URL, so errors can't leak it); wait out free-tier 429s."""
    for attempt in range(attempts):
        response = httpx.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=60)
        if response.status_code != 429:
            response.raise_for_status()
            return response
        wait = 20 * (attempt + 1)
        print(f"  rate limited (429); waiting {wait}s ...", flush=True)
        time.sleep(wait)
    raise SystemExit("Still rate limited after retries; wait a minute and re-run (cached results are kept).")


def embed(texts: list[str], task_type: str) -> list[list[float]]:
    """Embed texts (L2-normalised, 1536-d); results are cached on disk by content hash."""
    CACHE.mkdir(exist_ok=True)
    key = os.environ["GEMINI_API_KEY"]
    out: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        digest = hashlib.sha256(json.dumps([MODEL, DIM, task_type, batch]).encode()).hexdigest()
        cache_file = CACHE / f"{digest}.json"
        if cache_file.exists():
            out.extend(json.loads(cache_file.read_text()))
            continue
        response = _post_with_backoff(
            f"{API}/models/{MODEL}:batchEmbedContents",
            key,
            {"requests": [
                {"model": f"models/{MODEL}", "content": {"parts": [{"text": t}]},
                 "taskType": task_type, "outputDimensionality": DIM}
                for t in batch
            ]},
        )
        vectors = [_normalize(e["values"]) for e in response.json()["embeddings"]]
        cache_file.write_text(json.dumps(vectors))
        out.extend(vectors)
    return out


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# --------------------------------------------------------------------------- chunkers
def chunk_fixed_windows(text: str) -> list[str]:
    """Baseline: the old approach, naive 1200-character windows with 150 overlap."""
    step = 1200 - 150
    return [text[i : i + 1200].strip() for i in range(0, len(text), step) if text[i : i + 1200].strip()]


def chunk_production(text: str) -> list[str]:
    """The real chunker used by ingestion."""
    from services.policy_chunking import chunk_text

    return [chunk.content for chunk in chunk_text(text)]


CHUNKERS = {"fixed_1200_baseline": chunk_fixed_windows, "production_chunker": chunk_production}


# --------------------------------------------------------------------------- evaluation
def load_policies() -> dict[str, tuple[str, str]]:
    """filename -> (org, text). Org is the suffix `_orgX` in the file name."""
    policies = {}
    for path in sorted((HERE / "policies").glob("*.md")):
        org = re.search(r"_org([A-Z])", path.stem).group(1)
        policies[path.name] = (org, path.read_text(encoding="utf-8"))
    return policies


def evaluate(chunker_name: str, doc_task: str, query_task: str) -> dict:
    policies = load_policies()
    queries = json.loads((HERE / "queries.json").read_text())["queries"]

    chunks: list[dict] = []  # {org, policy, text}
    for name, (org, text) in policies.items():
        for piece in CHUNKERS[chunker_name](text):
            chunks.append({"org": org, "policy": name, "text": piece})
    chunk_vecs = embed([c["text"] for c in chunks], doc_task)
    query_vecs = embed([q["q"] for q in queries], query_task)

    hits = {k: 0 for k in TOP_K}
    relevant_n = 0
    gold_scores, off_scores, near_scores = [], [], []
    missed: list[str] = []
    leaks = 0  # results from another org: must stay 0 (org filter is applied before ranking)

    for query, qvec in zip(queries, query_vecs):
        # Org isolation is a hard filter in production, so only rank that org's chunks.
        # Off-topic queries have no org: rank against every chunk.
        pool = [i for i, c in enumerate(chunks) if query.get("org") in (None, c["org"])]
        ranked = sorted(pool, key=lambda i: dot(qvec, chunk_vecs[i]), reverse=True)
        top_score = dot(qvec, chunk_vecs[ranked[0]])
        if query["kind"] == "relevant":
            relevant_n += 1
            gold = [i for i in pool if _norm(query["expect"]) in _norm(chunks[i]["text"])]
            if not gold:
                raise SystemExit(f"Gold text not found in any chunk ({chunker_name}): {query['expect']!r}")
            best_gold = max(dot(qvec, chunk_vecs[i]) for i in gold)
            gold_scores.append(best_gold)
            for k in TOP_K:
                if set(ranked[:k]) & set(gold):
                    hits[k] += 1
            if not set(ranked[:5]) & set(gold):
                missed.append(query["q"][:60])
        elif query["kind"] == "off_topic":
            off_scores.append(top_score)
        else:
            near_scores.append(top_score)
        leaks += sum(1 for i in ranked if query.get("org") and chunks[i]["org"] != query["org"])

    return {
        "chunks": len(chunks),
        "recall": {k: hits[k] / relevant_n for k in TOP_K},
        "gold": gold_scores, "off": off_scores, "near": near_scores,
        "missed": missed, "leaks": leaks,
    }


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def summarize(label: str, result: dict) -> None:
    gold, off, near = result["gold"], result["off"], result["near"]
    unrelated = off + near
    print(f"\n=== {label}  ({result['chunks']} chunks)")
    print("  recall@k      " + "  ".join(f"@{k}={result['recall'][k]:.0%}" for k in TOP_K))
    print(f"  correct-answer score  min={min(gold):.3f}  p10={_pct(gold, 10):.3f}  median={statistics.median(gold):.3f}")
    print(f"  off-topic top score   median={statistics.median(off):.3f}  max={max(off):.3f}")
    print(f"  near-miss top score   median={statistics.median(near):.3f}  max={max(near):.3f}")
    # Best floor: maximise (correct answers kept) - (unrelated queries let through).
    best = max(
        (t / 1000 for t in range(200, 900, 5)),
        key=lambda t: sum(s >= t for s in gold) / len(gold) - sum(s >= t for s in unrelated) / len(unrelated),
    )
    kept = sum(s >= best for s in gold) / len(gold)
    passed = sum(s >= best for s in unrelated) / len(unrelated)
    print(f"  best floor ~{best:.3f}: keeps {kept:.0%} of correct answers, lets through {passed:.0%} of unrelated queries")
    at_075 = sum(s >= 0.75 for s in gold) / len(gold)
    print(f"  current floor 0.75: keeps only {at_075:.0%} of correct answers")
    if result["missed"]:
        print("  not in top-5:", result["missed"])


def _pct(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))]


if __name__ == "__main__":
    for chunker in CHUNKERS:
        for doc_task, query_task in (("RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"),):
            summarize(f"{chunker} | docs={doc_task} queries={query_task}", evaluate(chunker, doc_task, query_task))
