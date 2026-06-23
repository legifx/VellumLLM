"""Image ingestion: OCR text-in-image plus a lightweight descriptive caption.

OCR (pytesseract) and Pillow are optional. Without them we still index a
caption built from the filename and basic metadata so the image is citable.
"""
from __future__ import annotations

from pathlib import Path

from ..chunking import TextPiece


def _dimensions(path: Path) -> str:
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(path) as im:
            return f"{im.width}x{im.height}"
    except Exception:
        return ""


def _ocr(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(path) as im:
            return pytesseract.image_to_string(im).strip()
    except Exception:
        return ""


def extract_image(path: Path) -> list[TextPiece]:
    name = path.stem.replace("_", " ").replace("-", " ")
    dims = _dimensions(path)
    caption = f"Image '{path.name}'"
    if dims:
        caption += f" ({dims})"
    caption += f". Filename keywords: {name}."

    ocr_text = _ocr(path)
    pieces = [TextPiece(text=caption, locator="caption")]
    if ocr_text:
        pieces.append(TextPiece(text=f"Text detected in image:\n{ocr_text}",
                                locator="ocr"))
    return pieces
