from server.config import Config
from server.embeddings import HashingEmbedder
from server.ingest import detect_modality, expand_paths, process_source, register_source
from server.ingest.audio import extract_audio
from server.ingest.documents import extract_csv, extract_document, extract_html, extract_pdf
from server.ingest.images import extract_image
from server.store import Store


def test_detect_modality():
    from pathlib import Path
    assert detect_modality(Path("a.pdf")) == "document"
    assert detect_modality(Path("a.PNG")) == "image"
    assert detect_modality(Path("a.mp3")) == "audio"
    assert detect_modality(Path("a.mkv")) == "video"
    assert detect_modality(Path("a.xyz")) is None


def test_extract_txt_and_csv_and_html(sample_txt, sample_csv, sample_html):
    assert "New Selene" in extract_document(sample_txt)[0].text
    csv_pieces = extract_csv(sample_csv)
    assert any("admiral" in p.text for p in csv_pieces)
    html_pieces = extract_html(sample_html)
    assert "Hello world" in html_pieces[0].text
    assert "<b>" not in html_pieces[0].text


def test_extract_pdf_pages_with_locator(sample_pdf):
    pieces = extract_pdf(sample_pdf)
    assert len(pieces) == 2
    assert pieces[0].locator == "p. 1"
    assert "revenue" in pieces[0].text.lower()
    assert pieces[1].locator == "p. 2"


def test_extract_image_caption(sample_image):
    pieces = extract_image(sample_image)
    assert pieces
    assert "diagram solar panel" in pieces[0].text


def test_extract_audio_disabled_caption(sample_audio):
    pieces = extract_audio(sample_audio, "disabled", "base")
    assert len(pieces) == 1
    assert "not available" in pieces[0].text.lower()


def test_expand_paths_recurses_dir(tmp_path, sample_txt, sample_csv):
    found = expand_paths([str(tmp_path)])
    names = {p.name for p in found}
    assert {"notes.txt", "data.csv"} <= names


def test_full_pipeline_incremental(tmp_path, sample_txt):
    cfg = Config(data_dir=tmp_path / "data")
    cfg.ensure_dirs()
    store = Store(cfg.db_path)
    emb = HashingEmbedder(dim=128)

    src = register_source(store, sample_txt)
    out = process_source(store, emb, cfg, src.id)
    assert out.status == "ready"
    assert out.chunk_count >= 1
    first_hash = out.content_hash

    # re-process unchanged -> skipped, same hash, still ready
    out2 = process_source(store, emb, cfg, src.id)
    assert out2.status == "ready"
    assert out2.content_hash == first_hash
