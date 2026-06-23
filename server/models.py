"""Pydantic schemas for the API and internal data passing."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Modality = Literal["document", "image", "audio", "video"]
SourceStatus = Literal["pending", "processing", "ready", "error", "disabled"]


class Chunk(BaseModel):
    """A retrievable unit of content with provenance."""
    id: Optional[int] = None
    source_id: int
    ordinal: int
    text: str
    modality: Modality
    # Human-readable pointer into the source: "p. 3", "00:01:24", "frame 12".
    locator: str = ""


class RetrievedChunk(BaseModel):
    chunk: Chunk
    source_name: str
    source_path: str
    score: float


class Source(BaseModel):
    id: Optional[int] = None
    path: str
    name: str
    modality: Modality
    size: int = 0
    content_hash: str = ""
    status: SourceStatus = "pending"
    enabled: bool = True
    error: str = ""
    chunk_count: int = 0
    added_at: float = 0.0


class AddSourcesRequest(BaseModel):
    # Absolute paths to files and/or directories on the local machine.
    paths: list[str]


class ChatRequest(BaseModel):
    message: str
    # Restrict retrieval to these source ids (empty = all enabled sources).
    source_ids: list[int] = []
    top_k: Optional[int] = None


class Citation(BaseModel):
    source_id: int
    source_name: str
    locator: str
    snippet: str
    score: float
