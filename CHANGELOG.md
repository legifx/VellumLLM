# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Self-update.** `./vellum update` fast-forwards to the latest version (git)
  and reinstalls dependencies. On an interactive start Vellum briefly checks the
  remote and, if a newer version exists, asks **Yes/No** before installing
  (default No). Skip the check with `VELLUM_NO_UPDATE_CHECK=1`.
- **Multiple Vellums (notebooks).** Each notebook is fully isolated in its own
  folder (`data/notebooks/<id>/`, own SQLite index). Create, rename, categorize,
  and delete Vellums; an old single-pool index is migrated automatically. New
  notebook-scoped API (`/api/notebooks/...`); a default Vellum is auto-created.
- **Netflix-style start screen.** A redesigned web UI: a card grid of all
  Vellums (glow/gradient, fade-in) opens into a notebook view with a folder→file
  source tree, chat, and citations.
- **Add folder/files via a file browser.** A built-in server-side filesystem
  picker (`GET /api/fs/browse`) replaces typing paths; files are ingested in
  place. (When bound to `0.0.0.0` this also exposes the browser — surfaced in UI.)
- **File preview.** Click a source to preview images, PDFs, video, and text
  inline (`GET /api/notebooks/<id>/sources/<sid>/file`).
- **Model picker.** Choose the model per chat from a searchable, curated catalog
  (`server/model_catalog.py`, `GET /api/models`); passed to the adapter as
  `--model`. Optional default via `MMRAG_MODEL`.
- **CLI access to one Vellum.** `./vellum notebooks` and `./vellum ask -n <id>
  "question"` answer grounded in a single notebook, straight in the terminal
  (`--json`, `--sources-only`) — so agents can target one Vellum.
- **Network-visibility onboarding step** with clickable (numbered) menus for
  every option and a clear exposure warning for `0.0.0.0` (default: local only).
- **Vellum brand + onboarding.** A `./vellum` launcher with a guided first-run
  setup (`vellum init`): parchment-over-frame ASCII/ANSI brand mark (with a pure
  ASCII fallback and `NO_COLOR` support), short well-defaulted questions with
  validation, a commented `.env` output, repeatable `--reconfigure`, and a
  non-interactive mode (`--yes` + flags / `VELLUM_*` env) for CI.
- Automatic `.env` loading and `VELLUM_*` → `MMRAG_*` aliases in config.
- UI language setting (`en`/`de`) with a small in-app i18n layer.
- `./vellum doctor` prerequisite check and a redesigned server start banner.

### Added (earlier)
- Initial release of Local NotebookLM — a local, multimodal, source-grounded
  RAG system packaged as a CLI skill.
- Multimodal ingestion pipeline: documents (pdf/txt/md/csv/html/docx/pptx),
  images (caption + OCR), audio (transcription), video (keyframes + transcription).
- Local SQLite + NumPy vector store with incremental, hash-based re-ingestion.
- Dependency-free hashing embedder plus optional sentence-transformers backend.
- Source-grounded chat with strict prompting and `[S#]` citations.
- Pluggable CLI bridge with `claude-code`, `hermes`, `codex`, and generic
  `command` adapters.
- Browser UI (sources / chat / citations), no CDN or trackers.
- Security tooling: secret/PII scanner and a pre-commit hook.
- Test suite covering ingestion, retrieval, prompting, adapters, and the API.

### Fixed
- Dimension-safe search: switching the embedder no longer crashes retrieval.
  Stale-dimension chunks are excluded from search, surfaced per notebook via
  `GET /api/notebooks/<id>/sources` (`needs_reprocess` / `stale_source_ids`), and
  re-embedded in one step via `POST /api/notebooks/<id>/sources/reprocess-all`
  or a UI banner.

### Docs
- Honest limitations: lexical (not semantic) default embedder, image OCR/caption
  (no vision model), and unverified `hermes`/`codex` adapter flags with the
  generic `command` adapter recommended when in doubt.
