"""Runtime configuration.

Resolution order (highest precedence first):
    1. Process environment variables (MMRAG_* / VELLUM_*)
    2. A local .env file (written by `vellum init`; gitignored)
    3. config.yaml in the project root (gitignored; optional)
    4. Built-in defaults

No secrets, paths, or credentials are hardcoded here. A missing required value
raises a clear error explaining what to set — never a sample secret.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# VELLUM_* is accepted as a friendly alias for the canonical MMRAG_* names.
_ALIAS_PREFIX = ("VELLUM_", "MMRAG_")


def load_dotenv(path: Path | None = None) -> None:
    """Load a simple KEY=VALUE .env into os.environ without overriding values
    already present in the real environment. No external dependency."""
    env_path = path or Path(os.environ.get("VELLUM_ENV_FILE", PROJECT_ROOT / ".env"))
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _apply_aliases() -> None:
    """Mirror VELLUM_X -> MMRAG_X when only the alias is set."""
    for key in list(os.environ):
        if key.startswith("VELLUM_"):
            canonical = "MMRAG_" + key[len("VELLUM_"):]
            os.environ.setdefault(canonical, os.environ[key])


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # optional dependency
    except ImportError:
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _get(env_key: str, yaml_section: dict, yaml_key: str, default: Any) -> Any:
    if env_key in os.environ and os.environ[env_key] != "":
        return os.environ[env_key]
    if yaml_key in yaml_section and yaml_section[yaml_key] is not None:
        return yaml_section[yaml_key]
    return default


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8008
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    language: str = "en"

    cli_adapter: str = "claude-code"
    cli_command: str = ""
    cli_timeout: int = 120
    claude_bin: str = "claude"
    hermes_bin: str = "hermes"
    codex_bin: str = "codex"

    embedder: str = "hashing"
    st_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    transcriber: str = "disabled"
    whisper_model: str = "base"

    top_k: int = 6
    chunk_size: int = 1000
    chunk_overlap: int = 150

    @classmethod
    def load(cls, config_path: Path | None = None) -> Config:
        load_dotenv()
        _apply_aliases()
        cfg_file = config_path or (PROJECT_ROOT / "config.yaml")
        y = _load_yaml(cfg_file)
        server = y.get("server", {}) or {}
        cli = y.get("cli", {}) or {}
        emb = y.get("embeddings", {}) or {}
        tr = y.get("transcription", {}) or {}
        ret = y.get("retrieval", {}) or {}

        data_dir = Path(_get("MMRAG_DATA_DIR", server, "data_dir", "data"))
        if not data_dir.is_absolute():
            data_dir = PROJECT_ROOT / data_dir

        return cls(
            host=str(_get("MMRAG_HOST", server, "host", "127.0.0.1")),
            port=int(_get("MMRAG_PORT", server, "port", 8008)),
            data_dir=data_dir,
            language=str(_get("MMRAG_LANGUAGE", server, "language", "en")),
            cli_adapter=str(_get("MMRAG_CLI_ADAPTER", cli, "adapter", "claude-code")),
            cli_command=str(_get("MMRAG_CLI_COMMAND", cli, "command", "")),
            cli_timeout=int(_get("MMRAG_CLI_TIMEOUT", cli, "timeout", 120)),
            claude_bin=str(_get("MMRAG_CLAUDE_BIN", cli, "claude_bin", "claude")),
            hermes_bin=str(_get("MMRAG_HERMES_BIN", cli, "hermes_bin", "hermes")),
            codex_bin=str(_get("MMRAG_CODEX_BIN", cli, "codex_bin", "codex")),
            embedder=str(_get("MMRAG_EMBEDDER", emb, "backend", "hashing")),
            st_model=str(_get("MMRAG_ST_MODEL", emb, "st_model",
                              "sentence-transformers/all-MiniLM-L6-v2")),
            transcriber=str(_get("MMRAG_TRANSCRIBER", tr, "backend", "disabled")),
            whisper_model=str(_get("MMRAG_WHISPER_MODEL", tr, "whisper_model", "base")),
            top_k=int(_get("MMRAG_TOP_K", ret, "top_k", 6)),
            chunk_size=int(_get("MMRAG_CHUNK_SIZE", ret, "chunk_size", 1000)),
            chunk_overlap=int(_get("MMRAG_CHUNK_OVERLAP", ret, "chunk_overlap", 150)),
        )

    # Derived paths (all under the gitignored data dir).
    @property
    def db_path(self) -> Path:
        return self.data_dir / "notebook.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
