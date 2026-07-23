"""Retrieval for the Biomedical Waste Agent's RAG grounding.

Two paths, tried in order:
  1. FAISS + sentence-transformers semantic search, if the index built by
     ``app.rag.ingest`` exists and those packages are installed.
  2. MongoDB ``$text`` search over the same ``knowledge_base`` collection,
     always available since it needs nothing beyond the core requirements.txt —
     this is what runs on a memory-constrained deployment that never installed
     requirements-ai.txt, per that file's own documented trade-off.

Either path returns the same shape: a list of chunks with a relevance score, so
the agent that consumes this never needs to know which path served it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.repositories import KnowledgeChunkRepository

logger = get_logger(__name__)


def _faiss_index_file() -> Path:
    return Path(settings.faiss_index_path) / "knowledge.index"


@lru_cache(maxsize=1)
def _faiss_available() -> bool:
    if not _faiss_index_file().exists():
        return False
    try:
        import faiss  # noqa: F401
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _load_faiss():
    import faiss

    return faiss.read_index(str(_faiss_index_file()))


@lru_cache(maxsize=1)
def _load_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


async def _semantic_search(query: str, top_k: int, category: str | None) -> list[dict[str, Any]]:
    index = _load_faiss()
    embedder = _load_embedder()

    query_vector = embedder.encode([query], normalize_embeddings=True)
    scores, positions = index.search(query_vector, top_k * 3 if category else top_k)

    repo = KnowledgeChunkRepository()
    rows = await repo.by_faiss_positions([int(p) for p in positions[0] if p >= 0])

    score_by_position = {int(p): float(s) for p, s in zip(positions[0], scores[0])}
    results = []
    for row in rows:
        if category and row.get("category") != category:
            continue
        results.append({**row, "relevance_score": score_by_position.get(row["faiss_index_position"], 0.0)})

    results.sort(key=lambda r: r["relevance_score"], reverse=True)
    return results[:top_k]


async def _text_search(query: str, top_k: int, category: str | None) -> list[dict[str, Any]]:
    repo = KnowledgeChunkRepository()
    rows = await repo.text_search(query, limit=top_k * 3 if category else top_k)
    results = [
        {**row, "relevance_score": row.get("score", 0.0)}
        for row in rows
        if not category or row.get("category") == category
    ]
    return results[:top_k]


async def retrieve(
    query: str, *, top_k: int | None = None, category: str | None = None
) -> list[dict[str, Any]]:
    """Top-``top_k`` chunks for ``query``, optionally restricted to ``category``.

    Every returned row includes ``relevance_score`` (cosine similarity for the
    FAISS path, MongoDB's ``textScore`` for the fallback path — not directly
    comparable across the two, which is fine since a given deployment only ever
    uses one path). Rows below ``settings.rag_score_threshold`` are the caller's
    responsibility to filter — this function returns candidates, not a verdict.
    """
    k = top_k or settings.rag_top_k

    if _faiss_available():
        try:
            return await _semantic_search(query, k, category)
        except Exception as exc:  # noqa: BLE001 - fall through to text search
            logger.warning("rag.semantic_search_failed", error=str(exc))

    return await _text_search(query, k, category)
