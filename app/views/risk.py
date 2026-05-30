"""Risk Prediction: LightGBM predicts a prolonged NICU stay (LOS above the
cohort median) from structured features; SHAP (or LightGBM gain) explains an
individual infant's predicted risk."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from robocop import risk as risk_mod
from ._ui import need_con


def render():
    st.header("Risk Prediction — Prolonged Stay")
    st.caption(
        "LightGBM predicts whether an infant's length of stay will exceed the "
        "cohort median, from gestational age, diagnoses, meds, labs, and "
        "interventions. SHAP explains each prediction."
    )
    if not need_con(services.get_con()):
        return
    rm = services.get_risk_model()
    fb = services.get_features()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Infants", len(rm.X))
    c2.metric("Features", rm.X.shape[1])
    c3.metric("LOS threshold (d)", int(rm.threshold))
    gap = rm.preds[rm.y == 1].mean() - rm.preds[rm.y == 0].mean()
    c4.metric("Class-mean gap", f"{gap:.2f}")

    df = fb.meta.copy()
    df["risk"] = rm.preds
    df["prolonged"] = rm.y
    df = df.sort_values("risk", ascending=False)
    st.subheader("Cohort risk ranking")
    st.dataframe(
        df[["ga_weeks", "los_days", "drg", "risk", "prolonged"]]
        .style.format({"risk": "{:.3f}"})
        .background_gradient(subset=["risk"], cmap="RdYlGn_r"),
        width="stretch", height=360,
    )

    st.subheader("Per-infant explanation")
    patid = st.selectbox(
        "Infant", rm.patids,
        format_func=lambda p: f"{p} · risk {rm.preds[rm.patient_index(p)]:.3f} · "
        f"{'prolonged' if rm.y[rm.patient_index(p)] else 'typical'}",
    )
    contrib = risk_mod.explain_patient(rm, patid).head(10)
    method = contrib["method"].iloc[0]
    if method == "gain":
        st.info("SHAP unavailable in this environment; showing global LightGBM gain.")

    left, right = st.columns([2, 3])
    with left:
        st.dataframe(
            contrib[["feature", "value", "contribution"]]
            .style.format({"value": "{:.2f}", "contribution": "{:+.3f}"})
            .background_gradient(subset=["contribution"], cmap="RdBu_r"),
            hide_index=True, width="stretch",
        )
    with right:
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(6, 4.2))
            c = contrib.iloc[::-1]
            colors = ["#d62728" if v > 0 else "#1f77b4" for v in c["contribution"]]
            ax.barh(c["feature"], c["contribution"], color=colors)
            ax.axvline(0, color="black", linewidth=0.5)
            ax.set_xlabel("SHAP value" if method == "shap" else "LightGBM gain")
            ax.set_title(f"Top contributors · {patid}")
            fig.tight_layout()
            st.pyplot(fig)
        except Exception:  # noqa: BLE001
            pass
