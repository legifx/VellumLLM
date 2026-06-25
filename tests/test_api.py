"""End-to-end API tests using FastAPI's TestClient and a fake CLI.

The API is notebook-scoped: a default Vellum is auto-created, and sources/chat
live under ``/api/notebooks/<id>/...``.
"""
import time

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Config


def _client(tmp_path, fake_cli):
    cfg = Config(data_dir=tmp_path / "data", cli_adapter="command",
                 cli_command=fake_cli, embedder="hashing")
    return TestClient(create_app(cfg))


def _default_nb(client) -> str:
    return client.get("/api/notebooks").json()[0]["id"]


def _wait_ready(client, nb, source_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        sources = client.get(f"/api/notebooks/{nb}/sources").json()["sources"]
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
    assert cfg["network_exposed"] is False


def test_default_notebook_created(tmp_path, fake_cli):
    client = _client(tmp_path, fake_cli)
    nbs = client.get("/api/notebooks").json()
    assert len(nbs) == 1
    assert nbs[0]["source_count"] == 0


def test_notebook_crud(tmp_path, fake_cli):
    client = _client(tmp_path, fake_cli)
    nb = client.post("/api/notebooks", json={"name": "Biology 101", "category": "School"}).json()
    assert nb["name"] == "Biology 101"
    assert nb["id"] == "biology-101"
    upd = client.patch(f"/api/notebooks/{nb['id']}", json={"name": "Bio"}).json()
    assert upd["name"] == "Bio"
    assert client.delete(f"/api/notebooks/{nb['id']}").json()["deleted"] == nb["id"]
    assert all(n["id"] != nb["id"] for n in client.get("/api/notebooks").json())


def test_add_source_and_chat_with_citations(tmp_path, fake_cli, sample_txt):
    client = _client(tmp_path, fake_cli)
    nb = _default_nb(client)
    resp = client.post(f"/api/notebooks/{nb}/sources", json={"paths": [str(sample_txt)]})
    assert resp.status_code == 200
    sid = resp.json()["added"][0]["id"]
    s = _wait_ready(client, nb, sid)
    assert s["status"] == "ready"

    with client.stream("POST", f"/api/notebooks/{nb}/chat",
                       json={"message": "What is the moon colony capital?"}) as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert "event: citations" in body
    assert "notes.txt" in body          # citation references the source
    assert "ANSWER based on sources" in body  # streamed model answer
    assert "event: done" in body


def test_source_file_preview(tmp_path, fake_cli, sample_txt):
    client = _client(tmp_path, fake_cli)
    nb = _default_nb(client)
    sid = client.post(f"/api/notebooks/{nb}/sources",
                      json={"paths": [str(sample_txt)]}).json()["added"][0]["id"]
    _wait_ready(client, nb, sid)
    r = client.get(f"/api/notebooks/{nb}/sources/{sid}/file")
    assert r.status_code == 200
    assert "moon" in r.text.lower() or len(r.text) > 0


def test_fs_browse_lists_directory(tmp_path, fake_cli, sample_txt):
    client = _client(tmp_path, fake_cli)
    r = client.get("/api/fs/browse", params={"path": str(sample_txt.parent)})
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == str(sample_txt.parent.resolve())
    assert any(e["name"] == sample_txt.name and e["supported"] for e in data["entries"])


def test_chat_without_matching_sources_is_grounded(tmp_path, fake_cli):
    client = _client(tmp_path, fake_cli)
    nb = _default_nb(client)
    with client.stream("POST", f"/api/notebooks/{nb}/chat",
                       json={"message": "anything at all"}) as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert "not covered by the provided sources" in body


def test_reprocess_all_clears_stale_after_embedder_switch(tmp_path, fake_cli, sample_txt):
    import numpy as np

    from server.config import Config
    from server.store import Store

    data_dir = tmp_path / "data"
    cfg = Config(data_dir=data_dir, cli_adapter="command", cli_command=fake_cli,
                 embedder="hashing")  # hashing default dim = 256
    client = TestClient(create_app(cfg))
    nb = _default_nb(client)
    sid = client.post(f"/api/notebooks/{nb}/sources",
                      json={"paths": [str(sample_txt)]}).json()["added"][0]["id"]
    _wait_ready(client, nb, sid)

    # Inject a stale-dimension chunk (simulating a previous, different embedder).
    from server.models import Chunk
    store = Store(data_dir / "notebooks" / nb / "notebook.sqlite3")
    store.replace_chunks(sid, [Chunk(source_id=sid, ordinal=0, text="x", modality="document")],
                         np.zeros((1, 64), dtype="float32"))

    listed = client.get(f"/api/notebooks/{nb}/sources").json()
    assert listed["needs_reprocess"] is True
    assert sid in listed["stale_source_ids"]

    client.post(f"/api/notebooks/{nb}/sources/reprocess-all")
    _wait_ready(client, nb, sid)
    assert client.get(f"/api/notebooks/{nb}/sources").json()["needs_reprocess"] is False


def test_enable_disable_and_delete(tmp_path, fake_cli, sample_txt):
    client = _client(tmp_path, fake_cli)
    nb = _default_nb(client)
    sid = client.post(f"/api/notebooks/{nb}/sources",
                      json={"paths": [str(sample_txt)]}).json()["added"][0]["id"]
    _wait_ready(client, nb, sid)
    assert client.patch(f"/api/notebooks/{nb}/sources/{sid}",
                        json={"enabled": False}).json()["enabled"] is False
    assert client.delete(f"/api/notebooks/{nb}/sources/{sid}").json()["deleted"] == sid
    assert client.get(f"/api/notebooks/{nb}/sources").json()["sources"] == []
