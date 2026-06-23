# Architecture

```
┌─────────────────────────────┐
│        Browser UI           │  pick sources, chat, inspect citations
│        (web/, vanilla JS)   │
└──────────────┬──────────────┘
               │ HTTP + SSE (localhost only)
┌──────────────▼──────────────┐
│   Local server (FastAPI)    │  server/app.py
│                             │
│  Ingestion pipeline ........ server/ingest/      PDF/image/audio/video → chunks
│  Embeddings ................ server/embeddings.py hashing | sentence-transformers
│  Vector store .............. server/store.py      SQLite + NumPy cosine
│  Retrieval ................. server/retrieval.py  query → top-k chunks (+floor)
│  Prompt builder ............ server/prompt.py     strict grounding + [S#] markers
│  CLI bridge ................ server/cli_bridge/   claude-code/hermes/codex/command
└─────────────────────────────┘
```

## Request flow

### Adding sources
1. UI `POST /api/sources` with local paths.
2. `ingest.expand_paths` walks directories for supported files.
3. Each file becomes a `Source` row (status `pending`) and is processed on a
   background thread.
4. `ingest.process_source` hashes the file (incremental skip), runs the modality
   extractor, chunks the text with provenance locators, embeds the chunks, and
   writes them to the store. Status moves `pending → processing → ready|error`.

### Chatting
1. UI `POST /api/chat` (message + optional source filter).
2. `retrieval.retrieve` embeds the query and ranks chunks by cosine similarity,
   dropping orthogonal matches.
3. `prompt.build_prompt` assembles the system prompt (strict grounding rules) +
   a SOURCES block where each chunk gets a stable `[S#]` marker + the question.
4. `cli_bridge` streams the prompt to the configured CLI on **stdin** and
   relays the answer.
5. The server emits Server-Sent Events: `citations` first, then `token` events,
   then `done` (or `error`).

## Why a CLI bridge instead of a hosted API key

The skill is meant to run inside a coding/agent CLI the user already trusts and
has authenticated. Routing through that CLI means **this project never stores or
requests an API key**, and the user controls which model answers. Adapters are
small and swappable; adding one is a single class plus a registry entry (see
`server/cli_bridge/adapters.py` and `CONTRIBUTING.md`).

## Vector store choice

A single local SQLite file holds sources, chunks, and float32 embedding blobs.
At notebook scale, loading the enabled-chunk matrix and computing cosine
similarity in NumPy is simple, fast, and dependency-free — no external service,
no cloud database. The embedding/retrieval layer is abstracted, so a different
backend (e.g. LanceDB/Chroma) could be slotted in without touching the API.

## Extensibility points

- **Embedders** — implement `Embedder` in `server/embeddings.py`.
- **Extractors** — add a modality handler under `server/ingest/`.
- **CLI adapters** — implement `CLIAdapter` and register it.
