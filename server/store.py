"""Local vector store + metadata, backed by SQLite.

Embeddings are stored as float32 blobs. Retrieval loads the (typically small,
notebook-scale) matrix of enabled chunk vectors and ranks by cosine similarity
in NumPy. No external service, no cloud — the whole index is one local file
inside the gitignored data directory.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import numpy as np

from .models import Chunk, RetrievedChunk, Source

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path         TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    modality     TEXT NOT NULL,
    size         INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    enabled      INTEGER NOT NULL DEFAULT 1,
    error        TEXT NOT NULL DEFAULT '',
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    added_at     REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    ordinal   INTEGER NOT NULL,
    text      TEXT NOT NULL,
    modality  TEXT NOT NULL,
    locator   TEXT NOT NULL DEFAULT '',
    dim       INTEGER NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
"""


def _row_to_source(r: sqlite3.Row) -> Source:
    return Source(
        id=r["id"], path=r["path"], name=r["name"], modality=r["modality"],
        size=r["size"], content_hash=r["content_hash"], status=r["status"],
        enabled=bool(r["enabled"]), error=r["error"], chunk_count=r["chunk_count"],
        added_at=r["added_at"],
    )


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- sources ---------------------------------------------------------
    def upsert_source(self, source: Source) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT id FROM sources WHERE path = ?", (source.path,))
            row = cur.fetchone()
            if row:
                sid = row["id"]
                self._conn.execute(
                    "UPDATE sources SET name=?, modality=?, size=?, content_hash=?, "
                    "status=?, error=?, chunk_count=? WHERE id=?",
                    (source.name, source.modality, source.size, source.content_hash,
                     source.status, source.error, source.chunk_count, sid),
                )
            else:
                cur = self._conn.execute(
                    "INSERT INTO sources(path,name,modality,size,content_hash,status,"
                    "enabled,error,chunk_count,added_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (source.path, source.name, source.modality, source.size,
                     source.content_hash, source.status, int(source.enabled),
                     source.error, source.chunk_count, source.added_at or time.time()),
                )
                sid = int(cur.lastrowid)
            self._conn.commit()
            return sid

    def get_source(self, source_id: int) -> Source | None:
        cur = self._conn.execute("SELECT * FROM sources WHERE id=?", (source_id,))
        row = cur.fetchone()
        return _row_to_source(row) if row else None

    def get_source_by_path(self, path: str) -> Source | None:
        cur = self._conn.execute("SELECT * FROM sources WHERE path=?", (path,))
        row = cur.fetchone()
        return _row_to_source(row) if row else None

    def list_sources(self) -> list[Source]:
        cur = self._conn.execute("SELECT * FROM sources ORDER BY id")
        return [_row_to_source(r) for r in cur.fetchall()]

    def set_status(self, source_id: int, status: str, error: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sources SET status=?, error=? WHERE id=?",
                (status, error, source_id),
            )
            self._conn.commit()

    def set_enabled(self, source_id: int, enabled: bool) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sources SET enabled=?, status=CASE WHEN ? THEN "
                "(CASE WHEN status='disabled' THEN 'ready' ELSE status END) "
                "ELSE 'disabled' END WHERE id=?",
                (int(enabled), int(enabled), source_id),
            )
            self._conn.commit()

    def delete_source(self, source_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
            self._conn.commit()

    # ---- chunks ----------------------------------------------------------
    def replace_chunks(self, source_id: int, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))
            dim = int(embeddings.shape[1]) if embeddings.size else 0
            for ch, vec in zip(chunks, embeddings, strict=False):
                self._conn.execute(
                    "INSERT INTO chunks(source_id,ordinal,text,modality,locator,dim,embedding)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (source_id, ch.ordinal, ch.text, ch.modality, ch.locator, dim,
                     vec.astype(np.float32).tobytes()),
                )
            self._conn.execute(
                "UPDATE sources SET chunk_count=? WHERE id=?", (len(chunks), source_id)
            )
            self._conn.commit()

    def _load_matrix(self, source_ids: list[int] | None, expected_dim: int):
        """Return (chunks, matrix, meta) for enabled, ready chunks.

        Only chunks whose stored dimension matches ``expected_dim`` are loaded.
        This makes search robust when the embedder was changed: stale-dimension
        chunks are ignored (and should be reprocessed) instead of crashing on a
        shape mismatch.
        """
        q = (
            "SELECT c.id, c.source_id, c.ordinal, c.text, c.modality, c.locator, "
            "c.dim, c.embedding, s.name AS sname, s.path AS spath "
            "FROM chunks c JOIN sources s ON s.id=c.source_id "
            "WHERE s.enabled=1 AND s.status='ready' AND c.dim=?"
        )
        params: list = [expected_dim]
        if source_ids:
            placeholders = ",".join("?" * len(source_ids))
            q += f" AND c.source_id IN ({placeholders})"
            params.extend(source_ids)
        rows = self._conn.execute(q, params).fetchall()
        if not rows:
            return [], np.zeros((0, expected_dim), dtype=np.float32), []
        mat = np.zeros((len(rows), expected_dim), dtype=np.float32)
        chunks, meta = [], []
        for i, r in enumerate(rows):
            mat[i] = np.frombuffer(r["embedding"], dtype=np.float32)
            chunks.append(Chunk(id=r["id"], source_id=r["source_id"], ordinal=r["ordinal"],
                                text=r["text"], modality=r["modality"], locator=r["locator"]))
            meta.append((r["sname"], r["spath"]))
        return chunks, mat, meta

    def distinct_chunk_dims(self) -> list[int]:
        """Distinct embedding dimensions present among ready chunks."""
        rows = self._conn.execute(
            "SELECT DISTINCT c.dim FROM chunks c JOIN sources s ON s.id=c.source_id "
            "WHERE s.status='ready'"
        ).fetchall()
        return sorted(r["dim"] for r in rows)

    def stale_source_ids(self, expected_dim: int) -> list[int]:
        """Ready sources whose chunks were embedded with a different dimension."""
        rows = self._conn.execute(
            "SELECT DISTINCT c.source_id FROM chunks c JOIN sources s ON s.id=c.source_id "
            "WHERE s.status='ready' AND c.dim<>?",
            (expected_dim,),
        ).fetchall()
        return sorted(r["source_id"] for r in rows)

    def search(self, query_vec: np.ndarray, top_k: int,
               source_ids: list[int] | None = None) -> list[RetrievedChunk]:
        q = query_vec.astype(np.float32).reshape(-1)
        chunks, mat, meta = self._load_matrix(source_ids, expected_dim=int(q.shape[0]))
        if not chunks:
            return []
        scores = mat @ q  # vectors are L2-normalized -> dot == cosine
        order = np.argsort(-scores)[:top_k]
        results = []
        for idx in order:
            name, path = meta[idx]
            results.append(RetrievedChunk(
                chunk=chunks[idx], source_name=name, source_path=path,
                score=float(scores[idx]),
            ))
        return results
