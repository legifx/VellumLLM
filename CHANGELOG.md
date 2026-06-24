# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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
  Stale-dimension chunks are excluded from search, surfaced via
  `GET /api/config` (`needs_reprocess` / `stale_source_ids`), and can be
  re-embedded in one step via `POST /api/sources/reprocess-all` or a UI banner.

### Docs
- Honest limitations: lexical (not semantic) default embedder, image OCR/caption
  (no vision model), and unverified `hermes`/`codex` adapter flags with the
  generic `command` adapter recommended when in doubt.
