"""Retrieval: embed the query and fetch the most relevant chunks."""
from __future__ import annotations

from typing import Optional

from .embeddings import Embedder
from .models import RetrievedChunk
from .store import Store


def retrieve(store: Store, embedder: Embedder, query: str, top_k: int,
             source_ids: Optional[list[int]] = None,
             min_score: float = 1e-6) -> list[RetrievedChunk]:
    query = (query or "").strip()
    if not query:
        return []
    qvec = embedder.encode([query])[0]
    results = store.search(qvec, top_k=top_k, source_ids=source_ids or None)
    # Drop non-relevant (orthogonal / negative) matches so genuinely
    # off-topic questions fall through to the "not in the sources" path
    # instead of being handed an irrelevant chunk.
    return [r for r in results if r.score > min_score]
