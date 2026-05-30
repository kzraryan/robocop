"""Thin Ollama embeddings client with an on-disk cache.

Uses the batch ``/api/embed`` endpoint (Ollama >= 0.2). Vectors are L2-normalized
so a FAISS inner-product index gives cosine similarity.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
import urllib.request
from pathlib import Path

import numpy as np

from . import config


def _cache_path(model: str) -> Path:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = model.replace("/", "_").replace(":", "_")
    return config.CACHE_DIR / f"emb_{safe}.pkl"


def _load_cache(model: str) -> dict[str, list[float]]:
    p = _cache_path(model)
    if p.exists():
        with p.open("rb") as f:
            return pickle.load(f)
    return {}


def _save_cache(model: str, cache: dict) -> None:
    with _cache_path(model).open("wb") as f:
        pickle.dump(cache, f)


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embed_batch(texts: list[str], model: str, host: str) -> list[list[float]]:
    payload = {"model": model, "input": texts}
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/embed",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310 (trusted localhost)
        data = json.loads(resp.read().decode("utf-8"))
    return data["embeddings"]


def embed_texts(
    texts: list[str],
    model: str | None = None,
    host: str | None = None,
    batch_size: int = 64,
    use_cache: bool = True,
    normalize: bool = True,
    checkpoint_every: int = 20,
    progress: bool | None = None,
) -> np.ndarray:
    """Embed ``texts`` -> float32 array (n, dim). Caches by text hash.

    The cache is flushed to disk every ``checkpoint_every`` batches, so a long
    run that is interrupted resumes from where it stopped instead of starting
    over. ``progress`` prints a running count to stderr (auto-enabled for large
    workloads when not explicitly set).
    """
    model = model or config.EMBED_MODEL
    host = host or config.OLLAMA_HOST
    cache = _load_cache(model) if use_cache else {}

    todo = [t for t in texts if _key(t) not in cache]
    # de-dup while preserving need
    seen: set[str] = set()
    unique_todo = []
    for t in todo:
        k = _key(t)
        if k not in seen:
            seen.add(k)
            unique_todo.append(t)

    total = len(unique_todo)
    if progress is None:
        progress = total > batch_size  # noisy only for real builds
    n_batches = (total + batch_size - 1) // batch_size
    for bi, i in enumerate(range(0, total, batch_size)):
        chunk = unique_todo[i : i + batch_size]
        vecs = _embed_batch(chunk, model, host)
        for t, v in zip(chunk, vecs):
            cache[_key(t)] = v
        # Periodic checkpoint so an interrupted run is resumable.
        if use_cache and checkpoint_every and (bi + 1) % checkpoint_every == 0:
            _save_cache(model, cache)
        if progress:
            done = min(i + batch_size, total)
            print(
                f"\r  embedded {done}/{total} new chunks "
                f"(batch {bi + 1}/{n_batches})",
                end="",
                file=sys.stderr,
                flush=True,
            )
    if progress and total:
        print("", file=sys.stderr)
    if use_cache and unique_todo:
        _save_cache(model, cache)

    mat = np.asarray([cache[_key(t)] for t in texts], dtype=np.float32)
    if normalize and len(mat):
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
    return mat


def embed_query(text: str, model: str | None = None, host: str | None = None) -> np.ndarray:
    return embed_texts([text], model=model, host=host, use_cache=False)[0]
