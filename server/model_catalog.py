"""Curated, offline model lists shown in the UI model picker.

No network and no API keys: each provider has a hand-maintained list of model
ids the user can pick from. The chosen id is passed straight to the CLI adapter
(``--model <id>``), so it must match what that CLI accepts. Edit these lists as
new models ship — keeping them here keeps Vellum dependency- and key-free.
"""
from __future__ import annotations

# Each entry: (id, human label). The id is what gets passed to the CLI.
_CLAUDE = [
    ("claude-opus-4-8", "Claude Opus 4.8"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
    ("claude-fable-5", "Claude Fable 5"),
]

# Models reachable through Hermes' OpenRouter / Nous Research routing. These use
# the provider-prefixed ids those gateways expect.
_HERMES = [
    ("anthropic/claude-opus-4-8", "Claude Opus 4.8 (OpenRouter)"),
    ("anthropic/claude-sonnet-4-6", "Claude Sonnet 4.6 (OpenRouter)"),
    ("openai/gpt-5", "GPT-5 (OpenRouter)"),
    ("openai/gpt-5-mini", "GPT-5 mini (OpenRouter)"),
    ("google/gemini-2.5-pro", "Gemini 2.5 Pro (OpenRouter)"),
    ("meta-llama/llama-4-70b-instruct", "Llama 4 70B (OpenRouter)"),
    ("deepseek/deepseek-v3", "DeepSeek V3 (OpenRouter)"),
    ("nousresearch/hermes-4-70b", "Hermes 4 70B (Nous)"),
]

_CODEX = [
    ("gpt-5", "GPT-5"),
    ("gpt-5-mini", "GPT-5 mini"),
    ("o4-mini", "o4-mini"),
]

_CATALOG: dict[str, list[tuple[str, str]]] = {
    "claude-code": _CLAUDE,
    "hermes": _HERMES,
    "codex": _CODEX,
    "command": [],  # generic command: model is baked into the command itself
}


def models_for(adapter: str) -> list[dict[str, str]]:
    """Return ``[{id, label}, ...]`` for the given adapter (possibly empty)."""
    return [{"id": i, "label": label}
            for i, label in _CATALOG.get((adapter or "").lower(), [])]
