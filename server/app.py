"""FastAPI application: REST API, SSE chat streaming, static UI."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ingest as ingest_mod
from .cli_bridge import CLIError, build_adapter
from .config import Config
from .embeddings import build_embedder
from .models import AddSourcesRequest, ChatRequest
from .prompt import build_prompt
from .retrieval import retrieve
from .store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class AppState:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.store = Store(cfg.db_path)
        self.embedder = build_embedder(cfg.embedder, cfg.st_model)
        self.executor = ThreadPoolExecutor(max_workers=2)

    def process_async(self, source_id: int, force: bool = False) -> None:
        self.executor.submit(
            ingest_mod.process_source, self.store, self.embedder, self.cfg,
            source_id, force,
        )


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or Config.load()
    state = AppState(cfg)
    app = FastAPI(title="Local NotebookLM", version="0.1.0")
    app.state.app_state = state

    # Localhost-only by default; CORS kept permissive only for local dev origins.
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?",
        allow_methods=["*"], allow_headers=["*"],
    )

    # ---- meta ------------------------------------------------------------
    @app.get("/api/config")
    def get_config():
        from .cli_bridge import available_adapters
        adapter = build_adapter(cfg)
        stale = state.store.stale_source_ids(state.embedder.dim)
        return {
            "cli_adapter": cfg.cli_adapter,
            "available_adapters": available_adapters(),
            "adapter_available": adapter.available(),
            "language": cfg.language,
            "embedder": cfg.embedder,
            "embedder_dim": state.embedder.dim,
            "transcriber": cfg.transcriber,
            "top_k": cfg.top_k,
            "supported_extensions": sorted(ingest_mod.SUPPORTED),
            # Sources embedded with a different dimension than the current
            # embedder; they are excluded from search until reprocessed.
            "stale_source_ids": stale,
            "needs_reprocess": bool(stale),
        }

    # ---- sources ---------------------------------------------------------
    @app.get("/api/sources")
    def list_sources():
        return [s.model_dump() for s in state.store.list_sources()]

    @app.post("/api/sources")
    def add_sources(req: AddSourcesRequest):
        files = ingest_mod.expand_paths(req.paths)
        if not files:
            raise HTTPException(400, "No supported files found at the given paths.")
        added = []
        for path in files:
            src = ingest_mod.register_source(state.store, path)
            state.process_async(src.id)
            added.append(src.model_dump())
        return {"added": added}

    @app.post("/api/sources/{source_id}/reprocess")
    def reprocess(source_id: int):
        if not state.store.get_source(source_id):
            raise HTTPException(404, "Source not found")
        state.process_async(source_id, force=True)
        return {"status": "processing"}

    @app.post("/api/sources/reprocess-all")
    def reprocess_all():
        """Force re-ingestion of every source. Use after changing the embedder
        so all chunks share the current embedding dimension."""
        ids = [s.id for s in state.store.list_sources()]
        for sid in ids:
            state.process_async(sid, force=True)
        return {"reprocessing": ids}

    @app.patch("/api/sources/{source_id}")
    def update_source(source_id: int, body: dict):
        if not state.store.get_source(source_id):
            raise HTTPException(404, "Source not found")
        if "enabled" in body:
            state.store.set_enabled(source_id, bool(body["enabled"]))
        return state.store.get_source(source_id).model_dump()

    @app.delete("/api/sources/{source_id}")
    def delete_source(source_id: int):
        state.store.delete_source(source_id)
        return {"deleted": source_id}

    # ---- chat (SSE) ------------------------------------------------------
    @app.post("/api/chat")
    def chat(req: ChatRequest):
        top_k = req.top_k or cfg.top_k
        chunks = retrieve(state.store, state.embedder, req.message, top_k,
                          source_ids=req.source_ids or None)
        prompt, citations = build_prompt(req.message, chunks)

        def sse(event: str, data) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        def generator():
            yield sse("citations", [c.model_dump() for c in citations])
            if not chunks:
                yield sse("token", {"text": "This is not covered by the provided sources."})
                yield sse("done", {})
                return
            try:
                adapter = build_adapter(cfg)
                for piece in adapter.stream(prompt, timeout=cfg.cli_timeout):
                    yield sse("token", {"text": piece})
                yield sse("done", {})
            except CLIError as exc:
                yield sse("error", {"message": str(exc)})

        return StreamingResponse(generator(), media_type="text/event-stream")

    # ---- static UI -------------------------------------------------------
    if WEB_DIR.exists():
        @app.get("/")
        def index():
            return FileResponse(WEB_DIR / "index.html")

        app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    return app
