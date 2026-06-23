# Configuration reference

Configuration resolves in this order (highest precedence first):

1. **Environment variables** (`MMRAG_*`)
2. **`config.yaml`** in the project root (gitignored; optional)
3. **Built-in defaults**

Copy a template to start: `cp .env.example .env` or
`cp config.example.yaml config.yaml`. Both real files are gitignored. Never put
secrets in either — this project needs none.

## Variables

| Env var | config.yaml | Default | Meaning |
|---------|-------------|---------|---------|
| `MMRAG_HOST` | `server.host` | `127.0.0.1` | Bind address. Change only with care (see security). |
| `MMRAG_PORT` | `server.port` | `8008` | Server port. |
| `MMRAG_DATA_DIR` | `server.data_dir` | `data` | Local data directory (gitignored). |
| `MMRAG_CLI_ADAPTER` | `cli.adapter` | `claude-code` | `claude-code` \| `hermes` \| `codex` \| `command`. |
| `MMRAG_CLI_COMMAND` | `cli.command` | — | For the `command` adapter: a CLI that reads a prompt on stdin. |
| `MMRAG_CLI_TIMEOUT` | `cli.timeout` | `120` | Seconds to wait for the CLI to answer. |
| `MMRAG_CLAUDE_BIN` | `cli.claude_bin` | `claude` | Override the claude binary name/path. |
| `MMRAG_HERMES_BIN` | `cli.hermes_bin` | `hermes` | Override the hermes binary. |
| `MMRAG_CODEX_BIN` | `cli.codex_bin` | `codex` | Override the codex binary. |
| `MMRAG_EMBEDDER` | `embeddings.backend` | `hashing` | `hashing` (no deps) \| `sentence-transformers`. |
| `MMRAG_ST_MODEL` | `embeddings.st_model` | `all-MiniLM-L6-v2` | Model when using sentence-transformers. |
| `MMRAG_TRANSCRIBER` | `transcription.backend` | `disabled` | `disabled` \| `faster-whisper` \| `whisper`. |
| `MMRAG_WHISPER_MODEL` | `transcription.whisper_model` | `base` | Whisper model size. |
| `MMRAG_TOP_K` | `retrieval.top_k` | `6` | Chunks retrieved per query. |
| `MMRAG_CHUNK_SIZE` | `retrieval.chunk_size` | `1000` | Target chunk size (characters). |
| `MMRAG_CHUNK_OVERLAP` | `retrieval.chunk_overlap` | `150` | Overlap between chunks. |

## CLI adapter notes

- **claude-code** *(verified)* — runs `claude -p` (non-interactive print mode),
  prompt on stdin.
- **hermes** *(unverified default)* — runs `hermes ask -`, prompt on stdin.
- **codex** *(unverified default)* — runs `codex exec -`, prompt on stdin.
- **command** *(recommended when in doubt)* — runs `MMRAG_CLI_COMMAND` verbatim,
  prompt on stdin, answer from stdout. Use this for any other local LLM CLI.

> The `hermes` and `codex` invocations are reasonable defaults, but the exact
> sub-command and flags differ between releases of those tools (and "Hermes" is
> an ambiguous name). If chat fails or behaves oddly, check the real one-shot
> syntax for *your* CLI, or just use the `command` adapter:
>
> ```bash
> export MMRAG_CLI_ADAPTER=command
> export MMRAG_CLI_COMMAND="your-cli <one-shot-flags>"   # reads stdin, writes stdout
> ```
>
> You can also override just the binary name without changing the invocation
> shape via `MMRAG_HERMES_BIN` / `MMRAG_CODEX_BIN` / `MMRAG_CLAUDE_BIN`.

If the configured CLI is not on `PATH`, `/api/config` reports
`adapter_available: false` and chat returns a clear error explaining what to set
— never a sample credential.

## Enabling optional features

```bash
# semantic embeddings
pip install -r requirements-optional.txt
export MMRAG_EMBEDDER=sentence-transformers

# transcription (needs ffmpeg on PATH)
pip install faster-whisper
export MMRAG_TRANSCRIBER=faster-whisper

# OCR (needs system tesseract + poppler-utils)
pip install pytesseract pdf2image
```

## Changing the embedder (important)

Different embedders produce vectors of different dimensions (e.g. the hashing
embedder is 256-d, `all-MiniLM-L6-v2` is 384-d). The vector index can only
compare vectors of the same dimension, so after you change `MMRAG_EMBEDDER`:

- Sources embedded with the *old* model are automatically **excluded from
  search** — they are never silently mixed in, and search will not crash.
- `GET /api/config` reports `needs_reprocess: true` and `stale_source_ids`.
- The UI shows a **"Reprocess all"** banner. Click it, or call:

  ```bash
  curl -X POST http://127.0.0.1:8008/api/sources/reprocess-all
  ```

This re-embeds every source with the current model so they rejoin the index.
