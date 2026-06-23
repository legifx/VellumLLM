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
2. The user adds **folders or files** as sources; an ingestion pipeline extracts
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
# from the skill directory
bash scripts/start.sh
```

This provisions a virtualenv, installs the light core dependencies, installs the
secret-scan git hook, and launches the server. Open the printed URL, paste a
folder/file path into **Sources**, wait for ingestion, then ask questions.

Stop with Ctrl-C.

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
