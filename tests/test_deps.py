from server import deps
from server.config import Config


def test_defaults_need_nothing():
    rep = deps.report(Config(transcriber="disabled", embedder="hashing"))
    assert rep["missing_pip"] == []
    assert rep["needs_ffmpeg"] is False
    assert rep["ok"] is True


def test_faster_whisper_reports_missing_package_and_ffmpeg_need():
    rep = deps.report(Config(transcriber="faster-whisper", embedder="hashing"))
    # faster_whisper is an optional extra, not installed in the test venv.
    assert "faster-whisper" in rep["missing_pip"]
    assert rep["needs_ffmpeg"] is True
    assert rep["ok"] is False


def test_semantic_embedder_reports_missing_package():
    rep = deps.report(Config(transcriber="disabled", embedder="sentence-transformers"))
    assert "sentence-transformers" in rep["missing_pip"]
    assert rep["ok"] is False
