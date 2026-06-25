"""FastAPI application: REST API, SSE chat streaming, static UI.

The API is organised around *notebooks* ("Vellums"). Each notebook is an
isolated index (its own SQLite file under ``data/notebooks/<id>/``); sources and
chat are always scoped to one notebook. A few endpoints are global: filesystem
browsing for the add-folder dialog, the model catalog, and server config.
"""
from __future__ import annotations

import json
import mimetypes
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import fsbrowse, model_catalog
from . import ingest as ingest_mod
from .cli_bridge import CLIError, build_adapter
from .config import Config
from .embeddings import build_embedder
from .models import (
    AddSourcesRequest,
    ChatRequest,
    NotebookRequest,
    NotebookUpdate,
)
from .notebooks import NotebookRegistry
from .prompt import build_prompt
from .retrieval import retrieve
from .store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class AppState:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.registry = NotebookRegistry(cfg.notebooks_dir)
        self.embedder = build_embedder(cfg.embedder, cfg.st_model)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._stores: dict[str, Store] = {}
        self._stores_lock = threading.Lock()

        # Adopt an old single-pool index, then guarantee at least one Vellum so
        # the UI always opens onto something.
        self.registry.migrate_legacy(cfg.db_path)
        if not self.registry.list():
            self.registry.create("My Vellum")

    def store_for(self, notebook_id: str) -> Store | None:
        if not self.registry.exists(notebook_id):
            return None
        with self._stores_lock:
            st = self._stores.get(notebook_id)
            if st is None:
                st = Store(self.registry.db_path(notebook_id))
                self._stores[notebook_id] = st
            return st

    def drop_store(self, notebook_id: str) -> None:
        with self._stores_lock:
            st = self._stores.pop(notebook_id, None)
        if st:
            st.close()

    def process_async(self, notebook_id: str, source_id: int, force: bool = False) -> None:
        store = self.store_for(notebook_id)
        if store is None:
            return
        self.executor.submit(
            ingest_mod.process_source, store, self.embedder, self.cfg,
            source_id, force,
        )


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or Config.load()
    state = AppState(cfg)
    app = FastAPI(title="Vellum", version="0.2.0")
    app.state.app_state = state

    # Localhost-only by default; CORS kept permissive only for local dev origins.
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost|0\.0\.0\.0)(:\d+)?",
        allow_methods=["*"], allow_headers=["*"],
    )

    def get_store(notebook_id: str) -> Store:
        store = state.store_for(notebook_id)
        if store is None:
            raise HTTPException(404, "Vellum not found")
        return store

    # ---- meta ------------------------------------------------------------
    @app.get("/api/config")
    def get_config():
        from .cli_bridge import available_adapters
        adapter = build_adapter(cfg)
        exposed = cfg.host not in ("127.0.0.1", "localhost", "::1")
        return {
            "cli_adapter": cfg.cli_adapter,
            "available_adapters": available_adapters(),
            "adapter_available": adapter.available(),
            "model": cfg.model,
            "models": model_catalog.models_for(cfg.cli_adapter),
            "language": cfg.language,
            "embedder": cfg.embedder,
            "embedder_dim": state.embedder.dim,
            "transcriber": cfg.transcriber,
            "top_k": cfg.top_k,
            "host": cfg.host,
            "network_exposed": exposed,
            "supported_extensions": sorted(ingest_mod.SUPPORTED),
        }

    @app.get("/api/models")
    def list_models(adapter: str | None = None):
        return {"models": model_catalog.models_for(adapter or cfg.cli_adapter)}

    # ---- filesystem browser (add-folder dialog) --------------------------
    @app.get("/api/fs/browse")
    def fs_browse(path: str | None = None):
        try:
            return fsbrowse.list_dir(path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    # ---- notebooks (Vellums) --------------------------------------------
    @app.get("/api/notebooks")
    def list_notebooks():
        out = []
        for nb in state.registry.list():
            d = nb.to_dict()
            store = state.store_for(nb.id)
            d["source_count"] = len(store.list_sources()) if store else 0
            out.append(d)
        return out

    @app.post("/api/notebooks")
    def create_notebook(req: NotebookRequest):
        nb = state.registry.create(req.name, req.category)
        return nb.to_dict()

    @app.get("/api/notebooks/{notebook_id}")
    def get_notebook(notebook_id: str):
        nb = state.registry.get(notebook_id)
        if nb is None:
            raise HTTPException(404, "Vellum not found")
        return nb.to_dict()

    @app.patch("/api/notebooks/{notebook_id}")
    def update_notebook(notebook_id: str, req: NotebookUpdate):
        nb = state.registry.update(notebook_id, name=req.name, category=req.category)
        if nb is None:
            raise HTTPException(404, "Vellum not found")
        return nb.to_dict()

    @app.delete("/api/notebooks/{notebook_id}")
    def delete_notebook(notebook_id: str):
        state.drop_store(notebook_id)
        if not state.registry.delete(notebook_id):
            raise HTTPException(404, "Vellum not found")
        return {"deleted": notebook_id}

    # ---- sources (scoped to a notebook) ---------------------------------
    @app.get("/api/notebooks/{notebook_id}/sources")
    def list_sources(notebook_id: str):
        store = get_store(notebook_id)
        stale = store.stale_source_ids(state.embedder.dim)
        return {
            "sources": [s.model_dump() for s in store.list_sources()],
            "stale_source_ids": stale,
            "needs_reprocess": bool(stale),
        }

    @app.post("/api/notebooks/{notebook_id}/sources/reprocess-all")
    def reprocess_all(notebook_id: str):
        """Force re-ingestion of every source so all chunks share the current
        embedding dimension (use after switching the embedder)."""
        store = get_store(notebook_id)
        ids = [s.id for s in store.list_sources()]
        for sid in ids:
            state.process_async(notebook_id, sid, force=True)
        return {"reprocessing": ids}

    @app.post("/api/notebooks/{notebook_id}/sources")
    def add_sources(notebook_id: str, req: AddSourcesRequest):
        store = get_store(notebook_id)
        files = ingest_mod.expand_paths(req.paths)
        if not files:
            raise HTTPException(400, "No supported files found at the given paths.")
        added = []
        for path in files:
            src = ingest_mod.register_source(store, path)
            state.process_async(notebook_id, src.id)
            added.append(src.model_dump())
        return {"added": added}

    @app.get("/api/notebooks/{notebook_id}/sources/{source_id}/file")
    def get_source_file(notebook_id: str, source_id: int):
        store = get_store(notebook_id)
        src = store.get_source(source_id)
        if src is None:
            raise HTTPException(404, "Source not found")
        p = Path(src.path)
        if not p.exists() or not p.is_file():
            raise HTTPException(404, "File no longer exists on disk")
        media, _ = mimetypes.guess_type(str(p))
        # inline so browsers preview images/PDFs/video instead of downloading
        return FileResponse(str(p), media_type=media or "application/octet-stream",
                            filename=p.name, content_disposition_type="inline")

    @app.post("/api/notebooks/{notebook_id}/sources/{source_id}/reprocess")
    def reprocess(notebook_id: str, source_id: int):
        store = get_store(notebook_id)
        if not store.get_source(source_id):
            raise HTTPException(404, "Source not found")
        state.process_async(notebook_id, source_id, force=True)
        return {"status": "processing"}

    @app.patch("/api/notebooks/{notebook_id}/sources/{source_id}")
    def update_source(notebook_id: str, source_id: int, body: dict):
        store = get_store(notebook_id)
        if not store.get_source(source_id):
            raise HTTPException(404, "Source not found")
        if "enabled" in body:
            store.set_enabled(source_id, bool(body["enabled"]))
        return store.get_source(source_id).model_dump()

    @app.delete("/api/notebooks/{notebook_id}/sources/{source_id}")
    def delete_source(notebook_id: str, source_id: int):
        store = get_store(notebook_id)
        store.delete_source(source_id)
        return {"deleted": source_id}

    # ---- chat (SSE, scoped to a notebook) -------------------------------
    @app.post("/api/notebooks/{notebook_id}/chat")
    def chat(notebook_id: str, req: ChatRequest):
        store = get_store(notebook_id)
        top_k = req.top_k or cfg.top_k
        chunks = retrieve(store, state.embedder, req.message, top_k,
                          source_ids=req.source_ids or None)
        prompt, citations = build_prompt(req.message, chunks)
        model = req.model or cfg.model

        def sse(event: str, data) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        def generator():
            yield sse("citations", [c.model_dump() for c in citations])
            if not chunks:
                yield sse("token", {"text": "This is not covered by the provided sources."})
                yield sse("done", {})
                return
            try:
                adapter = build_adapter(cfg, model)
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
