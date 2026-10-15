"""Hybrid retrieval: BM25 keyword search fused with dense embeddings.

Both rankers work on page chunks, so every hit carries a manual name and page
number for citations. Scores are combined with reciprocal rank fusion (RRF),
which needs no score calibration between the two rankers.

Embeddings are pluggable. The default ``HashingEmbedder`` is a dependency-free
character n-gram embedding that works offline on any CPU; install the
``embeddings`` extra to use a multilingual sentence-transformers model instead.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

import numpy as np
from pydantic import BaseModel

from .ingest import PageChunk

_TOKEN = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens; fault codes like 'E101' or 'F-2040' stay whole."""
    return [t.lower() for t in _TOKEN.findall(text)]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = (sum(self.len) / len(docs)) if docs else 0.0
        df: Counter[str] = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tf))
        for i, tf in enumerate(self.tf):
            norm = self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1.0))
            for t in query:
                f = tf.get(t)
                if f:
                    out[i] += self.idf[t] * f * (self.k1 + 1) / (f + norm)
        return out


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class HashingEmbedder:
    """Character 3-5-gram feature hashing, L2-normalised. Offline and language agnostic."""

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        mat = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in tokenize(text):
                padded = f"<{word}>"
                for n in (3, 4, 5):
                    for i in range(len(padded) - n + 1):
                        h = hashlib.md5(padded[i : i + n].encode()).digest()
                        idx = int.from_bytes(h[:4], "little") % self.dim
                        sign = 1.0 if h[4] & 1 else -1.0
                        mat[row, idx] += sign
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        return mat / np.where(norms == 0, 1, norms)


class SentenceTransformerEmbedder:
    """Wraps a sentence-transformers model (pip install '.[embeddings]')."""

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)


class Hit(BaseModel):
    chunk: PageChunk
    score: float
    bm25_rank: int | None = None
    dense_rank: int | None = None

    @property
    def citation(self) -> str:
        return self.chunk.citation


class HybridRetriever:
    def __init__(
        self,
        chunks: list[PageChunk],
        embedder: Embedder | None = None,
        rrf_k: int = 60,
    ):
        self.chunks = chunks
        self.embedder = embedder or HashingEmbedder()
        self.rrf_k = rrf_k
        self.bm25 = BM25([tokenize(self._text(c)) for c in chunks])
        self.matrix = (
            self.embedder.encode([self._text(c) for c in chunks])
            if chunks
            else np.zeros((0, 1), dtype=np.float32)
        )

    @staticmethod
    def _text(c: PageChunk) -> str:
        return " ".join(filter(None, [c.model, c.system, c.text]))

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        if not self.chunks or not query.strip():
            return []
        sparse = self.bm25.scores(tokenize(query))
        dense = self.matrix @ self.embedder.encode([query])[0]
        fused: dict[int, Hit] = {}
        for attr, scores in (("bm25_rank", sparse), ("dense_rank", dense)):
            order = np.argsort(-scores, kind="stable")
            for rank, i in enumerate(order, start=1):
                if scores[i] <= 0:
                    break
                hit = fused.setdefault(int(i), Hit(chunk=self.chunks[i], score=0.0))
                setattr(hit, attr, rank)
                hit.score += 1.0 / (self.rrf_k + rank)
        return sorted(fused.values(), key=lambda h: -h.score)[:top_k]
