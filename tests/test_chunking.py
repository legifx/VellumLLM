from server.chunking import TextPiece, chunk_pieces


def test_short_text_single_chunk():
    out = chunk_pieces([TextPiece("hello world", "p. 1")], chunk_size=100, overlap=10)
    assert len(out) == 1
    assert out[0].locator == "p. 1"


def test_long_text_splits_with_overlap_and_keeps_locator():
    text = " ".join(f"word{i}" for i in range(500))
    out = chunk_pieces([TextPiece(text, "p. 2")], chunk_size=200, overlap=40)
    assert len(out) > 1
    assert all(c.locator == "p. 2" for c in out)
    assert all(len(c.text) <= 260 for c in out)  # size + slack from boundary search


def test_empty_pieces_dropped():
    out = chunk_pieces([TextPiece("   ", "x")], chunk_size=50, overlap=5)
    assert out == []
