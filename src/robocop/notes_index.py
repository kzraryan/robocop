"""Chunk MU clinical notes, embed the chunks, and build a FAISS index for
semantic search. Chunks keep exact character offsets into the parent note so the
UI can highlight the matched section and expand the full note.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from . import config, embeddings

INDEX_FILE = "notes.faiss"
META_FILE = "chunks.parquet"


# --- offset-preserving chunker -------------------------------------------
def split_with_offsets(text: str, size: int, overlap: int) -> list[tuple[int, int, str]]:
    """Sliding window over ``text`` returning ``(start, end, chunk)`` triples with
    exact offsets. Breaks at a newline/space near the window end when possible."""
    n = len(text)
    if n == 0:
        return []
    if n <= size:
        return [(0, n, text)]

    out: list[tuple[int, int, str]] = []
    start = 0
    while start < n:
        end = min(start + size, n)
        if end < n:
            brk = text.rfind("\n", start + overlap, end)
            if brk == -1:
                brk = text.rfind(" ", start + overlap, end)
            if brk > start:
                end = brk
        out.append((start, end, text[start:end]))
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return out


@dataclass
class Hit:
    noteid: str
    patid: str
    provider_type: str
    note_date: str
    start: int
    end: int
    text: str        # the matched chunk
    score: float

    def as_dict(self) -> dict:
        return asdict(self)


class NotesIndex:
    def __init__(self, index: faiss.Index, meta: pd.DataFrame):
        self.index = index
        self.meta = meta.reset_index(drop=True)

    # --- build / persist ---------------------------------------------------
    @classmethod
    def build(
        cls,
        notes: pd.DataFrame,
        size: int | None = None,
        overlap: int | None = None,
        embed_model: str | None = None,
        host: str | None = None,
    ) -> "NotesIndex":
        size = size or config.CHUNK_SIZE
        overlap = overlap or config.CHUNK_OVERLAP

        records: list[dict] = []
        for row in notes.itertuples(index=False):
            text = getattr(row, "NOTE_TEXT") or ""
            for start, end, chunk in split_with_offsets(text, size, overlap):
                records.append(
                    dict(
                        NOTEID=getattr(row, "NOTEID"),
                        PATID=getattr(row, "PATID"),
                        PROVIDER_TYPE=getattr(row, "PROVIDER_TYPE"),
                        NOTE_DATE=getattr(row, "NOTE_DATE"),
                        start=start,
                        end=end,
                        text=chunk,
                    )
                )
        meta = pd.DataFrame.from_records(records)
        if meta.empty:
            raise ValueError("No note chunks to index.")

        vecs = embeddings.embed_texts(
            meta["text"].tolist(), model=embed_model, host=host
        )
        dim = vecs.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vecs)
        return cls(index, meta)

    def save(self, faiss_dir: Path | None = None) -> Path:
        faiss_dir = Path(faiss_dir or config.FAISS_DIR)
        faiss_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(faiss_dir / INDEX_FILE))
        self.meta.to_parquet(faiss_dir / META_FILE, index=False)
        return faiss_dir

    @classmethod
    def load(cls, faiss_dir: Path | None = None) -> "NotesIndex":
        faiss_dir = Path(faiss_dir or config.FAISS_DIR)
        index = faiss.read_index(str(faiss_dir / INDEX_FILE))
        meta = pd.read_parquet(faiss_dir / META_FILE)
        return cls(index, meta)

    # --- search ------------------------------------------------------------
    def search(
        self,
        query: str,
        patid: str | None = None,
        providers: list[str] | None = None,
        k: int = 20,
        embed_model: str | None = None,
        host: str | None = None,
    ) -> list[Hit]:
        qv = embeddings.embed_query(query, model=embed_model, host=host).astype(np.float32)
        qv = qv.reshape(1, -1)

        filtering = bool(patid or providers)
        fetch = min(self.index.ntotal, k * 10 if filtering else k)
        scores, idxs = self.index.search(qv, fetch)

        hits: list[Hit] = []
        for score, i in zip(scores[0], idxs[0]):
            if i < 0:
                continue
            r = self.meta.iloc[int(i)]
            if patid and r["PATID"] != patid:
                continue
            if providers and r["PROVIDER_TYPE"] not in providers:
                continue
            hits.append(
                Hit(
                    noteid=r["NOTEID"],
                    patid=r["PATID"],
                    provider_type=r["PROVIDER_TYPE"],
                    note_date=r["NOTE_DATE"],
                    start=int(r["start"]),
                    end=int(r["end"]),
                    text=r["text"],
                    score=float(score),
                )
            )
            if len(hits) >= k:
                break
        return hits


    # --- patient note-embedding centroids (for the similarity engine) -----
    def patient_centroids(self) -> tuple[list[str], np.ndarray]:
        """Average each patient's chunk vectors -> (patids, normalized matrix).

        Vectors are reconstructed from the FAISS index, so no re-embedding."""
        n = self.index.ntotal
        vecs = self.index.reconstruct_n(0, n)  # (n, dim), already unit-norm at build
        pat = self.meta["PATID"].to_numpy()
        patids = sorted(set(pat.tolist()))
        dim = vecs.shape[1]
        mat = np.zeros((len(patids), dim), dtype=np.float32)
        for i, p in enumerate(patids):
            rows = vecs[pat == p]
            if len(rows):
                c = rows.mean(axis=0)
                norm = np.linalg.norm(c)
                mat[i] = c / norm if norm else c
        return patids, mat


def build_from_duckdb(con, **kwargs) -> NotesIndex:
    notes = con.execute("SELECT * FROM mu_nicu.NOTE").fetchdf()
    return NotesIndex.build(notes, **kwargs)
