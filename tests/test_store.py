
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


def test_mixed_embedding_dims_do_not_crash_search(tmp_path):
    # Simulates switching the embedder: source A has 64-dim chunks, source B
    # has 128-dim chunks. Search must not crash and must only use chunks that
    # match the query's dimension; the other source is reported as stale.
    s = _store(tmp_path)
    sid_a = s.upsert_source(Source(path="/x/a.txt", name="a.txt", modality="document",
                                   status="ready"))
    sid_b = s.upsert_source(Source(path="/x/b.txt", name="b.txt", modality="document",
                                   status="ready"))
    vec64 = HashingEmbedder(dim=64).encode(["alpha beta"])
    vec128 = HashingEmbedder(dim=128).encode(["gamma delta"])
    s.replace_chunks(sid_a, [Chunk(source_id=sid_a, ordinal=0, text="alpha beta",
                                   modality="document")], vec64)
    s.replace_chunks(sid_b, [Chunk(source_id=sid_b, ordinal=0, text="gamma delta",
                                   modality="document")], vec128)

    assert sorted(s.distinct_chunk_dims()) == [64, 128]
    assert s.stale_source_ids(64) == [sid_b]
    assert s.stale_source_ids(128) == [sid_a]

    q64 = HashingEmbedder(dim=64).encode(["alpha"])[0]
    results = s.search(q64, top_k=5)  # must not raise
    assert {r.chunk.source_id for r in results} == {sid_a}


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
