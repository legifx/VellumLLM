"""Audio ingestion via transcription."""
from __future__ import annotations

from pathlib import Path

from ..chunking import TextPiece
from .transcribe import segments_to_pieces, transcribe


def extract_audio(path: Path, transcriber: str, whisper_model: str) -> list[TextPiece]:
    segments = transcribe(path, transcriber, whisper_model)
    if not segments:
        # Transcription disabled or unavailable: index a caption so the source
        # is still listed and citable, without fabricating content.
        return [TextPiece(
            text=(f"Audio file '{path.name}'. Transcription is not available "
                  f"(set MMRAG_TRANSCRIBER to enable). No transcript content indexed."),
            locator="caption",
        )]
    return segments_to_pieces(segments)
