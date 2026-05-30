"""Patient Similarity — the core capability. Pick an index infant and find the
most similar infants by a blend of structured features and clinical-note
embeddings, with a per-factor explanation of each match and a confidence score."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from robocop import timeline
from ._ui import need_con


def render():
    st.header("Patient Similarity")
    st.caption(
        "Find infants most similar to an index patient — blending structured "
        "features (GA, LOS, diagnoses, meds, labs, interventions) with clinical "
        "note embeddings. The match is explained, not a black box."
    )
    con = services.get_con()
    if not need_con(con):
        return
    fb = services.get_features()
    eng = services.get_similarity()

    c1, c2, c3 = st.columns([2, 1, 1])
    patid = c1.selectbox(
        "Index infant", list(fb.features.index),
        format_func=lambda p: f"{p} · GA {fb.meta.loc[p,'ga_weeks']}wk · "
        f"LOS {int(fb.meta.loc[p,'los_days'])}d",
    )
    k = c2.slider("Neighbors", 3, 20, 8)
    if eng.has_notes:
        alpha = c3.slider("Structured ↔ Notes", 0.0, 1.0, 0.6,
                          help="1.0 = structured only, 0.0 = notes only")
    else:
        alpha = 1.0
        c3.caption("Notes blend disabled\n(no embeddings built).")

    neighbors = eng.most_similar(patid, k=k, alpha=alpha)
    conf = eng.confidence(neighbors)

    m1, m2 = st.columns([1, 3])
    m1.metric("Match confidence", f"{conf:.0%}")
    m2.metric("Matched infants", len(neighbors))

    # Cohort note timeline — a top-level visualization comparing the index
    # infant against its matches across day-of-life (not hidden in an expander).
    st.subheader("Cohort timeline — index infant vs. matches")
    st.caption(
        "Each row is an infant; each point is a clinical event placed at its day "
        "of life, colored by event type. The index infant (★) is at the top."
    )
    _cohort_timeline(con, patid, neighbors)

    st.subheader("Most similar infants")
    rows = []
    for n in neighbors:
        r = n.as_row()
        m = fb.meta.loc[n.patid]
        r = {"patid": n.patid, "GA (wk)": m["ga_weeks"], "LOS (d)": int(m["los_days"]),
             **{kk: vv for kk, vv in r.items() if kk != "patid"}}
        rows.append(r)
    df = pd.DataFrame(rows)
    st.dataframe(
        df.style.background_gradient(subset=["similarity"], cmap="Greens"),
        hide_index=True, width="stretch",
    )

    st.subheader("Why these match")
    idx_meta = fb.meta.loc[patid]
    st.markdown(
        f"**Index {patid}** — GA {idx_meta['ga_weeks']}wk, LOS {int(idx_meta['los_days'])}d, "
        f"{idx_meta['n_diagnoses']} diagnoses."
    )
    for n in neighbors[:5]:
        why = ", ".join(f"{services.similarity.FRIENDLY.get(f,f)}" for f, _ in n.top_factors[:5])
        shared = ", ".join(n.shared_dx) if n.shared_dx else "—"
        with st.expander(f"{n.patid} · similarity {n.score:.3f}"):
            st.write(f"**Shared diagnoses:** {shared}")
            st.write(f"**Top shared factors:** {why}")
            st.caption(f"structured {n.struct_score:.3f} · notes {n.note_score:.3f}")


def _cohort_timeline(con, patid, neighbors) -> None:
    """Plot every infant's events on a shared day-of-life axis. Dots are colored
    by **event type** (diagnosis, medication, lab, …); the index infant stays
    distinguishable by its row label. Shown as a primary chart."""
    ids = [patid] + [n.patid for n in neighbors]
    rows = []
    for pid in ids:
        ev = timeline.patient_events(con, pid)
        ylabel = f"★ {pid} (index)" if pid == patid else f"Patient {pid}"
        for r in ev.itertuples(index=False):
            rows.append({
                "infant": ylabel,
                "dol": r.dol,
                "event": str(r.category),
                "label": r.label,
            })

    if not rows:
        st.info(
            "No dated events available for this cohort yet — build the data "
            "(`python scripts/build_index.py`) to populate this timeline."
        )
        return

    tdf = pd.DataFrame(rows)
    # Index infant on top; matches below in similarity order.
    y_order = list(reversed(
        [f"★ {patid} (index)"] + [f"Patient {n.patid}" for n in neighbors]
    ))
    # Stable, readable-on-light colors per event category.
    color_map = {
        "Diagnosis": "#c0392b", "Condition": "#8e44ad", "Medication": "#27ae60",
        "Procedure": "#8c564b", "Ventilation": "#2471a3", "Feeding/GI": "#e67e22",
        "Lab": "#1696a3", "Vital": "#9a9412", "Pain": "#d6608f", "Note": "#5d6d7e",
    }
    try:
        import plotly.express as px
        fig = px.scatter(
            tdf, x="dol", y="infant", color="event",
            render_mode="svg",  # avoid WebGL (scattergl); some browsers lack it
            category_orders={
                "infant": y_order,
                "event": [c for c in color_map if c in set(tdf["event"])],
            },
            color_discrete_map=color_map,
            hover_data=["label"],
        )
        fig.update_traces(marker=dict(size=11, opacity=0.85,
                                      line=dict(width=0.5, color="#ffffff")))
        fig.update_layout(
            height=max(260, 48 * len(ids)),
            xaxis_title="Day of life", yaxis_title="",
            legend_title="Event", legend=dict(orientation="h", y=1.06, x=0),
            margin=dict(l=10, r=10, t=10, b=10),
            font=dict(color="#28261d", size=13),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(gridcolor="#e6e2d8", zeroline=False)
        # Force a categorical y-axis: numeric-looking PATIDs would otherwise be
        # read as numbers and shown with SI suffixes (e.g. '2M' for 2000123).
        fig.update_yaxes(gridcolor="#e6e2d8", type="category",
                         categoryorder="array", categoryarray=y_order)
        st.plotly_chart(fig, width="stretch")
    except Exception:  # noqa: BLE001
        st.dataframe(tdf, hide_index=True, width="stretch")
