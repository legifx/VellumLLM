import pytest

from server import fsbrowse


def test_shortcuts_include_a_root():
    labels = [s["label"] for s in fsbrowse.shortcuts()]
    # A drive (Windows) or "/ (root)" (POSIX) is always offered, plus Home.
    assert any("root" in s.lower() or s.endswith(":") for s in labels)
    assert "Home" in labels


def test_list_dir_lists_supported_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "ignore.xyz").write_text("no", encoding="utf-8")
    out = fsbrowse.list_dir(str(tmp_path))
    names = {e["name"] for e in out["entries"]}
    assert "sub" in names and "notes.txt" in names
    assert "ignore.xyz" not in names          # unsupported extension hidden
    assert out["parent"] == str(tmp_path.parent)


def test_search_dir_finds_nested_supported_file(tmp_path):
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "report.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "a" / "skip.bin").write_text("x", encoding="utf-8")
    res = fsbrowse.search_dir(str(tmp_path), "report")
    names = {r["name"] for r in res["results"]}
    assert "report.pdf" in names
    assert res["truncated"] is False


def test_search_dir_empty_query_rejected(tmp_path):
    with pytest.raises(ValueError):
        fsbrowse.search_dir(str(tmp_path), "   ")
