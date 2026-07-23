"""Builds the FAISS index and the corresponding ``knowledge_base`` Mongo rows from
the markdown corpus in ``knowledge_base/``.

Run offline, from ``backend/`` (needs requirements-ai.txt installed):
    python -m app.rag.ingest

This intentionally does NOT run as part of the API's startup — indexing is a
deliberate, versioned build step, not something that should silently happen on
every container boot. ``app/rag/retriever.py`` loads whatever this script last
produced; if it has never been run, the retriever falls back to MongoDB text
search (see that module's docstring).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.repositories import KnowledgeChunkRepository

logger = get_logger(__name__)

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"
INDEX_VERSION = "kb@1.0.0"

# Maps a source filename (without extension) to the ``category`` field every chunk
# from it gets tagged with — the Biomedical Waste Agent filters retrieval by this.
DOCUMENT_CATEGORIES: dict[str, str] = {
    "cpcb_biomedical_waste_rules_2016": "biomedical_waste",
}


@dataclass
class Chunk:
    doc_id: str
    section: str | None
    category: str
    content: str


def _split_into_sections(text: str) -> list[tuple[str | None, str]]:
    """Split a markdown document on ``##`` headers. Returns (heading, body) pairs."""
    parts = re.split(r"\n(?=## )", text)
    sections: list[tuple[str | None, str]] = []
    for part in parts:
        match = re.match(r"## (.+)\n", part)
        heading = match.group(1).strip() if match else None
        sections.append((heading, part.strip()))
    return sections


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Character-window chunking with overlap. Splits on paragraph boundaries where
    possible so a chunk doesn't get cut mid-sentence more than necessary."""
    if len(text) <= size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= size:
            current = f"{current}\n\n{paragraph}" if current else paragraph
        else:
            if current:
                chunks.append(current)
            # Overlap: carry the tail of the previous chunk forward.
            current = (current[-overlap:] + "\n\n" + paragraph) if current else paragraph

    if current:
        chunks.append(current)
    return chunks


def build_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []

    for doc_path in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        doc_id = doc_path.stem
        category = DOCUMENT_CATEGORIES.get(doc_id, "general")
        text = doc_path.read_text(encoding="utf-8")

        for heading, section_text in _split_into_sections(text):
            for piece in _chunk_text(section_text, settings.rag_chunk_size, settings.rag_chunk_overlap):
                if piece.strip():
                    chunks.append(Chunk(doc_id=doc_id, section=heading, category=category, content=piece.strip()))

    return chunks


async def ingest() -> dict:
    """Embed every chunk, build the FAISS index, and replace the Mongo mirror.

    Requires ``requirements-ai.txt`` (sentence-transformers, faiss-cpu). Imported
    lazily so importing this module doesn't force those dependencies onto every
    deployment — only running the ingestion script does.
    """
    import faiss
    from sentence_transformers import SentenceTransformer

    chunks = build_chunks()
    if not chunks:
        raise RuntimeError(f"No markdown documents found in {KNOWLEDGE_BASE_DIR}")

    model = SentenceTransformer(settings.embedding_model)
    embeddings = model.encode(
        [chunk.content for chunk in chunks], normalize_embeddings=True, show_progress_bar=False
    )

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # inner product on normalised vectors = cosine similarity
    index.add(embeddings)

    index_dir = Path(settings.faiss_index_path)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / "knowledge.index"))

    documents = [
        {
            "doc_id": chunk.doc_id,
            "chunk_id": f"{chunk.doc_id}::{position}",
            "faiss_index_position": position,
            "source_document": f"{chunk.doc_id}.md",
            "section": chunk.section,
            "category": chunk.category,
            "content": chunk.content,
            "token_count": len(chunk.content.split()),
            "embedding_model": settings.embedding_model,
            "index_version": INDEX_VERSION,
        }
        for position, chunk in enumerate(chunks)
    ]

    repo = KnowledgeChunkRepository()
    written = await repo.replace_all(documents)

    logger.info("rag.ingested", chunks=len(documents), index_path=str(index_dir))
    return {"chunks_written": written, "dimension": dimension, "index_version": INDEX_VERSION}


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(ingest())
    print(f"Ingested {result['chunks_written']} chunks (dim={result['dimension']}) -> {settings.faiss_index_path}")
