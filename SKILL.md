---
name: local-notebooklm
description: >-
  Local, multimodal NotebookLM as a CLI skill. Use when the user wants to build
  a NOTEBOOK from their own SOURCES and ask grounded questions about them — chat
  with / query / summarize a folder of PDFs, images, audio, or video; "talk to
  my documents"; RAG over local files with citations; a private/offline
  NotebookLM alternative. Triggers on: notebook, sources, multimodal RAG,
  "query my PDFs/audio/video", "ground answers in my files", local NotebookLM.
---

# Local NotebookLM

A local, multimodal retrieval system: turn a folder of files (PDF, images,
audio, video) into a **source-grounded notebook** and chat about them in a
browser. Answers come **only from the selected sources**, with **citations**.
Everything runs locally; the model is reached through your own CLI.

## When to use this skill

- The user wants to ask questions about **their own documents/media** and have
  answers **grounded with citations** (not free-form generation).
- They mention a **notebook**, **sources**, **"query my files"**, **multimodal
  RAG**, or a **local/offline NotebookLM**.
- They want to chat with **PDFs, scanned docs, images, audio, or video**.

## What it does

1. Starts a local server with a browser UI (default <http://127.0.0.1:8008>).
   The start screen shows all **Vellums** (separate notebooks); pick one or
   create a new one (name + optional category) to enter it.
2. Inside a Vellum the user adds **folders or files** via a built-in file
   browser (no path typing); an ingestion pipeline extracts
   text (PDF text/OCR, image OCR + filename caption, audio transcription, video
   keyframes + transcription), chunks it, and stores embeddings in a **local**
   vector store. (Images are matched via OCR'd text/caption, not a vision model.)
3. The user chats; the server retrieves the most relevant chunks, builds a
   **strictly source-bound prompt**, and sends it to the configured CLI
   (`claude-code` / `hermes` / `codex` / generic `command`).
4. Answers stream back with **[S#] citations** linking to file + page/timestamp.
   Anything not in the sources is reported as *"not covered by the sources."*

## Quick start

```bash
# from the skill directory (macOS/Linux)
./vellum
# on Windows (PowerShell/cmd): vellum   or   .\vellum
```

The launcher is cross-platform: a small `vellum.py` holds the logic, with
`vellum` (bash) and `vellum.cmd` (Windows) as thin shims. First run launches a
short setup wizard (provider, language, network visibility, data folder, port,
modalities, embeddings, color), writes a commented `.env`, provisions a
virtualenv with the light core deps, installs the secret-scan git hook, and
starts the server. Afterwards `./vellum` just starts it. Open the printed URL,
paste a folder/file path into **Sources**, wait for ingestion, then ask
questions. Stop with Ctrl-C.

Re-run setup any time with `./vellum init --reconfigure`; for CI use
`./vellum init --yes` plus flags.

## Staying up to date

`./vellum update` fast-forwards to the latest version (git checkout) and
reinstalls dependencies. On an interactive start, Vellum briefly checks for a
newer version and asks **Yes/No** before installing it (default No). Set
`VELLUM_NO_UPDATE_CHECK=1` to disable that check.

## Multiple Vellums & CLI/agent access

Each notebook ("Vellum") is fully isolated — its own folder and index under
`data/notebooks/<id>/`. Create, rename, sort by category, and delete them from
the start screen. A CLI agent (or you) can query exactly one Vellum from the
terminal, grounded only in that Vellum's files:

```bash
./vellum notebooks                          # list Vellums and their ids
./vellum ask -n biology-101 "Define osmosis"
./vellum ask -n "Biology 101" "..." --json  # {answer, citations}
./vellum ask -n biology-101 "..." --sources-only   # retrieved context, no model
```

So when told "use the `biology-101` Vellum", an agent runs `vellum ask -n
biology-101 …` and answers from those documents alone — directly in the CLI.

## Choosing the model

The web UI has a **model picker** (with search) in the top bar; the chosen model
is passed to your CLI adapter as `--model`. `vellum ask` accepts `--model` too.
Set a default with `MMRAG_MODEL=…`. Available ids per provider live in
`server/model_catalog.py` (curated, offline — edit as new models ship).

## Configure the CLI bridge

The UI does **not** call a hosted API directly — it forwards prompts to the
local CLI you choose. Set the adapter via env (or `config.yaml`):

```bash
export MMRAG_CLI_ADAPTER=claude-code   # claude-code | hermes | codex | command
```

For the generic adapter, point it at any CLI that reads a prompt on stdin:

```bash
export MMRAG_CLI_ADAPTER=command
export MMRAG_CLI_COMMAND="my-llm-cli --stdin"
```

Copy `.env.example` → `.env` (or `config.example.yaml` → `config.yaml`) for all
options. Both real files are gitignored. See
[`references/configuration.md`](references/configuration.md).

## Optional capabilities

The core install is intentionally light (documents + image captions work out of
the box with the dependency-free hashing embedder). Enable more when needed:

- **Semantic embeddings:** `pip install -r requirements-optional.txt` and set
  `MMRAG_EMBEDDER=sentence-transformers`.
- **Audio/video transcription:** install `faster-whisper` + `ffmpeg`, set
  `MMRAG_TRANSCRIBER=faster-whisper`.
- **OCR (scanned PDFs / text in images):** install `pytesseract`, plus the
  `tesseract` and `poppler-utils` system packages.

## Supported file types

Documents: pdf, txt, md, docx, pptx, csv, html · Images: png, jpg, jpeg, webp,
gif · Audio: mp3, wav, m4a, flac · Video: mp4, mov, mkv.

## Privacy

All sources, transcripts, embeddings, and the vector store live under the local,
gitignored `data/` directory. No telemetry, no phone-home, no third-party CDN.
The server binds to `127.0.0.1` by default. See
[`references/security.md`](references/security.md).

## More detail

- Architecture: [`references/architecture.md`](references/architecture.md)
- Configuration reference: [`references/configuration.md`](references/configuration.md)
- Security & privacy: [`references/security.md`](references/security.md)
