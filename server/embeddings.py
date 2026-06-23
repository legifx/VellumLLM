"""Embedding backends.

Two interchangeable embedders:

* ``HashingEmbedder`` — deterministic, dependency-free (hashing trick over
  token n-grams, L2-normalized). Good enough for testing and minimal installs;
  no network, no model download.
* ``SentenceTransformerEmbedder`` — real semantic embeddings via the optional
  ``sentence-transformers`` package (lazy-imported so the core stays light).

Both expose ``dim`` and ``encode(list[str]) -> np.ndarray`` (float32, L2-norm).
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(ABC):
    dim: int

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:  # (n, dim) float32
        ...


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (mat / norms).astype(np.float32)


class HashingEmbedder(Embedder):
    """Feature-hashing embedder over unigrams + bigrams. No dependencies."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _tokens(self, text: str) -> list[str]:
        words = _TOKEN_RE.findall(text.lower())
        bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
        return words + bigrams

    def _hash(self, token: str) -> tuple[int, int]:
        h = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "little") % self.dim
        sign = 1 if h[4] & 1 else -1
        return idx, sign

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in self._tokens(text):
                idx, sign = self._hash(tok)
                out[i, idx] += sign
        return _normalize(out)


class SentenceTransformerEmbedder(Embedder):
    """Wrapper around sentence-transformers (optional, heavier install)."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised via message
            raise RuntimeError(
                "MMRAG_EMBEDDER=sentence-transformers but the package is not "
                "installed. Run: pip install -r requirements-optional.txt — or "
                "set MMRAG_EMBEDDER=hashing for the dependency-free embedder."
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)


def build_embedder(backend: str, st_model: str) -> Embedder:
    backend = (backend or "hashing").lower()
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder(st_model)
    if backend == "hashing":
        return HashingEmbedder()
    raise ValueError(
        f"Unknown embedder backend '{backend}'. Use 'hashing' or "
        f"'sentence-transformers' (set MMRAG_EMBEDDER)."
    )
