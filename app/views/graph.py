"""Phenotype Graph: patient–diagnosis bipartite graph, patient-similarity
projection, and greedy-modularity phenotype communities."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from ._ui import need_con


def render():
    st.header("Phenotype Graph")
    st.caption(
        "Patients linked by shared diagnoses, clustered into phenotype "
        "communities (NetworkX greedy modularity)."
    )
    if not need_con(services.get_con()):
        return
    pg = services.get_phenotype()

    G, Gp = pg.bipartite, pg.patient_graph
    profiles = [p for p in pg.community_profiles() if p["n_patients"] >= 3]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Infants", sum(1 for _, d in G.nodes(data=True) if d["kind"] == "patient"))
    c2.metric("Diagnoses", sum(1 for _, d in G.nodes(data=True) if d["kind"] == "diagnosis"))
    c3.metric("Similarity edges", Gp.number_of_edges())
    c4.metric("Communities (≥3)", len(profiles))

    t_comm, t_proj, t_central = st.tabs(["Communities", "Similarity graph", "Diagnosis centrality"])

    with t_comm:
        for p in profiles:
            tops = ", ".join(f"{n} ({c})" for n, c in p["top_conditions"][:5])
            st.markdown(f"**Community {p['community']}** — {p['n_patients']} infants")
            st.caption(f"Dominant: {tops}")
            with st.expander(f"members ({p['n_patients']})"):
                st.write(", ".join(p["members"]))
            st.divider()

    with t_proj:
        try:
            import matplotlib.pyplot as plt
            import networkx as nx
            fig, ax = plt.subplots(figsize=(9, 6))
            pos = nx.spring_layout(Gp, seed=42, k=0.4)
            colors = [pg.pid_to_comm.get(n, 0) for n in Gp.nodes()]
            sizes = [80 + 25 * Gp.nodes[n].get("n_dx", 0) for n in Gp.nodes()]
            nx.draw_networkx_edges(Gp, pos, alpha=0.15, ax=ax)
            nx.draw_networkx_nodes(Gp, pos, node_color=colors, node_size=sizes,
                                   cmap="tab20", linewidths=0.3, edgecolors="black", ax=ax)
            ax.set_title("Patient similarity graph (colored by community)")
            ax.axis("off")
            st.pyplot(fig)
        except Exception as e:  # noqa: BLE001
            st.info(f"Graph rendering unavailable: {e}")

    with t_central:
        import networkx as nx
        deg = nx.degree_centrality(G)
        rows = [(G.nodes[n]["name"], round(v, 3)) for n, v in deg.items()
                if G.nodes[n]["kind"] == "diagnosis"]
        df = pd.DataFrame(sorted(rows, key=lambda x: -x[1]),
                          columns=["diagnosis", "degree_centrality"])
        st.dataframe(df, hide_index=True, use_container_width=True, height=420)
