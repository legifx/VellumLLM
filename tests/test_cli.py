"""Tests for the single-Vellum CLI (server.cli)."""
import json
import time

from fastapi.testclient import TestClient

from server import cli
from server.app import create_app
from server.config import Config
from server.notebooks import NotebookRegistry


def _cfg(tmp_path, fake_cli):
    return Config(data_dir=tmp_path / "data", cli_adapter="command",
                  cli_command=fake_cli, embedder="hashing")


def _env(monkeypatch, cfg, fake_cli):
    """Make Config.load() inside cli.main resolve to this test's setup,
    isolated from any real project .env."""
    monkeypatch.setenv("VELLUM_ENV_FILE", str(cfg.data_dir / ".env.absent"))
    monkeypatch.setenv("MMRAG_DATA_DIR", str(cfg.data_dir))
    monkeypatch.setenv("MMRAG_CLI_ADAPTER", "command")
    monkeypatch.setenv("MMRAG_CLI_COMMAND", fake_cli)
    monkeypatch.setenv("MMRAG_EMBEDDER", "hashing")


def _ingest(cfg, sample_txt):
    """Use the API to create the default Vellum and ingest one ready source."""
    client = TestClient(create_app(cfg))
    nb = client.get("/api/notebooks").json()[0]["id"]
    client.post(f"/api/notebooks/{nb}/sources",
                json={"paths": [str(sample_txt)]})
    deadline = time.time() + 10
    while time.time() < deadline:
        s = client.get(f"/api/notebooks/{nb}/sources").json()["sources"][0]
        if s["status"] in ("ready", "error"):
            break
        time.sleep(0.1)
    return nb


def test_resolve_by_id_and_name(tmp_path):
    reg = NotebookRegistry(tmp_path / "nb")
    nb = reg.create("Biology 101")
    assert cli.resolve_notebook(reg, nb.id).id == nb.id
    assert cli.resolve_notebook(reg, "Biology 101").id == nb.id
    assert cli.resolve_notebook(reg, "biology").id == nb.id
    assert cli.resolve_notebook(reg, "nope") is None


def test_ask_sources_only(tmp_path, fake_cli, sample_txt, capsys, monkeypatch):
    cfg = _cfg(tmp_path, fake_cli)
    nb = _ingest(cfg, sample_txt)
    _env(monkeypatch, cfg, fake_cli)
    rc = cli.main(["ask", "-n", nb, "moon", "colony", "capital", "--sources-only"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["notebook"] == nb
    assert out["citations"][0]["source_name"] == "notes.txt"


def test_ask_streams_answer(tmp_path, fake_cli, sample_txt, capsys, monkeypatch):
    cfg = _cfg(tmp_path, fake_cli)
    nb = _ingest(cfg, sample_txt)
    _env(monkeypatch, cfg, fake_cli)
    rc = cli.main(["ask", "-n", nb, "what", "is", "the", "capital"])
    assert rc == 0
    assert "ANSWER based on sources" in capsys.readouterr().out


def test_ask_unknown_notebook(tmp_path, fake_cli, monkeypatch):
    cfg = _cfg(tmp_path, fake_cli)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    _env(monkeypatch, cfg, fake_cli)
    assert cli.main(["ask", "-n", "ghost", "hi"]) == 2


def test_notebooks_json(tmp_path, fake_cli, sample_txt, capsys, monkeypatch):
    cfg = _cfg(tmp_path, fake_cli)
    nb = _ingest(cfg, sample_txt)
    _env(monkeypatch, cfg, fake_cli)
    rc = cli.main(["notebooks", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any(n["id"] == nb and n["source_count"] == 1 for n in data)
