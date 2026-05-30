import hashlib

import numpy as np
import pandas as pd
import pytest

from robocop import embeddings, notes_index
from robocop.notes_index import NotesIndex, split_with_offsets


def test_split_offsets_reconstruct_text():
    text = "para one.\n\n" + "word " * 200 + "\n\nfinal section here."
    chunks = split_with_offsets(text, size=120, overlap=20)
    assert len(chunks) > 1
    for start, end, chunk in chunks:
        assert text[start:end] == chunk          # offsets are exact
        assert 0 <= start < end <= len(text)


def test_split_short_text_single_chunk():
    assert split_with_offsets("short", 500, 80) == [(0, 5, "short")]


def _fake_vec(text: str, dim: int = 16) -> np.ndarray:
    h = hashlib.sha256(text.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def patched_embed(monkeypatch):
    def fake_embed_texts(texts, **kw):
        return np.vstack([_fake_vec(t) for t in texts]).astype(np.float32)

    def fake_embed_query(text, **kw):
        return _fake_vec(text)

    monkeypatch.setattr(embeddings, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(notes_index.embeddings, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(notes_index.embeddings, "embed_query", fake_embed_query)


def _notes_df():
    return pd.DataFrame(
        [
            dict(NOTEID="N1", PATID="MU1", PROVIDER_TYPE="MD", NOTE_DATE="2020-01-01",
                 NOTE_TEXT="feeding intolerance with abdominal distension. " * 20),
            dict(NOTEID="N2", PATID="MU2", PROVIDER_TYPE="RN", NOTE_DATE="2020-01-02",
                 NOTE_TEXT="respiratory desaturations on CPAP overnight. " * 20),
        ]
    )


def test_build_and_search_with_filters(patched_embed):
    idx = NotesIndex.build(_notes_df(), size=120, overlap=20)
    assert idx.index.ntotal == len(idx.meta) > 2

    hits = idx.search("anything", k=5)
    assert hits and all(h.text == h.text for h in hits)

    # patient filter
    only_mu1 = idx.search("anything", patid="MU1", k=10)
    assert only_mu1 and all(h.patid == "MU1" for h in only_mu1)

    # provider filter
    only_rn = idx.search("anything", providers=["RN"], k=10)
    assert all(h.provider_type == "RN" for h in only_rn)

    # offsets valid against parent text
    for h in hits:
        assert 0 <= h.start < h.end
