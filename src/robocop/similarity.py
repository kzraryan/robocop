"""NICU patient-similarity engine — the core hackathon capability.

Each infant becomes a standardized structured feature vector (GA, LOS, diagnosis
/ medication flags, lab summaries, intervention counts). When note embeddings are
available we also build a per-patient note-embedding centroid. Similarity is a
blend of structured cosine and note cosine, and we expose *why* two infants match
(top contributing factors + shared diagnoses) plus a confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .features import FeatureBundle

FRIENDLY = {
    "ga_weeks": "gestational age",
    "sex_male": "sex",
    "los_days": "length of stay",
    "dx_rds": "RDS",
    "dx_bpd": "BPD",
    "dx_nec": "NEC",
    "dx_rop": "ROP",
    "dx_sepsis": "sepsis",
    "dx_jaundice": "jaundice",
    "dx_pda": "PDA",
    "dx_apnea": "apnea of prematurity",
    "dx_anemia": "anemia of prematurity",
    "dx_ivh": "IVH",
    "n_diagnoses": "diagnosis burden",
    "med_caffeine": "caffeine",
    "med_surfactant": "surfactant",
    "med_antibiotic": "antibiotics",
    "med_diuretic": "diuretics",
    "n_medications": "medication count",
    "lab_bili_max": "peak bilirubin",
    "lab_crp_max": "peak CRP",
    "lab_hgb_min": "lowest hemoglobin",
    "lab_glucose_mean": "mean glucose",
    "n_procedures": "procedure count",
    "vent_events": "ventilation events",
    "n_notes": "note volume",
    "birth_weight_kg": "birth weight",
    "weight_gain_kg": "weight gain",
}


@dataclass
class Neighbor:
    patid: str
    score: float                 # blended similarity 0..1
    struct_score: float
    note_score: float
    shared_dx: list[str]
    top_factors: list[tuple[str, float]] = field(default_factory=list)

    def as_row(self) -> dict:
        return {
            "patid": self.patid,
            "similarity": round(self.score, 3),
            "structured": round(self.struct_score, 3),
            "notes": round(self.note_score, 3),
            "shared diagnoses": ", ".join(self.shared_dx) if self.shared_dx else "—",
            "why": ", ".join(FRIENDLY.get(f, f) for f, _ in self.top_factors[:4]),
        }


class SimilarityEngine:
    def __init__(
        self,
        bundle: FeatureBundle,
        note_centroids: tuple[list[str], np.ndarray] | None = None,
    ):
        self.bundle = bundle
        self.patids = list(bundle.features.index)
        self.cols = bundle.feature_columns

        X = bundle.features[self.cols].to_numpy(dtype=float)
        self.scaler = StandardScaler()
        self.Z = self.scaler.fit_transform(X)            # standardized features
        self.Zn = _row_normalize(self.Z)                 # unit rows for cosine

        # optional note centroids aligned to self.patids
        self.note_mat: np.ndarray | None = None
        if note_centroids is not None:
            ids, mat = note_centroids
            lut = {p: i for i, p in enumerate(ids)}
            dim = mat.shape[1]
            aligned = np.zeros((len(self.patids), dim), dtype=np.float32)
            for i, p in enumerate(self.patids):
                if p in lut:
                    aligned[i] = mat[lut[p]]
            self.note_mat = _row_normalize(aligned)

    @property
    def has_notes(self) -> bool:
        return self.note_mat is not None

    def _struct_sims(self, i: int) -> np.ndarray:
        return self.Zn @ self.Zn[i]

    def _note_sims(self, i: int) -> np.ndarray:
        if self.note_mat is None:
            return np.zeros(len(self.patids))
        return self.note_mat @ self.note_mat[i]

    def most_similar(self, patid: str, k: int = 10, alpha: float = 0.6) -> list[Neighbor]:
        """alpha weights the structured cosine; (1-alpha) weights notes."""
        if patid not in self.patids:
            raise KeyError(patid)
        i = self.patids.index(patid)
        struct = self._struct_sims(i)
        note = self._note_sims(i)
        a = alpha if self.has_notes else 1.0
        blended = a * struct + (1 - a) * note

        order = np.argsort(-blended)
        out: list[Neighbor] = []
        my_dx = self.bundle.dx_sets.get(patid, set())
        for j in order:
            if j == i:
                continue
            pj = self.patids[j]
            shared = sorted(my_dx & self.bundle.dx_sets.get(pj, set()))
            out.append(
                Neighbor(
                    patid=pj,
                    score=float(blended[j]),
                    struct_score=float(struct[j]),
                    note_score=float(note[j]),
                    shared_dx=shared,
                    top_factors=self._top_factors(i, j),
                )
            )
            if len(out) >= k:
                break
        return out

    def _top_factors(self, i: int, j: int) -> list[tuple[str, float]]:
        """Per-feature contribution to the structured cosine (z_i * z_j on unit
        vectors); large positive => the pair is jointly notable on that feature."""
        contrib = self.Zn[i] * self.Zn[j]
        idx = np.argsort(-contrib)
        return [(self.cols[c], float(contrib[c])) for c in idx if contrib[c] > 0][:8]

    def confidence(self, neighbors: list[Neighbor]) -> float:
        """Crude confidence: top score scaled by its margin over the median."""
        if not neighbors:
            return 0.0
        scores = np.array([n.score for n in neighbors])
        top = scores[0]
        margin = top - np.median(scores)
        return float(np.clip(0.5 * top + 0.5 * (0.5 + margin), 0, 1))


def _row_normalize(M: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (M / norms).astype(np.float32)
