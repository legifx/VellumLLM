# Local NotebookLM

> A local, **multimodal** NotebookLM — packaged as a **CLI skill** for Claude Code, Hermes, and Codex.

Local NotebookLM turns a folder of your own files into a **source-grounded notebook**. Add PDFs, images, audio, and video; then chat about them in your browser. Answers come **only from your sources**, with **citations** pointing back to the exact file, page, or timestamp — like Google NotebookLM, but it runs on your machine and is driven by the coding/agent CLI you already use.

**Everything stays local.** No cloud vector database, no telemetry, no upload of your documents. The server binds to `127.0.0.1` by default.

---

## Why this exists

Coding/agent CLIs (Claude Code, Hermes, Codex) are great at answering questions — but they don't have a clean way to *ground* answers in a private, multimodal corpus. Local NotebookLM adds that: a small local server does ingestion + retrieval, builds a strictly source-bound prompt, and hands it to **your already-running CLI** through a pluggable **adapter**. The model never sees more than the chunks you retrieved, and every claim can be traced to a source.

---

## Features

- 🗂 **Pick sources from your machine** — folders or individual files, via the web UI.
- 🧩 **Multimodal ingestion**
  - **Documents:** `.pdf`, `.txt`, `.md`, `.docx`, `.pptx`, `.csv`, `.html` (PDF OCR fallback for scans)
  - **Images:** `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` (OCR of in-image text + a filename/metadata caption; **no vision-model understanding yet** — see [limitations](#limitations))
  - **Audio:** `.mp3`, `.wav`, `.m4a`, `.flac` (transcription)
  - **Video:** `.mp4`, `.mov`, `.mkv` (keyframes + audio transcription)
- 🔎 **Local vector store** — SQLite + NumPy by default. No external service, no paid DB.
- 🧠 **Embeddings, your choice** — a dependency-free **lexical** hashing embedder by default (keyword-style matching, instant, no downloads), or real **semantic** embeddings via the optional `sentence-transformers` backend.
- ♻️ **Incremental** — files are hashed; unchanged files are not re-processed.
- 💬 **Source-grounded chat** — strict system prompt; out-of-source questions are marked *"not in the sources."*
- 📌 **Citations** — every answer references file + page/timestamp; clickable in the UI.
- 🔌 **CLI bridge** — swap between `claude-code`, `hermes`, `codex`, or a generic `command` adapter via config.
- 🔒 **Local-first & private** — see [Privacy](#privacy).

---

## Architecture

```
┌─────────────────────────────┐
│        Browser UI           │  pick sources, chat, inspect citations
└──────────────┬──────────────┘
               │ HTTP / SSE (localhost only)
┌──────────────▼──────────────┐
│      Local server (FastAPI) │
│  ┌───────────────────────┐  │
│  │ Ingestion pipeline    │  │  PDF / image / audio / video → chunks
│  ├───────────────────────┤  │
│  │ Vector store          │  │  embeddings + metadata (SQLite + NumPy)
│  ├───────────────────────┤  │
│  │ Retrieval + prompt     │  │  build strictly source-bound context
│  ├───────────────────────┤  │
│  │ CLI bridge (adapters)  │  │  claude-code / hermes / codex / command
│  └───────────────────────┘  │
└─────────────────────────────┘
```

The model is reached **through the local CLI**, not a hosted API key baked into this project. See [`references/architecture.md`](references/architecture.md).

---

## Quick start

Requirements: **Python 3.10+**, and `ffmpeg` on your PATH if you want audio/video.

```bash
git clone https://github.com/legifx/VellumLLM.git
cd VellumLLM

# 1) install (creates a venv, installs core deps, sets up git hooks)
bash scripts/start.sh
```

`scripts/start.sh` checks dependencies, installs the core requirements into a
local virtualenv, starts the server, and prints the UI URL (default
<http://127.0.0.1:8008>). Open it in your browser, add a folder of sources, wait
for ingestion, and start chatting.

To configure, copy the examples (both are gitignored once renamed):

```bash
cp .env.example .env          # or: cp config.example.yaml config.yaml
```

### Optional heavy features

The core install is intentionally light. Enable the heavier capabilities when
you need them:

```bash
# real semantic embeddings (instead of the hashing fallback)
pip install -r requirements-optional.txt   # sentence-transformers, torch
# OCR for scanned PDFs / text-in-images
#   also install the tesseract binary via your OS package manager
# audio/video transcription
#   set MMRAG_TRANSCRIBER=faster-whisper (after installing faster-whisper)
```

See [`references/configuration.md`](references/configuration.md) for every knob.

---

## Use as a CLI skill

This repo is also a **skill**. Drop it where your CLI looks for skills (e.g.
`~/.claude/skills/`, `~/.agents/skills/`, or your Codex skills dir) and the
[`SKILL.md`](SKILL.md) frontmatter lets the CLI trigger it on prompts like
*"open a notebook for these PDFs"* or *"let me query this folder of sources."*

The active CLI adapter is chosen with `MMRAG_CLI_ADAPTER`
(`claude-code` | `hermes` | `codex` | `command`).

> **Adapter status:** the `claude-code` adapter (`claude -p`) is verified. The
> `hermes` and `codex` invocations are reasonable defaults but **not verified
> against every version** of those tools — flags differ between releases. If
> your CLI uses a different syntax, the most reliable option is the generic
> `command` adapter: set `MMRAG_CLI_COMMAND` to any CLI that reads a prompt on
> stdin and writes the answer to stdout. See
> [`references/configuration.md`](references/configuration.md).

---

## Supported file types

| Modality | Extensions | How it's processed |
|----------|------------|--------------------|
| Documents | pdf, txt, md, docx, pptx, csv, html | text extraction (+OCR fallback for scanned PDFs) |
| Images | png, jpg, jpeg, webp, gif | OCR of in-image text + filename/metadata caption (no vision model) |
| Audio | mp3, wav, m4a, flac | transcription (Whisper, optional) |
| Video | mp4, mov, mkv | keyframes (OCR) + audio transcription |

---

## Privacy

- **Your data never leaves your machine.** Sources, transcripts, embeddings,
  the vector store, and caches all live under a local, **gitignored** `data/`
  directory.
- **No telemetry, no analytics, no phone-home, no third-party CDN.**
- The server listens on **`127.0.0.1`** by default. Exposing it to a network is
  an explicit, documented opt-in (`MMRAG_HOST`) — do so only if you understand
  the risk.
- The model is reached through **your local CLI**; this project ships no API
  keys and asks for none.

See [`references/security.md`](references/security.md).

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
bash scripts/install-hooks.sh      # secret-scan + blocked-path pre-commit hook
pytest                             # run the test suite
python scripts/secret_scan.py --all
```

Contributions welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Limitations

Honest about what this does and doesn't do today:

- **Default embeddings are lexical, not semantic.** The dependency-free hashing
  embedder matches on shared tokens (keyword-style). For NotebookLM-grade
  semantic recall, install `requirements-optional.txt` and set
  `MMRAG_EMBEDDER=sentence-transformers`.
- **Images are not "understood" by a vision model.** Ingestion does OCR
  (text *in* the image) plus a caption built from the filename and dimensions.
  Images are therefore findable and citable via any text they contain, but a
  photo with no text carries little signal. True visual understanding would
  require adding a vision model to the ingestion step (a planned extension
  point — see `server/ingest/images.py`).
- **CLI adapters beyond `claude-code` are unverified** across tool versions; use
  the generic `command` adapter if flags differ (see above).
- **Switching the embedder changes the vector dimension.** Sources embedded with
  the old model are automatically **excluded from search** (no crash) and shown
  with a "Reprocess all" prompt in the UI. Click it — or `POST
  /api/sources/reprocess-all` — to re-embed everything with the current model.
- **No authentication.** The server is localhost-only by design; don't expose it
  to an untrusted network.

## FAQ

**Does it send my files anywhere?** No. Ingestion, embeddings, and the vector
store are entirely local. The only outbound interaction is whatever your chosen
CLI does when *you* ask it a question.

**Do I need a GPU?** No. The hashing embedder and base Whisper model run on CPU.
A GPU only speeds up the optional `sentence-transformers` / Whisper backends.

**Can it run fully offline?** Yes, once the optional models are downloaded. With
the default hashing embedder and transcription disabled, it needs nothing extra.

**Which CLIs are supported?** `claude-code`, `hermes`, `codex`, plus a generic
`command` adapter for any CLI that reads a prompt on stdin.

---

## License

[MIT](LICENSE) — open source. © 2026 Local NotebookLM contributors.
