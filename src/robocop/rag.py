"""Minimal retrieval over clinical notes: FAISS dense search + BM25 sparse,
with an optional hybrid combine. Everything runs locally on the server.

Embeddings come from sentence-transformers by default (fast on the A100); pass
``backend="ollama"`` to use Ollama's embedding models instead.

Example::

    from robocop import data, notes, rag
    df = notes.normalize(data.load_notes("Iowa"))
    idx = rag.NoteIndex.build(df["text"].tolist(), metadata=df.to_dict("records"))
    for hit in idx.search("apnea of prematurity caffeine", k=5):
        print(hit["score"], hit["text"][:200])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from .config import DEFAULT_EMBED_MODEL, DEFAULT_ST_EMBED_MODEL


def _st_model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


@dataclass
class NoteIndex:
    """A searchable index over a list of text chunks."""

    texts: list[str]
    metadata: list[dict] = field(default_factory=list)
    backend: Literal["sentence-transformers", "ollama"] = "sentence-transformers"
    model_name: str = DEFAULT_ST_EMBED_MODEL
    _embeddings: np.ndarray | None = None
    _faiss: Any = None
    _bm25: Any = None

    # --- construction ---------------------------------------------------------
    @classmethod
    def build(
        cls,
        texts: list[str],
        metadata: list[dict] | None = None,
        backend: Literal["sentence-transformers", "ollama"] = "sentence-transformers",
        model_name: str | None = None,
    ) -> "NoteIndex":
        idx = cls(
            texts=list(texts),
            metadata=list(metadata) if metadata else [{} for _ in texts],
            backend=backend,
            model_name=model_name
            or (DEFAULT_ST_EMBED_MODEL if backend == "sentence-transformers" else DEFAULT_EMBED_MODEL),
        )
        idx._build_dense()
        idx._build_sparse()
        return idx

    def _embed(self, texts: list[str]) -> np.ndarray:
        if self.backend == "ollama":
            from . import llm

            vecs = llm.embed(texts, model=self.model_name)
            return np.asarray(vecs, dtype="float32")
        model = _st_model(self.model_name)
        return np.asarray(
            model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype="float32",
        )

    def _build_dense(self) -> None:
        import faiss

        emb = self._embed(self.texts)
        faiss.normalize_L2(emb)  # cosine via inner product
        index = faiss.IndexFlatIP(emb.shape[1])
        index.add(emb)
        self._embeddings, self._faiss = emb, index

    def _build_sparse(self) -> None:
        from rank_bm25 import BM25Okapi

        self._bm25 = BM25Okapi([t.lower().split() for t in self.texts])

    # --- search ---------------------------------------------------------------
    def search(self, query: str, k: int = 5) -> list[dict]:
        """Dense (cosine) search. Returns hits with score/text/metadata."""
        q = self._embed([query])
        import faiss

        faiss.normalize_L2(q)
        scores, ids = self._faiss.search(q, k)
        return self._collect(ids[0], scores[0])

    def search_bm25(self, query: str, k: int = 5) -> list[dict]:
        """Sparse keyword search (good for exact terms, codes, abbreviations)."""
        scores = self._bm25.get_scores(query.lower().split())
        ids = np.argsort(scores)[::-1][:k]
        return self._collect(ids, scores[ids])

    def search_hybrid(self, query: str, k: int = 5, alpha: float = 0.5) -> list[dict]:
        """Combine dense and sparse with min-max normalisation.

        ``alpha`` weights the dense score (1.0 = pure dense, 0.0 = pure BM25).
        """
        dense = {h["i"]: h["score"] for h in self.search(query, k=k * 4)}
        sparse = {h["i"]: h["score"] for h in self.search_bm25(query, k=k * 4)}

        def norm(d: dict[int, float]) -> dict[int, float]:
            if not d:
                return {}
            lo, hi = min(d.values()), max(d.values())
            rng = (hi - lo) or 1.0
            return {i: (v - lo) / rng for i, v in d.items()}

        dn, sn = norm(dense), norm(sparse)
        combined = {
            i: alpha * dn.get(i, 0.0) + (1 - alpha) * sn.get(i, 0.0)
            for i in set(dn) | set(sn)
        }
        top = sorted(combined, key=combined.get, reverse=True)[:k]
        return self._collect(top, [combined[i] for i in top])

    def _collect(self, ids, scores) -> list[dict]:
        out = []
        for i, s in zip(ids, scores):
            i = int(i)
            if i < 0:
                continue
            out.append(
                {"i": i, "score": float(s), "text": self.texts[i], "metadata": self.metadata[i]}
            )
        return out
