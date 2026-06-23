"""Text chunking with overlap, preserving a per-chunk locator."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextPiece:
    """A piece of extracted text with a provenance locator (page/timestamp)."""
    text: str
    locator: str = ""


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        # Prefer to break on a paragraph/sentence boundary near the end.
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", "\n", ". ", " "):
                idx = window.rfind(sep)
                if idx > chunk_size * 0.5:
                    end = start + idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def chunk_pieces(pieces: list[TextPiece], chunk_size: int, overlap: int) -> list[TextPiece]:
    """Chunk each piece independently so locators stay accurate."""
    result: list[TextPiece] = []
    for piece in pieces:
        for sub in _split_text(piece.text, chunk_size, overlap):
            result.append(TextPiece(text=sub, locator=piece.locator))
    return result
