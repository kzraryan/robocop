"""Per-infant feature engineering from the MU NICU tables.

Produces one row per PATID combining demographics, length of stay, diagnosis /
medication flags, lab summaries, and intervention counts. This single feature
table backs the similarity engine, the phenotype graph, and the risk model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config

# Key diagnosis ICD-10 codes -> readable flag name (drives multi-hot features).
DX_FLAGS = {
    "P22.0": "dx_rds",
    "P27.1": "dx_bpd",
    "P77.9": "dx_nec",
    "H35.10": "dx_rop",
    "P36.9": "dx_sepsis",
    "P59.9": "dx_jaundice",
    "Q25.0": "dx_pda",
    "P28.4": "dx_apnea",
    "P61.2": "dx_anemia",
    "P52.3": "dx_ivh",
}
# Medication name substrings -> flag.
MED_FLAGS = {
    "caffeine": "med_caffeine",
    "surfactant": "med_surfactant",
    "ampicillin": "med_antibiotic",
    "gentamicin": "med_antibiotic",
    "furosemide": "med_diuretic",
}
# Lab name -> (feature column, aggregation)
LAB_AGGS = [
    ("Total bilirubin", "lab_bili_max", "max"),
    ("C-reactive protein", "lab_crp_max", "max"),
    ("Hemoglobin", "lab_hgb_min", "min"),
    ("Glucose", "lab_glucose_mean", "mean"),
]

NULLS = set(config.NULL_SENTINELS) | {None}


@dataclass
class FeatureBundle:
    features: pd.DataFrame          # numeric features indexed by PATID
    meta: pd.DataFrame             # readable columns (sex, drg, los, ga_weeks ...)
    dx_sets: dict[str, set]        # PATID -> set of diagnosis names (for graph/Jaccard)
    feature_columns: list[str]     # numeric feature column names


def _num(series: pd.Series) -> pd.Series:
    """Coerce to numeric, treating documented null sentinels and any stray
    non-numeric strings (e.g. ``\\N``) as missing."""
    s = series.astype(str).str.strip()
    s = s.where(~s.isin(NULLS))
    return pd.to_numeric(s, errors="coerce")


def build_features(con) -> FeatureBundle:
    demo = con.execute("SELECT * FROM mu_nicu.DEMOGRAPHIC").fetchdf()
    enc = con.execute("SELECT * FROM mu_nicu.ENCOUNTER").fetchdf()
    dx = con.execute("SELECT * FROM mu_nicu.DIAGNOSIS").fetchdf()
    rx = con.execute("SELECT * FROM mu_nicu.PRESCRIBING").fetchdf()
    labs = con.execute("SELECT * FROM mu_nicu.LAB_RESULT_CM").fetchdf()
    procs = con.execute("SELECT * FROM mu_nicu.PROCEDURES").fetchdf()
    vent = con.execute("SELECT * FROM mu_nicu.OBS_CLIN_NICU_VENT").fetchdf()
    notes = con.execute("SELECT * FROM mu_nicu.NOTE").fetchdf()

    # Real tables can carry >1 row per PATID (multiple encounters/records). Keep
    # one demographic row per infant so the per-PATID index stays unique; a
    # duplicate index would break the .reindex() alignments below.
    demo1 = demo.drop_duplicates(subset="PATID", keep="first").set_index("PATID")

    f = pd.DataFrame(index=demo1.index)
    ga = _num(demo1["GESTATIONAL_AGE"])
    # GA is documented in days (e.g. 275); if the column is actually in weeks
    # (median well under 60), convert to days so ga_weeks stays consistent.
    if ga.notna().any() and ga.median(skipna=True) < 60:
        ga = ga * 7
    f["ga_days"] = ga
    f["ga_weeks"] = (f["ga_days"] / 7.0)
    f["sex_male"] = (demo1["SEX"] == "M").astype(int)

    # length of stay
    enc2 = enc.copy()
    enc2["admit"] = pd.to_datetime(enc2["ADMIT_DATE"], errors="coerce")
    enc2["disch"] = pd.to_datetime(enc2["DISCHARGE_DATE"], errors="coerce")
    enc2["los_days"] = (enc2["disch"] - enc2["admit"]).dt.days
    los = enc2.groupby("PATID")["los_days"].max()
    f["los_days"] = los

    # diagnosis multi-hot + count
    for code, flag in DX_FLAGS.items():
        pats = set(dx.loc[dx["DX"] == code, "PATID"])
        f[flag] = f.index.isin(pats).astype(int)
    f["n_diagnoses"] = dx.groupby("PATID")["DIAGNOSISID"].nunique().reindex(f.index).fillna(0)

    # medication flags + count
    rx_lower = rx.assign(_m=rx["RAW_RX_MED_NAME"].astype(str).str.lower())
    for sub, flag in MED_FLAGS.items():
        pats = set(rx_lower.loc[rx_lower["_m"].str.contains(sub, na=False), "PATID"])
        if flag not in f:
            f[flag] = 0
        f[flag] = (f[flag].astype(bool) | f.index.isin(pats)).astype(int)
    f["n_medications"] = rx.groupby("PATID")["PRESCRIBINGID"].nunique().reindex(f.index).fillna(0)

    # lab summaries
    labs2 = labs.copy()
    labs2["val"] = _num(labs2["RESULT_NUM"])
    for raw_name, col, agg in LAB_AGGS:
        sub = labs2[labs2["RAW_LAB_NAME"] == raw_name].dropna(subset=["val"])
        g = sub.groupby("PATID")["val"].agg(agg) if len(sub) else pd.Series(dtype=float)
        f[col] = g.reindex(f.index)

    # intervention counts
    f["n_procedures"] = procs.groupby("PATID")["PROCEDURESID"].nunique().reindex(f.index).fillna(0)
    f["vent_events"] = vent.groupby("PATID")["OBSCLINID"].nunique().reindex(f.index).fillna(0)
    f["n_notes"] = notes.groupby("PATID")["NOTEID"].nunique().reindex(f.index).fillna(0)

    # weight trajectory
    vit = con.execute("SELECT PATID, MEASURE_DATE, WT FROM mu_nicu.VITAL").fetchdf()
    vit["wt"] = _num(vit["WT"])
    vit["t"] = pd.to_datetime(vit["MEASURE_DATE"], errors="coerce")
    vit = vit.dropna(subset=["wt", "t"]).sort_values("t")
    first = vit.groupby("PATID")["wt"].first()
    last = vit.groupby("PATID")["wt"].last()
    f["birth_weight_kg"] = first.reindex(f.index)
    f["weight_gain_kg"] = (last - first).reindex(f.index)

    f = f.fillna(0.0)

    # readable meta
    meta = pd.DataFrame(index=f.index)
    meta["ga_weeks"] = f["ga_weeks"].round(1)
    meta["sex"] = demo1["SEX"].reindex(f.index)
    meta["los_days"] = f["los_days"].astype(int)
    # One DRG per infant: real ENCOUNTER has many rows per PATID, so collapse to
    # the first non-null DRG instead of set_index (which would duplicate labels).
    drg = enc.dropna(subset=["DRG"]).groupby("PATID")["DRG"].first()
    meta["drg"] = drg.reindex(f.index)
    meta["n_diagnoses"] = f["n_diagnoses"].astype(int)

    # diagnosis name sets (for graph / Jaccard)
    dx_sets = (
        dx.groupby("PATID")["RAW_DIAGNOSIS_NAME"]
        .agg(lambda s: set(s.dropna()))
        .reindex(f.index)
        .apply(lambda x: x if isinstance(x, set) else set())
        .to_dict()
    )

    feature_columns = [c for c in f.columns if c != "ga_days"]  # ga_weeks already captures GA
    return FeatureBundle(features=f, meta=meta, dx_sets=dx_sets, feature_columns=feature_columns)
