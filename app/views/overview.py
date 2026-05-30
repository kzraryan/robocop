"""Cohort overview: demographics, gestational-age & LOS distributions, and the
most common diagnoses, medications, and procedures."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from ._ui import need_con


def render():
    st.header("Cohort Overview")
    st.caption("MU NICU cohort — gestational age drives length of stay and acuity.")
    con = services.get_con()
    if not need_con(con):
        return
    fb = services.get_features()

    n = len(fb.features)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Infants", n)
    c2.metric("Median GA (wk)", round(float(fb.features["ga_weeks"].median()), 1))
    c3.metric("Median LOS (days)", int(fb.features["los_days"].median()))
    c4.metric("Median diagnoses", int(fb.meta["n_diagnoses"].median()))

    left, right = st.columns(2)
    with left:
        st.subheader("Gestational age distribution")
        ga = fb.features["ga_weeks"].round().value_counts().sort_index()
        st.bar_chart(ga)
    with right:
        st.subheader("Length of stay by GA band")
        df = fb.features.copy()
        df["GA band"] = pd.cut(
            df["ga_weeks"], [0, 28, 32, 37, 100],
            labels=["<28wk", "28-31wk", "32-36wk", "≥37wk"],
        )
        st.bar_chart(df.groupby("GA band", observed=True)["los_days"].mean())

    st.subheader("Most common diagnoses, medications & procedures")
    t1, t2, t3 = st.columns(3)
    with t1:
        dx = con.execute(
            "SELECT RAW_DIAGNOSIS_NAME AS diagnosis, COUNT(DISTINCT PATID) AS infants "
            "FROM mu_nicu.DIAGNOSIS GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ).fetchdf()
        st.dataframe(dx, hide_index=True, width="stretch")
    with t2:
        rx = con.execute(
            "SELECT RAW_RX_MED_NAME AS medication, COUNT(DISTINCT PATID) AS infants "
            "FROM mu_nicu.PRESCRIBING GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ).fetchdf()
        st.dataframe(rx, hide_index=True, width="stretch")
    with t3:
        pr = con.execute(
            "SELECT RAW_PROCEDURE_NAME AS procedure, COUNT(DISTINCT PATID) AS infants "
            "FROM mu_nicu.PROCEDURES GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ).fetchdf()
        st.dataframe(pr, hide_index=True, width="stretch")

    with st.expander("Feature table (one row per infant)"):
        st.dataframe(fb.features.round(2), width="stretch", height=400)
