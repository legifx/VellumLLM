# Contributing to Local NotebookLM

Thanks for your interest! This project is open source under the [MIT license](LICENSE).

## Ground rules

1. **Never commit secrets, PII, or user data.** API keys, tokens, passwords,
   personal emails, absolute home paths, and real source files (PDFs, images,
   audio, video) must never enter the repo or its history. The pre-commit hook
   and `scripts/secret_scan.py` enforce this — keep them passing.
2. **Local-first.** No telemetry, no analytics, no third-party CDN, no required
   cloud service. User data stays in the gitignored `data/` directory.
3. **Keep the core light.** Heavy ML dependencies (torch, whisper) are optional
   extras, never core requirements.

## Getting set up

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
bash scripts/install-hooks.sh
pytest
```

## Before you open a PR

- [ ] `pytest` passes.
- [ ] `ruff check .` is clean (style).
- [ ] `python scripts/secret_scan.py --all` passes.
- [ ] Commits are small and have clear messages.
- [ ] New behavior has tests for the critical paths (ingestion, retrieval, adapters).

## Adding a CLI adapter

Implement the `CLIAdapter` interface in `server/cli_bridge/` and register it in
the adapter factory. Adapters receive a fully-built prompt and return the
model's answer (streaming optional). Don't hardcode paths or credentials —
read them from config/env.

## Reporting issues

Please don't paste real secrets or private documents into issues. Redact paths
and use small, shareable sample files.
