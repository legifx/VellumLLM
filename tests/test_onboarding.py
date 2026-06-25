import builtins

from server.onboarding import (
    ADAPTER_OPTS,
    MODALITY_OPTS,
    NETWORK_OPTS,
    NETWORK_WARN,
    Prompter,
    Style,
    _v_modalities,
    _v_port,
    build_parser,
    read_env,
    run,
    write_env,
)


# ---- validators ----
def test_v_port():
    assert _v_port("8008") == (True, 8008)
    assert _v_port("80")[0] is False       # below 1024
    assert _v_port("99999")[0] is False    # above range
    assert _v_port("abc")[0] is False


def test_v_modalities_forces_text_and_rejects_unknown():
    ok, parsed = _v_modalities("image,audio")
    assert ok and parsed[0] == "text" and "audio" in parsed
    assert _v_modalities("text,hologram")[0] is False


# ---- env io ----
def test_write_and_read_env_roundtrip(tmp_path):
    env = tmp_path / ".env"
    cfg = {"adapter": "command", "command": "my-llm --stdin", "language": "de",
           "data_dir": "data", "port": 9100, "modalities": ["text", "image"],
           "transcriber": "disabled", "embedder": "hashing", "color": "1"}
    write_env(env, cfg, extra=["MMRAG_TOP_K=8"])
    got = read_env(env)
    assert got["MMRAG_CLI_ADAPTER"] == "command"
    assert got["MMRAG_CLI_COMMAND"] == "my-llm --stdin"
    assert got["MMRAG_LANGUAGE"] == "de"
    assert got["MMRAG_PORT"] == "9100"
    assert got["MMRAG_TOP_K"] == "8"  # preserved custom key


# ---- prompter ----
def test_prompter_non_interactive_uses_default():
    p = Prompter(interactive=False, style=Style(False))
    assert p.ask("X", "explain", "abc") == "abc"
    assert p.ask("P", "port", "8008", validate=_v_port) == 8008


def test_prompter_interactive_validates_and_reprompts(monkeypatch):
    answers = iter(["", "70000", "8080"])  # "" -> default (valid) returns immediately
    monkeypatch.setattr(builtins, "input", lambda _="": next(answers))
    p = Prompter(interactive=True, style=Style(False))
    # default 8008; first "" -> default 8008 is valid, returns immediately
    assert p.ask("Port", "explain", "8008", validate=_v_port) == 8008


def test_prompter_interactive_rejects_then_accepts(monkeypatch):
    answers = iter(["70000", "8080"])
    monkeypatch.setattr(builtins, "input", lambda _="": next(answers))
    p = Prompter(interactive=True, style=Style(False))
    assert p.ask("Port", "explain", "abc", validate=_v_port) == 8080


# ---- end to end (non-interactive) ----
def test_run_writes_env_non_interactive(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    data = tmp_path / "mydata"
    monkeypatch.setenv("VELLUM_ENV_FILE", str(env))
    args = build_parser().parse_args(
        ["--yes", "--port", "9211", "--lang", "de", "--adapter", "codex",
         "--modalities", "text,image,audio", "--data-dir", str(data)])
    rc = run(args)
    assert rc == 0
    got = read_env(env)
    assert got["MMRAG_PORT"] == "9211"
    assert got["MMRAG_LANGUAGE"] == "de"
    assert got["MMRAG_CLI_ADAPTER"] == "codex"
    assert got["MMRAG_TRANSCRIBER"] == "faster-whisper"  # audio enabled
    assert data.exists()  # data dir created


def test_select_by_number_and_default(monkeypatch):
    p = Prompter(interactive=True, style=Style(False))
    monkeypatch.setattr(builtins, "input", lambda _="": "2")
    assert p.select("Provider", "x", ADAPTER_OPTS, "claude-code") == ADAPTER_OPTS[1][0]
    monkeypatch.setattr(builtins, "input", lambda _="": "")  # Enter -> default
    assert p.select("Provider", "x", ADAPTER_OPTS, "hermes") == "hermes"


def test_select_non_interactive_returns_default():
    p = Prompter(interactive=False, style=Style(False))
    assert p.select("Net", "x", NETWORK_OPTS, "0.0.0.0") == "0.0.0.0"


def test_select_warns_on_exposed_host(monkeypatch, capsys):
    p = Prompter(interactive=True, style=Style(False))
    monkeypatch.setattr(builtins, "input", lambda _="": "2")  # 0.0.0.0
    chosen = p.select("Net", "x", NETWORK_OPTS, "127.0.0.1", warn_on=NETWORK_WARN)
    assert chosen == "0.0.0.0"
    assert "exposes" in capsys.readouterr().out


def test_multiselect_forces_text_and_parses_numbers(monkeypatch):
    p = Prompter(interactive=True, style=Style(False))
    monkeypatch.setattr(builtins, "input", lambda _="": "3")  # audio only -> text+audio
    chosen = p.multiselect("Mod", "x", MODALITY_OPTS, ["text"], forced=("text",))
    assert chosen[0] == "text" and "audio" in chosen


def test_run_writes_host_non_interactive(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setenv("VELLUM_ENV_FILE", str(env))
    args = build_parser().parse_args(
        ["--yes", "--host", "0.0.0.0", "--data-dir", str(tmp_path / "d")])
    assert run(args) == 0
    assert read_env(env)["MMRAG_HOST"] == "0.0.0.0"


def test_reconfigure_prefills_from_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("MMRAG_PORT=7777\nMMRAG_CLI_ADAPTER=hermes\nMMRAG_LANGUAGE=de\n"
                   "MMRAG_DATA_DIR=" + str(tmp_path / "d") + "\nMMRAG_EMBEDDER=hashing\n"
                   "MMRAG_TRANSCRIBER=disabled\n", encoding="utf-8")
    monkeypatch.setenv("VELLUM_ENV_FILE", str(env))
    # non-interactive reconfigure with no overriding flags -> keeps prior values
    args = build_parser().parse_args(["--yes", "--reconfigure"])
    assert run(args) == 0
    got = read_env(env)
    assert got["MMRAG_PORT"] == "7777"
    assert got["MMRAG_CLI_ADAPTER"] == "hermes"
