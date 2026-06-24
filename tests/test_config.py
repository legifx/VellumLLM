from server.config import Config, load_dotenv


def _clear(monkeypatch, *keys):
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def test_load_dotenv_does_not_override_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("MMRAG_PORT=1234\nMMRAG_LANGUAGE=de\n", encoding="utf-8")
    monkeypatch.setenv("VELLUM_ENV_FILE", str(env))
    monkeypatch.setenv("MMRAG_PORT", "9999")  # real env wins
    _clear(monkeypatch, "MMRAG_LANGUAGE")
    load_dotenv()
    import os
    assert os.environ["MMRAG_PORT"] == "9999"
    assert os.environ["MMRAG_LANGUAGE"] == "de"


def test_config_load_reads_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("MMRAG_PORT=8123\nMMRAG_LANGUAGE=de\nMMRAG_CLI_ADAPTER=codex\n",
                   encoding="utf-8")
    monkeypatch.setenv("VELLUM_ENV_FILE", str(env))
    _clear(monkeypatch, "MMRAG_PORT", "MMRAG_LANGUAGE", "MMRAG_CLI_ADAPTER")
    cfg = Config.load()
    assert cfg.port == 8123
    assert cfg.language == "de"
    assert cfg.cli_adapter == "codex"


def test_vellum_alias_maps_to_mmrag(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("VELLUM_PORT=8222\n", encoding="utf-8")
    monkeypatch.setenv("VELLUM_ENV_FILE", str(env))
    _clear(monkeypatch, "MMRAG_PORT", "VELLUM_PORT")
    cfg = Config.load()
    assert cfg.port == 8222
