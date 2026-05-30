"""Cohort note-selection for the embedding build (scripts/build_index.py).

Guards the behavior that bit us: "10 patients with >= 50 notes" must embed a
small, on-target set (the *fewest*-qualifying patients, optionally capped per
patient), never the whole corpus.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_index  # noqa: E402


@pytest.fixture
def note_con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA mu_nicu")
    rows = []
    # p0=5 notes ... p9=50 notes, each with a date so the cap can sort.
    for p in range(10):
        for k in range((p + 1) * 5):
            rows.append((f"n{p}_{k}", f"p{p}", f"2024-01-{(k % 28) + 1:02d}", f"text {p} {k}"))
    values = ",".join(f"('{a}','{b}','{c}','{d}')" for a, b, c, d in rows)
    con.execute(
        "CREATE TABLE mu_nicu.NOTE AS SELECT * FROM (VALUES "
        + values + ") AS t(NOTEID, PATID, NOTE_DATE, NOTE_TEXT)"
    )
    yield con
    con.close()


def test_cohort_takes_fewest_qualifying_first(note_con):
    # >= 20 notes qualifies p3..p9; fewest-first picks p3(20), p4(25), p5(30).
    df = build_index._select_cohort_notes(note_con, n_patients=3, min_notes=20)
    assert sorted(df["PATID"].unique().tolist()) == ["p3", "p4", "p5"]
    assert len(df) == 20 + 25 + 30


def test_per_patient_cap_bounds_volume(note_con):
    df = build_index._select_cohort_notes(
        note_con, n_patients=3, min_notes=20, per_patient_cap=10
    )
    assert len(df) == 30
    assert df.groupby("PATID").size().max() == 10


def test_no_qualifying_patients_returns_empty(note_con):
    assert build_index._select_cohort_notes(note_con, n_patients=5, min_notes=1000).empty


def test_fewer_than_requested_returns_all_qualifying(note_con):
    # Only p9 has >= 50 notes; asking for 5 returns just that one.
    df = build_index._select_cohort_notes(note_con, n_patients=5, min_notes=50)
    assert df["PATID"].unique().tolist() == ["p9"]
    assert len(df) == 50
