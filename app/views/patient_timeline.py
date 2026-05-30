"""Patient Timeline: every event in one infant's NICU course on a single
day-of-life axis, plus the weight-gain trajectory."""

from __future__ import annotations

import streamlit as st

import services
from robocop import timeline
from ._ui import need_con


def render():
    st.header("Patient Timeline")
    st.caption("A unified longitudinal view of one infant's entire NICU course.")
    con = services.get_con()
    if not need_con(con):
        return
    fb = services.get_features()

    patid = _select_patient(fb)
    meta = fb.meta.loc[patid]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GA (weeks)", meta["ga_weeks"])
    c2.metric("Sex", meta["sex"])
    c3.metric("LOS (days)", int(meta["los_days"]))
    c4.metric("DRG", meta["drg"])

    events = timeline.patient_events(con, patid)
    if events.empty:
        st.info("No events for this infant.")
        return

    st.subheader("Event timeline (by day of life)")
    try:
        import plotly.express as px
        fig = px.scatter(
            events, x="dol", y="category", color="category",
            hover_data=["label", "detail", "date"],
        )
        fig.update_traces(marker=dict(size=11, opacity=0.75))
        fig.update_layout(height=380, showlegend=False,
                          margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="Day of life")
        st.plotly_chart(fig, width="stretch")
    except Exception:  # noqa: BLE001 - plotly optional
        st.dataframe(events, hide_index=True, width="stretch")

    st.subheader("Weight trajectory")
    wc = timeline.weight_curve(con, patid)
    if not wc.empty:
        st.line_chart(wc.set_index("date")["weight_kg"])

    st.subheader("Event log")
    cats = st.multiselect(
        "Filter categories", list(events["category"].cat.categories),
        default=list(events["category"].cat.categories),
    )
    view = events[events["category"].isin(cats)][["dol", "date", "category", "label", "detail"]]
    st.dataframe(view, hide_index=True, width="stretch", height=420)


def _select_patient(fb) -> str:
    ids = list(fb.features.index)
    return st.selectbox(
        "Infant", ids,
        format_func=lambda p: f"{p} · GA {fb.meta.loc[p,'ga_weeks']}wk · "
        f"LOS {int(fb.meta.loc[p,'los_days'])}d",
    )
