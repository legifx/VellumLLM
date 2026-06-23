"""Runtime configuration.

Resolution order (highest precedence first):
    1. Environment variables (MMRAG_*)
    2. config.yaml in the project root (gitignored; optional)
    3. Built-in defaults

No secrets, paths, or credentials are hardcoded here. A missing required value
raises a clear error explaining what to set — never a sample secret.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
