"""Unified longitudinal event timeline for a single infant.

Pulls every event type (diagnoses, conditions, labs, medications, procedures,
vitals, ventilation, pain scores, GI/feeding observations, notes) into one long
DataFrame anchored to day-of-life, for a single chronological NICU-course view.
"""

from __future__ import annotations

import pandas as pd

CATEGORY_ORDER = [
    "Diagnosis", "Condition", "Medication", "Procedure", "Ventilation",
    "Feeding/GI", "Lab", "Vital", "Pain", "Note",
]


def _birth_date(con, patid: str):
    row = con.execute(
        "SELECT BIRTH_DATE FROM mu_nicu.DEMOGRAPHIC WHERE PATID = ?", [patid]
    ).fetchone()
    return pd.to_datetime(row[0], errors="coerce") if row else pd.NaT


def patient_events(con, patid: str) -> pd.DataFrame:
    """Return a tidy event log: date, dol, category, label, detail."""
    birth = _birth_date(con, patid)
    rows: list[dict] = []

    def add(date, category, label, detail=""):
        t = pd.to_datetime(date, errors="coerce")
        rows.append({"date": t, "category": category, "label": str(label), "detail": str(detail)})

    q = lambda sql: con.execute(sql, [patid]).fetchall()  # noqa: E731

    for d, name, code in q(
        "SELECT DX_DATE, RAW_DIAGNOSIS_NAME, DX FROM mu_nicu.DIAGNOSIS WHERE PATID=?"
    ):
        add(d, "Diagnosis", name, f"ICD-10 {code}")
    for d, name, code in q(
        "SELECT REPORT_DATE, RAW_CONDITION_NAME, CONDITION FROM mu_nicu.CONDITION WHERE PATID=?"
    ):
        add(d, "Condition", name, f"SNOMED {code}")
    for d, name, route in q(
        "SELECT RX_START_DATE, RAW_RX_MED_NAME, RX_ROUTE FROM mu_nicu.PRESCRIBING WHERE PATID=?"
    ):
        add(d, "Medication", name, route)
    for name, in q("SELECT RAW_PROCEDURE_NAME FROM mu_nicu.PROCEDURES WHERE PATID=?"):
        add(birth, "Procedure", name)  # procedures lack a date column; anchor to birth
    for d, name, res in q(
        "SELECT OBSCLIN_START_DATE, RAW_OBSCLIN_NAME, OBSCLIN_RESULT FROM mu_nicu.OBS_CLIN_NICU_VENT WHERE PATID=?"
    ):
        add(d, "Ventilation", name, res)
    for d, name, res in q(
        "SELECT OBSCLIN_START_DATE, RAW_OBSCLIN_NAME, OBSCLIN_RESULT FROM mu_nicu.OBS_CLIN_NICU_ENTERAL_GI WHERE PATID=?"
    ):
        add(d, "Feeding/GI", name, res)
    for d, name, num, unit in q(
        "SELECT SPECIMEN_DATE, RAW_LAB_NAME, RESULT_NUM, RESULT_UNIT FROM mu_nicu.LAB_RESULT_CM WHERE PATID=?"
    ):
        add(d, "Lab", name, f"{num} {unit}".strip())
    for d, wt, sys, dia in q(
        "SELECT MEASURE_DATE, WT, SYSTOLIC, DIASTOLIC FROM mu_nicu.VITAL WHERE PATID=?"
    ):
        add(d, "Vital", f"weight {wt} kg", f"BP {sys}/{dia}")
    for d, scale, score in q(
        "SELECT OBSCLIN_START_DATE, RAW_OBSCLIN_NAME, OBSCLIN_RESULT FROM mu_nicu.OBS_CLIN_NICU_PAIN_SCORES WHERE PATID=?"
    ):
        add(d, "Pain", scale, f"score {score}")
    for d, prov, nid in q(
        "SELECT NOTE_DATE, PROVIDER_TYPE, NOTEID FROM mu_nicu.NOTE WHERE PATID=?"
    ):
        add(d, "Note", f"{prov} note", nid)

    df = pd.DataFrame(rows).dropna(subset=["date"])
    if df.empty:
        return df
    # Anchor day-of-life to the birth *date* (midnight); date-only events would
    # otherwise floor below a same-day birth timestamp and yield DOL -1.
    anchor = birth.normalize() if pd.notna(birth) else df["date"].min().normalize()
    df["dol"] = (df["date"].dt.normalize() - anchor).dt.days.clip(lower=0)
    df["category"] = pd.Categorical(df["category"], categories=CATEGORY_ORDER, ordered=True)
    return df.sort_values("date").reset_index(drop=True)


def weight_curve(con, patid: str) -> pd.DataFrame:
    df = con.execute(
        "SELECT MEASURE_DATE, WT FROM mu_nicu.VITAL WHERE PATID=? ORDER BY MEASURE_DATE", [patid]
    ).fetchdf()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["MEASURE_DATE"], errors="coerce")
    df["weight_kg"] = pd.to_numeric(df["WT"], errors="coerce")
    return df.dropna(subset=["date", "weight_kg"])[["date", "weight_kg"]]
