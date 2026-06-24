<!-- hero -->
```
   ┏━━━━━━━━━━┓
   ┃ ╭──────╮ ┃
   ┃ │▁▁▁▁▁▁│ ┃
   ┃ │▁▁▁▁  │ ┃
   ┃ │▁▁▁▁▁▁│ ┃
   ┃ ╰──────╯ ┃
   ┗━━━━━━━━━━┛
      V E L L U M
   local · multimodal · yours
```

# Vellum

**Point Vellum at a folder of your files — PDFs, images, audio, video — and ask
questions about them. Answers come only from your sources, with citations.**
It's a local, multimodal NotebookLM you run from your own CLI, on your own
machine. Nothing is uploaded.

```bash
git clone https://github.com/legifx/VellumLLM.git
cd VellumLLM
./vellum            # guided setup, then opens at http://127.0.0.1:8008
```

---

## Why local & open

- **Your files never leave your machine.** Ingestion, embeddings, and the index
  are all local. The server binds to `127.0.0.1`. No telemetry, no CDN, no
  account.
- **Model-agnostic.** Vellum doesn't ship an API key or call a hosted model
  itself. It hands the prompt to a CLI you already run — `claude-code`, `codex`,
  `hermes`, or any command that reads stdin.
- **Grounded, not guessing.** Retrieval feeds the model only the relevant chunks
  under a strict prompt; every answer cites the file + page/timestamp it used,
  and off-source questions are marked *“not in the sources.”*

---

## Quickstart

```bash
./vellum            # first run: setup wizard → starts the server
```

That's it. The wizard asks a handful of well-defaulted questions (press Enter to
accept), writes a commented `.env`, and launches the UI. Open the printed URL,
paste a folder or file path into **Sources**, wait for ingestion, and ask away.

Other commands:

```bash
./vellum init --reconfigure   # change your settings later
./vellum start                # just start (skip setup)
./vellum doctor               # check prerequisites
```

**Prerequisites:** Python 3.10+. `ffmpeg` only if you want audio/video.
`./vellum doctor` tells you what's missing in plain language.

---

## Setup wizard

`./vellum init` walks through, with sensible defaults and live validation:

| Step | What it sets | Default |
|------|--------------|---------|
| Provider | which CLI answers chat (`claude-code`/`codex`/`hermes`/`command`) | `claude-code` |
| Language | UI language (`en`/`de`) | from `$LANG` |
| Data folder | where sources + index live | `data` |
| Port | localhost port | `8008` |
| Modalities | `text,image,audio,video` | `text,image` |
| Embeddings | `lexical` (instant) or `semantic` | `lexical` |
| Color | terminal color | on |

**Non-interactive** (CI / power users) — every step has a flag, and `--yes`
accepts the rest:

```bash
./vellum init --yes --adapter command --command "my-llm --stdin" \
              --port 8800 --lang en --modalities text,image,audio --embedder semantic
```

Everything lands in a commented `.env` you can also edit by hand
(`MMRAG_*` keys; `VELLUM_*` works as an alias). Full reference:
[`references/configuration.md`](references/configuration.md).

---

## How it works

```
  your files ─▶ ingest ─▶ chunks+embeddings ─▶ local index (SQLite)
                                                      │
  question ─▶ retrieve top matches ─▶ strict prompt ─▶ your CLI ─▶ answer + [S#] cites
```

1. **Ingest** — PDFs (text/OCR), images (OCR + caption), audio & video
   (keyframes + transcription) become text chunks with a page/timestamp locator.
2. **Index** — chunks are embedded and stored locally (SQLite + NumPy). Re-runs
   are incremental via file hashing.
3. **Retrieve & ground** — your question pulls the most relevant chunks into a
   strict, source-bound prompt.
4. **Answer** — your CLI responds, streamed to the UI with clickable `[S#]`
   citations back to each source.

More detail: [`references/architecture.md`](references/architecture.md).

---

## Supported files

| Modality | Extensions | Notes |
|----------|------------|-------|
| Documents | pdf, txt, md, docx, pptx, csv, html | text + OCR fallback for scans |
| Images | png, jpg, jpeg, webp, gif | OCR of in-image text + filename caption |
| Audio | mp3, wav, m4a, flac | transcription (optional) |
| Video | mp4, mov, mkv | keyframes + audio transcription |

The light default install handles documents and images with a dependency-free
**lexical** embedder. Turn on the rest when you want them:

```bash
pip install -r requirements-optional.txt   # semantic embeddings, OCR, transcription
```

---

## Honest limitations

- **Default embeddings are lexical** (keyword-style). For NotebookLM-grade recall
  pick **semantic** in the wizard (`sentence-transformers`).
- **Images aren't understood by a vision model** — only OCR'd text and a filename
  caption are indexed.
- **`hermes`/`codex` adapter flags are reasonable defaults, not verified** across
  every version. If chat misbehaves, use the generic `command` adapter.
- **Switching the embedder** changes the vector size; affected sources are
  excluded from search until you hit **Reprocess all** (the UI offers it).
- **No auth** — it's localhost-only by design.

---

## Privacy

Sources, transcripts, embeddings, the index, and caches live under a local,
gitignored `data/` folder. No telemetry, no phone-home, no third-party CDN. The
only outbound traffic is whatever your chosen CLI does when *you* ask a question.
See [`references/security.md`](references/security.md).

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
bash scripts/install-hooks.sh    # secret-scan pre-commit hook
pytest && ruff check .
```

Contributions welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE) — open source. © 2026 Vellum contributors.
