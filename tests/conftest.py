"""Shared test fixtures.

All sample files are GENERATED at test time in a temp dir — no real user data,
no committed binaries.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    p = tmp_path / "notes.txt"
    p.write_text(
        "The capital of the moon colony is New Selene. "
        "Its primary export is helium-3. The colony was founded in 2071.",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text("name,role\nAda,engineer\nGrace,admiral\n", encoding="utf-8")
    return p


@pytest.fixture
def sample_html(tmp_path: Path) -> Path:
    p = tmp_path / "page.html"
    p.write_text(
        "<html><head><style>.x{}</style></head><body>"
        "<h1>Title</h1><p>Hello <b>world</b> from HTML.</p></body></html>",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    from PIL import Image
    p = tmp_path / "diagram_solar_panel.png"
    Image.new("RGB", (64, 48), color=(120, 120, 200)).save(p)
    return p


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    p = tmp_path / "report.pdf"
    c = canvas.Canvas(str(p), pagesize=letter)
    c.drawString(72, 720, "Quarterly report: revenue grew by 42 percent.")
    c.showPage()
    c.drawString(72, 720, "Risks include supply chain delays on page two.")
    c.showPage()
    c.save()
    return p


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    # Transcription is disabled in tests, so the bytes are never decoded.
    p = tmp_path / "interview.mp3"
    p.write_bytes(b"\x00\x00\x00")
    return p


@pytest.fixture
def fake_cli(tmp_path: Path) -> str:
    """A stand-in 'LLM CLI' that reads a prompt on stdin and echoes an answer.

    Returns a shell command string suitable for MMRAG_CLI_COMMAND.
    """
    script = tmp_path / "fake_cli.py"
    script.write_text(
        "import sys\n"
        "data = sys.stdin.read()\n"
        "print('ANSWER based on sources [S1]')\n",
        encoding="utf-8",
    )
    return f"{sys.executable} {script}"
