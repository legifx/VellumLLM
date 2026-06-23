from server.config import Config
from server.embeddings import HashingEmbedder
from server.ingest import process_source, register_source
from server.retrieval import retrieve
from server.store import Store


def _ready_store(tmp_path, text):
    cfg = Config(data_dir=tmp_path / "data")
    cfg.ensure_dirs()
    store = Store(cfg.db_path)
    emb = HashingEmbedder(dim=256)
    src_file = tmp_path / "doc.txt"
    src_file.write_text(text, encoding="utf-8")
    src = register_source(store, src_file)
    process_source(store, emb, cfg, src.id)
    return store, emb


def test_relevant_query_retrieves(tmp_path):
    store, emb = _ready_store(tmp_path, "Photosynthesis converts sunlight into energy in plants.")
    hits = retrieve(store, emb, "how do plants use sunlight", top_k=5)
    assert hits and "photosynthesis" in hits[0].chunk.text.lower()


def test_offtopic_scores_far_below_ontopic(tmp_path):
    # The retrieval floor drops orthogonal matches; remaining off-topic matches
    # score far lower than on-topic ones (final grounding is enforced by the
    # system prompt, which tells the model to answer only from the sources).
    store, emb = _ready_store(tmp_path, "Photosynthesis converts sunlight into energy in plants.")
    on = retrieve(store, emb, "how do plants use sunlight", top_k=5)
    off = retrieve(store, emb, "quarterly tax depreciation schedule jurisdiction", top_k=5)
    on_score = on[0].score if on else 0.0
    off_score = off[0].score if off else 0.0
    assert on_score > off_score
    assert off_score < 0.2  # weak/irrelevant
