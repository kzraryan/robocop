"""Exercise the real-server ingestion path against a simulated drop:
- structured tables under STRUCTURED_DATA_V1/ with the 'DIAGONSIS' misspelling
- note text split across shards using a DEID_NOTE_RELEASE column
- per-note metadata + a provider-id -> provider-type lookup
- \\N null sentinels in a numeric column
"""

import pandas as pd
import pytest

from robocop import features, ingest, synth


def _make_real_dir(root):
    frames = synth.generate(n_patients=40, seed=5)
    structured = root / "STRUCTURED_DATA_V1"
    structured.mkdir(parents=True)
    for name, df in frames.items():
        if name == "NOTE":
            continue
        # misspell DIAGNOSIS on disk to test alias resolution
        fname = "DIAGONSIS.csv" if name == "DIAGNOSIS" else f"{name}.csv"
        if name == "LAB_RESULT_CM":               # inject a backslash-N sentinel
            df = df.copy()
            df.loc[df.index[:5], "RESULT_NUM"] = "\\N"
        df.to_csv(structured / fname, index=False)

    notes = frames["NOTE"]
    # provider id per provider type
    ptypes = sorted(notes["PROVIDER_TYPE"].unique())
    pid_of = {t: f"PRV{i}" for i, t in enumerate(ptypes)}
    notes_dir = root / "2024-11-20"
    notes_dir.mkdir()
    # split note text into two shards with DEID_NOTE_RELEASE column
    half = len(notes) // 2
    for i, part in enumerate([notes.iloc[:half], notes.iloc[half:]]):
        part.rename(columns={"NOTEID": "NOTE_ID", "NOTE_TEXT": "DEID_NOTE_RELEASE"})[
            ["NOTE_ID", "DEID_NOTE_RELEASE"]
        ].to_csv(notes_dir / f"notes_{i}.csv", index=False)

    # metadata: NOTE_ID -> PATID, NOTE_DATE, PROVIDER_ID
    meta = notes[["NOTEID", "PATID", "NOTE_DATE", "ENCOUNTERID", "PROVIDER_TYPE"]].copy()
    meta["PROVIDER_ID"] = meta["PROVIDER_TYPE"].map(pid_of)
    meta = meta.rename(columns={"NOTEID": "NOTE_ID"}).drop(columns="PROVIDER_TYPE")
    meta.to_csv(root / "NICU_NOTE_METADATA.csv", index=False)
    # providers lookup: PROVIDER_ID -> PROVIDER_TYPE
    pd.DataFrame({"PROVIDER_ID": list(pid_of.values()),
                  "PROVIDER_TYPE": list(pid_of.keys())}).to_csv(
        root / "NICU_PROVIDERS.csv", index=False)
    return root


def test_resolve_file_alias(tmp_path):
    (tmp_path / "DIAGONSIS.csv").write_text("x\n1\n")
    assert ingest.resolve_file(tmp_path, "DIAGNOSIS").name == "DIAGONSIS.csv"


def test_detect_col():
    cols = ["PAT_ID", "NOTE_ID", "Service_Date", "Provider_Type", "ENCOUNTER_ID"]
    assert ingest.detect_col(cols, "patid") == "PAT_ID"
    assert ingest.detect_col(cols, "noteid") == "NOTE_ID"
    assert ingest.detect_col(cols, "date") == "Service_Date"
    assert ingest.detect_col(cols, "provider_type") == "Provider_Type"
    assert ingest.detect_col(cols, "encounter") == "ENCOUNTER_ID"


@pytest.fixture(scope="module")
def real_con(tmp_path_factory):
    root = _make_real_dir(tmp_path_factory.mktemp("real"))
    db = ingest.build_real(real_dir=root, db_path=root / "mu.duckdb", verbose=False)
    c = ingest.connect(db, read_only=True)
    yield c
    c.close()


def test_structured_with_misspelled_diagnosis(real_con):
    assert real_con.execute("SELECT count(*) FROM mu_nicu.DIAGNOSIS").fetchone()[0] > 0
    assert real_con.execute("SELECT count(*) FROM mu_nicu.DEMOGRAPHIC").fetchone()[0] == 40


def test_notes_assembled_with_patid_and_provider(real_con):
    n = real_con.execute("SELECT count(*) FROM mu_nicu.NOTE").fetchone()[0]
    assert n > 0
    # PATID linked from metadata, provider type resolved via the id->type join
    linked = real_con.execute(
        "SELECT count(*) FROM mu_nicu.NOTE WHERE PATID IS NOT NULL").fetchone()[0]
    assert linked == n
    provs = {r[0] for r in real_con.execute(
        "SELECT DISTINCT PROVIDER_TYPE FROM mu_nicu.NOTE").fetchall()}
    assert provs & {"MD", "RN", "OT", "PT", "SLP"}
    # note text survived the DEID_NOTE_RELEASE rename
    txt = real_con.execute(
        "SELECT NOTE_TEXT FROM mu_nicu.NOTE WHERE NOTE_TEXT IS NOT NULL LIMIT 1").fetchone()[0]
    assert isinstance(txt, str) and len(txt) > 10


def test_backslash_n_coerced_to_null(real_con):
    fb = features.build_features(real_con)
    # \N sentinels must not poison the numeric lab feature
    assert fb.features["lab_bili_max"].notna().any()
    assert pd.api.types.is_numeric_dtype(fb.features["lab_bili_max"])
