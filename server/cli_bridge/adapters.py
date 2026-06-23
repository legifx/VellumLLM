"""Concrete CLI adapters: claude-code, hermes, codex, and a generic command.

Each adapter knows how to invoke its CLI in a non-interactive, single-shot
"answer this prompt from stdin" mode. Binaries and the generic command are
configurable (never hardcoded credentials or paths).
"""
from __future__ import annotations

import shlex

from ..config import Config
from .base import CLIAdapter, CLIError


class ClaudeCodeAdapter(CLIAdapter):
    name = "claude-code"

    def __init__(self, cfg: Config):
        self._bin = cfg.claude_bin

    def command(self) -> list[str]:
        # `claude -p` runs Claude Code in non-interactive print mode, reading
        # the prompt from stdin and streaming the answer to stdout.
        return [self._bin, "-p"]


class HermesAdapter(CLIAdapter):
    name = "hermes"

    def __init__(self, cfg: Config):
        self._bin = cfg.hermes_bin

    def command(self) -> list[str]:
        # Hermes is invoked in one-shot mode, prompt on stdin.
        return [self._bin, "ask", "-"]


class CodexAdapter(CLIAdapter):
    name = "codex"

    def __init__(self, cfg: Config):
        self._bin = cfg.codex_bin

    def command(self) -> list[str]:
        # `codex exec` runs a single non-interactive turn; "-" reads stdin.
        return [self._bin, "exec", "-"]


class CommandAdapter(CLIAdapter):
    name = "command"

    def __init__(self, cfg: Config):
        if not cfg.cli_command.strip():
            raise CLIError(
                "MMRAG_CLI_ADAPTER=command requires MMRAG_CLI_COMMAND to be set "
                "to a CLI that reads a prompt on stdin and writes the answer to "
                "stdout (e.g. 'my-llm-cli --stdin')."
            )
        self._argv = shlex.split(cfg.cli_command)

    def command(self) -> list[str]:
        return self._argv


_REGISTRY = {
    "claude-code": ClaudeCodeAdapter,
    "hermes": HermesAdapter,
    "codex": CodexAdapter,
    "command": CommandAdapter,
}


def build_adapter(cfg: Config) -> CLIAdapter:
    key = (cfg.cli_adapter or "claude-code").lower()
    if key not in _REGISTRY:
        raise CLIError(
            f"Unknown CLI adapter '{key}'. Set MMRAG_CLI_ADAPTER to one of: "
            f"{', '.join(_REGISTRY)}."
        )
    return _REGISTRY[key](cfg)


def available_adapters() -> list[str]:
    return list(_REGISTRY)
