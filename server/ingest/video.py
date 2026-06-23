"""Video ingestion: keyframe extraction (+ optional OCR) and audio transcription.

Uses ffmpeg (must be on PATH) to pull keyframes and the audio track. Keyframe
OCR and transcription are optional and degrade gracefully.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..chunking import TextPiece
from .images import _ocr
from .transcribe import segments_to_pieces, transcribe


def _have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _extract_keyframes(path: Path, out_dir: Path, max_frames: int = 12) -> list[Path]:
    """Extract up to max_frames scene-change keyframes as JPEGs."""
    pattern = str(out_dir / "frame_%03d.jpg")
    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(path),
        "-vf", "select='gt(scene,0.3)',showinfo", "-vsync", "vfr",
        "-frames:v", str(max_frames), pattern,
    ]
    subprocess.run(cmd, check=False, capture_output=True)
    frames = sorted(out_dir.glob("frame_*.jpg"))
    if not frames:  # fallback: one frame every 30s
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf",
             "fps=1/30", "-frames:v", str(max_frames), pattern],
            check=False, capture_output=True,
        )
        frames = sorted(out_dir.glob("frame_*.jpg"))
    return frames


def _extract_audio(path: Path, out_wav: Path) -> bool:
    cmd = ["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1",
           "-ar", "16000", "-y", str(out_wav)]
    res = subprocess.run(cmd, check=False, capture_output=True)
    return res.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 0


def extract_video(path: Path, transcriber: str, whisper_model: str) -> list[TextPiece]:
    pieces: list[TextPiece] = []
    if not _have_ffmpeg():
        return [TextPiece(
            text=(f"Video file '{path.name}'. ffmpeg is not installed, so no "
                  f"keyframes or audio could be extracted."),
            locator="caption",
        )]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # 1) keyframes -> optional OCR
        ocr_texts = []
        for i, frame in enumerate(_extract_keyframes(path, tmp_dir), start=1):
            text = _ocr(frame)
            if text:
                ocr_texts.append(f"[keyframe {i}] {text}")
        if ocr_texts:
            pieces.append(TextPiece(text="On-screen text from keyframes:\n" +
                                    "\n".join(ocr_texts), locator="keyframes"))
        # 2) audio track -> transcription
        wav = tmp_dir / "audio.wav"
        if _extract_audio(path, wav):
            segments = transcribe(wav, transcriber, whisper_model)
            pieces.extend(segments_to_pieces(segments))

    if not pieces:
        pieces.append(TextPiece(
            text=(f"Video file '{path.name}'. No on-screen text detected and "
                  f"transcription is not available (set MMRAG_TRANSCRIBER to enable)."),
            locator="caption",
        ))
    return pieces
