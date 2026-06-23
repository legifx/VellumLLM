"""Audio transcription backends (optional).

Supports ``faster-whisper`` and the original ``whisper`` package. Both are
optional; if neither is installed (or the backend is "disabled"), transcription
returns an empty list and the caller records an informational note.

Returns timestamped segments so locators point to a position in the media.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


@lru_cache(maxsize=2)
def _faster_whisper_model(model_size: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device="cpu", compute_type="int8")


@lru_cache(maxsize=2)
def _whisper_model(model_size: str):
    import whisper
    return whisper.load_model(model_size)


def transcribe(path: Path, backend: str, model_size: str) -> list[Segment]:
    backend = (backend or "disabled").lower()
    if backend == "disabled":
        return []
    if backend == "faster-whisper":
        try:
            model = _faster_whisper_model(model_size)
        except ImportError as exc:
            raise RuntimeError(
                "MMRAG_TRANSCRIBER=faster-whisper but 'faster-whisper' is not "
                "installed. Run: pip install faster-whisper"
            ) from exc
        segments, _ = model.transcribe(str(path))
        return [Segment(s.start, s.end, s.text.strip()) for s in segments if s.text.strip()]
    if backend == "whisper":
        try:
            model = _whisper_model(model_size)
        except ImportError as exc:
            raise RuntimeError(
                "MMRAG_TRANSCRIBER=whisper but 'openai-whisper' is not installed. "
                "Run: pip install openai-whisper"
            ) from exc
        result = model.transcribe(str(path))
        return [Segment(s["start"], s["end"], s["text"].strip())
                for s in result.get("segments", []) if s["text"].strip()]
    raise ValueError(f"Unknown transcriber backend '{backend}'.")


def segments_to_pieces(segments: list[Segment]):
    """Group segments into ~chunkable text pieces with timestamp locators."""
    from ..chunking import TextPiece
    pieces = []
    buf: list[str] = []
    start_ts = None
    char_budget = 800
    for seg in segments:
        if start_ts is None:
            start_ts = seg.start
        buf.append(seg.text)
        if sum(len(b) for b in buf) >= char_budget:
            pieces.append(TextPiece(text=" ".join(buf),
                                    locator=f"{_fmt_ts(start_ts)}–{_fmt_ts(seg.end)}"))
            buf, start_ts = [], None
    if buf and start_ts is not None:
        pieces.append(TextPiece(text=" ".join(buf),
                                locator=f"{_fmt_ts(start_ts)}–{_fmt_ts(segments[-1].end)}"))
    return pieces
