"""Ingestion dispatcher.

Detects modality, expands directories, hashes files for incremental skipping,
runs the right extractor, chunks the text, embeds it, and writes everything to
the local store.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable
from pathlib import Path

from ..chunking import TextPiece, chunk_pieces
from ..config import Config
from ..embeddings import Embedder
from ..models import Chunk, Modality, Source
from ..store import Store
from . import audio as audio_mod
from . import documents as doc_mod
from . import images as img_mod
from . import video as video_mod

DOC_EXT = {".pdf", ".txt", ".md", ".docx", ".pptx", ".csv", ".html", ".htm"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUD_EXT = {".mp3", ".wav", ".m4a", ".flac"}
VID_EXT = {".mp4", ".mov", ".mkv"}
SUPPORTED = DOC_EXT | IMG_EXT | AUD_EXT | VID_EXT


def detect_modality(path: Path) -> Modality | None:
    ext = path.suffix.lower()
    if ext in DOC_EXT:
        return "document"
    if ext in IMG_EXT:
        return "image"
    if ext in AUD_EXT:
        return "audio"
    if ext in VID_EXT:
        return "video"
    return None


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def expand_paths(paths: Iterable[str]) -> list[Path]:
    """Expand directories into supported files; keep individual files."""
    found: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        if p.is_dir():
            for sub in sorted(p.rglob("*")):
                if sub.is_file() and sub.suffix.lower() in SUPPORTED:
                    found.append(sub)
        elif p.is_file() and p.suffix.lower() in SUPPORTED:
            found.append(p)
    # de-duplicate while preserving order
    seen, unique = set(), []
    for p in found:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    return unique


def _extract(path: Path, modality: Modality, cfg: Config) -> list[TextPiece]:
    if modality == "document":
        return doc_mod.extract_document(path)
    if modality == "image":
        return img_mod.extract_image(path)
    if modality == "audio":
        return audio_mod.extract_audio(path, cfg.transcriber, cfg.whisper_model)
    if modality == "video":
        return video_mod.extract_video(path, cfg.transcriber, cfg.whisper_model)
    raise RuntimeError(f"Unsupported modality: {modality}")


def register_source(store: Store, path: Path) -> Source:
    """Create or fetch a Source row in 'pending' state."""
    modality = detect_modality(path)
    if modality is None:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    resolved = str(path.resolve())
    existing = store.get_source_by_path(resolved)
    size = path.stat().st_size
    source = Source(
        id=existing.id if existing else None,
        path=resolved, name=path.name, modality=modality, size=size,
        status="pending", added_at=existing.added_at if existing else time.time(),
        content_hash=existing.content_hash if existing else "",
        chunk_count=existing.chunk_count if existing else 0,
    )
    source.id = store.upsert_source(source)
    return source


def process_source(store: Store, embedder: Embedder, cfg: Config,
                   source_id: int, force: bool = False) -> Source:
    """Run the full pipeline for one source. Incremental via content hash."""
    source = store.get_source(source_id)
    if source is None:
        raise ValueError(f"No source with id {source_id}")
    path = Path(source.path)
    if not path.exists():
        store.set_status(source_id, "error", "file no longer exists")
        return store.get_source(source_id)  # type: ignore

    new_hash = file_hash(path)
    if not force and source.content_hash == new_hash and source.status == "ready":
        return source  # unchanged -> skip re-processing

    store.set_status(source_id, "processing")
    try:
        pieces = _extract(path, source.modality, cfg)
        pieces = chunk_pieces(pieces, cfg.chunk_size, cfg.chunk_overlap)
        if pieces:
            texts = [p.text for p in pieces]
            embeddings = embedder.encode(texts)
            chunks = [Chunk(source_id=source_id, ordinal=i, text=p.text,
                            modality=source.modality, locator=p.locator)
                      for i, p in enumerate(pieces)]
            store.replace_chunks(source_id, chunks, embeddings)
        else:
            import numpy as np
            store.replace_chunks(source_id, [], np.zeros((0, embedder.dim), dtype="float32"))
        # persist new hash + ready status
        source.content_hash = new_hash
        source.status = "ready"
        source.error = ""
        source.chunk_count = len(pieces)
        store.upsert_source(source)
    except Exception as exc:  # record, never crash the server
        store.set_status(source_id, "error", str(exc)[:500])
    return store.get_source(source_id)  # type: ignore
