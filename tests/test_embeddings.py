import numpy as np

from server.embeddings import HashingEmbedder, build_embedder


def test_hashing_deterministic_and_normalized():
    emb = HashingEmbedder(dim=128)
    a = emb.encode(["the quick brown fox"])
    b = emb.encode(["the quick brown fox"])
    assert a.shape == (1, 128)
    assert np.allclose(a, b)
    assert np.isclose(np.linalg.norm(a[0]), 1.0, atol=1e-5)


def test_hashing_similarity_orders_sensibly():
    emb = HashingEmbedder(dim=256)
    vecs = emb.encode([
        "machine learning models and neural networks",
        "deep neural networks for machine learning",
        "a recipe for chocolate cake with sugar",
    ])
    sim_related = float(vecs[0] @ vecs[1])
    sim_unrelated = float(vecs[0] @ vecs[2])
    assert sim_related > sim_unrelated


def test_empty_text_is_zero_then_safe():
    emb = HashingEmbedder(dim=64)
    v = emb.encode([""])
    assert v.shape == (1, 64)
    assert np.all(np.isfinite(v))


def test_build_embedder_factory():
    assert isinstance(build_embedder("hashing", ""), HashingEmbedder)
    try:
        build_embedder("nonsense", "")
        assert False, "should raise"
    except ValueError:
        pass
