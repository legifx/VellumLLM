# Security & privacy

Local NotebookLM is **local-first** by design. This document states the
guarantees and how they are enforced.

## Data never leaves your machine

- Sources, extracted text, transcripts, embeddings, the vector store, and caches
  all live under the local `data/` directory, which is **gitignored**.
- There is **no telemetry, no analytics, no phone-home, and no third-party CDN**.
  The web UI ships its own CSS/JS; it loads nothing from the internet.
- The only outbound activity is whatever **your chosen CLI** does when *you* ask
  a question. This project stores no API keys and asks for none.

## Network exposure

- The server binds to **`127.0.0.1`** by default — reachable only from your
  machine.
- Binding elsewhere (`MMRAG_HOST`) is an explicit opt-in. The startup banner
  prints a warning if you do. There is no authentication layer, so do **not**
  expose it to an untrusted network. If you must, put it behind your own
  reverse proxy with auth and TLS.

## No secrets in the repository

This is a public, open-source project. The following are enforced so nothing
sensitive is ever committed:

1. **`.gitignore`** blocks `.env`, keys, `config.yaml`, and every data directory
   (`data/`, `sources/`, `vectorstore/`, `transcripts/`, `embeddings/`, `*.db`,
   logs, …).
2. **`scripts/secret_scan.py`** scans for credential and PII patterns
   (API keys, tokens, private keys, JWTs, home paths, emails) and exits non-zero
   on any finding. Documented placeholders are ignored.
3. **`scripts/pre-commit`** (installed via `scripts/install-hooks.sh`) runs the
   scanner and hard-blocks staged secret/data paths before every commit.

Run it any time:

```bash
python scripts/secret_scan.py --all
```

## Configuration is secret-free

All environment-specific values come from environment variables or a local,
gitignored `config.yaml`. The code contains **no default secrets, no real
paths, and no credentials**. A missing required value produces a clear error
explaining what to set — never an example secret.

## Reporting a vulnerability

Please open an issue describing the problem **without** including secrets or
private documents, or contact the maintainers privately if the issue is
sensitive.
