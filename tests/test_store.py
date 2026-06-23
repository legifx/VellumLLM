import numpy as np

from server.embeddings import HashingEmbedder
from server.models import Chunk, Source
from server.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.sqlite3")


def test_upsert_and_list(tmp_path):
    s = _store(tmp_path)
    sid = s.upsert_source(Source(path="/x/a.txt", name="a.txt", modality="document"))
    assert sid > 0
    # upsert again on same path updates, not duplicates
    s.upsert_source(Source(path="/x/a.txt", name="a.txt", modality="document",
                           status="ready", chunk_count=3))
    sources = s.list_sources()
    assert len(sources) == 1
    assert sources[0].status == "ready"
    assert sources[0].chunk_count == 3


def test_search_returns_ranked_enabled_ready(tmp_path):
    s = _store(tmp_path)
    emb = HashingEmbedder(dim=128)
    sid = s.upsert_source(Source(path="/x/a.txt", name="a.txt", modality="document",
                                 status="ready"))
    texts = ["apples and oranges are fruit", "cars and trucks are vehicles"]
    vecs = emb.encode(texts)
    chunks = [Chunk(source_id=sid, ordinal=i, text=t, modality="document", locator=f"#{i}")
              for i, t in enumerate(texts)]
    s.replace_chunks(sid, chunks, vecs)

    q = emb.encode(["fruit like apples"])[0]
    results = s.search(q, top_k=2)
    assert results
    assert results[0].chunk.text == texts[0]
    assert results[0].source_name == "a.txt"


def test_disabled_source_excluded_from_search(tmp_path):
    s = _store(tmp_path)
    emb = HashingEmbedder(dim=64)
    sid = s.upsert_source(Source(path="/x/a.txt", name="a.txt", modality="document",
                                 status="ready"))
    s.replace_chunks(sid, [Chunk(source_id=sid, ordinal=0, text="hello", modality="document")],
                     emb.encode(["hello"]))
    s.set_enabled(sid, False)
    assert s.search(emb.encode(["hello"])[0], top_k=5) == []


def test_delete_cascades(tmp_path):
    s = _store(tmp_path)
    emb = HashingEmbedder(dim=64)
    sid = s.upsert_source(Source(path="/x/a.txt", name="a.txt", modality="document",
                                 status="ready"))
    s.replace_chunks(sid, [Chunk(source_id=sid, ordinal=0, text="hi", modality="document")],
                     emb.encode(["hi"]))
    s.delete_source(sid)
    assert s.list_sources() == []
    assert s.search(emb.encode(["hi"])[0], top_k=5) == []
