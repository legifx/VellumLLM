from server.notebooks import NotebookRegistry, slugify


def test_slugify():
    assert slugify("Biology 101") == "biology-101"
    assert slugify("  Über/Café!! ") == "ber-caf"
    assert slugify("") == "vellum"


def test_create_list_update_delete(tmp_path):
    reg = NotebookRegistry(tmp_path / "nb")
    a = reg.create("Biology 101", "School")
    assert a.id == "biology-101"
    assert reg.exists(a.id)
    assert reg.db_path(a.id).parent.name == a.id

    # unique ids on name collision
    b = reg.create("Biology 101")
    assert b.id == "biology-101-2"

    assert {n.id for n in reg.list()} == {a.id, b.id}

    upd = reg.update(a.id, name="Bio", category="Sci")
    assert upd.name == "Bio" and upd.category == "Sci"
    assert reg.get(a.id).name == "Bio"

    assert reg.delete(a.id) is True
    assert not reg.exists(a.id)
    assert reg.delete("missing") is False


def test_migrate_legacy_single_pool(tmp_path):
    legacy = tmp_path / "notebook.sqlite3"
    legacy.write_bytes(b"SQLite format 3\x00")
    reg = NotebookRegistry(tmp_path / "nb")
    nb = reg.migrate_legacy(legacy, name="My Vellum")
    assert nb is not None
    assert reg.db_path(nb.id).exists()
    assert not legacy.exists()  # moved in
    # second call is a no-op (notebooks already exist)
    assert reg.migrate_legacy(legacy) is None
