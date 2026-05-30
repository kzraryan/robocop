"""Phenotype graph over the NICU cohort.

Builds a patient–diagnosis bipartite graph and a patient–patient similarity
projection (edge weight = shared diagnoses), then detects phenotype communities
with greedy modularity. Pure NetworkX so it runs anywhere.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import networkx as nx

from .features import FeatureBundle


@dataclass
class PhenotypeGraph:
    bipartite: nx.Graph
    patient_graph: nx.Graph
    communities: list[set]
    pid_to_comm: dict[str, int]
    dx_sets: dict[str, set]

    def community_profiles(self) -> list[dict]:
        out = []
        for i, comm in enumerate(self.communities):
            members = sorted(comm)
            counter: Counter = Counter()
            for pid in members:
                for d in self.dx_sets.get(pid, set()):
                    counter[d] += 1
            out.append(
                {
                    "community": i + 1,
                    "n_patients": len(members),
                    "members": members,
                    "top_conditions": counter.most_common(6),
                }
            )
        return out


def build_phenotype_graph(bundle: FeatureBundle, min_shared: int = 2) -> PhenotypeGraph:
    dx_sets = bundle.dx_sets
    G = nx.Graph()
    for pid in bundle.features.index:
        G.add_node(("P", pid), kind="patient")
    for pid, dxs in dx_sets.items():
        for d in dxs:
            cn = ("D", d)
            if not G.has_node(cn):
                G.add_node(cn, kind="diagnosis", name=d)
            G.add_edge(("P", pid), cn)

    # patient-patient projection weighted by shared diagnoses
    Gp = nx.Graph()
    for pid in bundle.features.index:
        Gp.add_node(pid, n_dx=len(dx_sets.get(pid, set())))
    pids = list(bundle.features.index)
    for a in range(len(pids)):
        for b in range(a + 1, len(pids)):
            shared = dx_sets.get(pids[a], set()) & dx_sets.get(pids[b], set())
            if len(shared) >= min_shared:
                Gp.add_edge(pids[a], pids[b], weight=len(shared))

    try:
        from networkx.algorithms.community import greedy_modularity_communities
        communities = list(greedy_modularity_communities(Gp, weight="weight"))
    except Exception:  # noqa: BLE001 - tiny/edgeless graph
        communities = [set(Gp.nodes())]
    pid_to_comm = {pid: i for i, comm in enumerate(communities) for pid in comm}

    return PhenotypeGraph(G, Gp, communities, pid_to_comm, dx_sets)
