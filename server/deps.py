"""Optional-dependency doctor.

The core install is intentionally light. Some features (audio/video
transcription, semantic embeddings) need extra packages. Given the active
config this reports which extras a feature requires and whether they are
actually importable — so the launcher can offer to install them instead of
letting ingestion fail at runtime with "faster-whisper is not installed".

Run as a module to get a JSON report for the current config:

    python -m server.deps        # prints {"missing_pip": [...], ...}
"""
from __future__ import annotations

import importlib.util
import json
import shutil

from .config import Config

# config value -> (import module name, pip package, needs ffmpeg)
_TRANSCRIBERS = {
    "faster-whisper": ("faster_whisper", "faster-whisper", True),
    "whisper": ("whisper", "openai-whisper", True),
}
_EMBEDDERS = {
    "sentence-transformers": ("sentence_transformers", "sentence-transformers", False),
}


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def report(cfg: Config) -> dict:
    """Return what the active config needs and what's missing."""
    missing_pip: list[str] = []
    needs_ffmpeg = False

    spec = _TRANSCRIBERS.get(cfg.transcriber)
    if spec:
        module, pip, ff = spec
        if not _installed(module):
            missing_pip.append(pip)
        needs_ffmpeg = needs_ffmpeg or ff

    spec = _EMBEDDERS.get(cfg.embedder)
    if spec:
        module, pip, _ = spec
        if not _installed(module):
            missing_pip.append(pip)

    ffmpeg_present = shutil.which("ffmpeg") is not None
    return {
        "missing_pip": missing_pip,
        "needs_ffmpeg": needs_ffmpeg,
        "ffmpeg_present": ffmpeg_present,
        "ffmpeg_missing": needs_ffmpeg and not ffmpeg_present,
        "ok": not missing_pip and not (needs_ffmpeg and not ffmpeg_present),
    }


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(report(Config.load())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
