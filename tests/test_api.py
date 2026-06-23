"""End-to-end API tests using FastAPI's TestClient and a fake CLI."""
import time

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Config


def _client(tmp_path, fake_cli):
    cfg = Config(data_dir=tmp_path / "data", cli_adapter="command",
                 cli_command=fake_cli, embedder="hashing")
    return TestClient(create_app(cfg))


def _wait_ready(client, source_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        sources = client.get("/api/sources").json()
        s = next((x for x in sources if x["id"] == source_id), None)
        if s and s["status"] in ("ready", "error"):
            return s
        time.sleep(0.1)
    raise AssertionError("ingestion did not finish")


def test_config_endpoint(tmp_path, fake_cli):
    client = _client(tmp_path, fake_cli)
    cfg = client.get("/api/config").json()
    assert cfg["cli_adapter"] == "command"
    assert ".pdf" in cfg["supported_extensions"]


def test_add_source_and_chat_with_citations(tmp_path, fake_cli, sample_txt):
    client = _client(tmp_path, fake_cli)
    resp = client.post("/api/sources", json={"paths": [str(sample_txt)]})
    assert resp.status_code == 200
    sid = resp.json()["added"][0]["id"]
    s = _wait_ready(client, sid)
    assert s["status"] == "ready"

    with client.stream("POST", "/api/chat",
                       json={"message": "What is the moon colony capital?"}) as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert "event: citations" in body
    assert "notes.txt" in body          # citation references the source
    assert "ANSWER based on sources" in body  # streamed model answer
    assert "event: done" in body


def test_chat_without_matching_sources_is_grounded(tmp_path, fake_cli):
    client = _client(tmp_path, fake_cli)
    with client.stream("POST", "/api/chat",
                       json={"message": "anything at all"}) as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert "not covered by the provided sources" in body


def test_enable_disable_and_delete(tmp_path, fake_cli, sample_txt):
    client = _client(tmp_path, fake_cli)
    sid = client.post("/api/sources", json={"paths": [str(sample_txt)]}).json()["added"][0]["id"]
    _wait_ready(client, sid)
    assert client.patch(f"/api/sources/{sid}", json={"enabled": False}).json()["enabled"] is False
    assert client.delete(f"/api/sources/{sid}").json()["deleted"] == sid
    assert client.get("/api/sources").json() == []
