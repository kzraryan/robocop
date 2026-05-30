"""Risk model: predict a *prolonged NICU stay* (length of stay above the cohort
median) from structured features, with SHAP explanations (and a LightGBM-gain
fallback when SHAP/torch isn't importable).

LOS is excluded from the predictors since the label is derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FeatureBundle

EXCLUDE = {"los_days"}  # leak: label derives from this


@dataclass
class RiskModel:
    booster: object
    X: np.ndarray
    y: np.ndarray
    preds: np.ndarray
    feature_names: list[str]
    patids: list[str]
    threshold: float

    def patient_index(self, patid: str) -> int:
        return self.patids.index(patid)


def train_risk_model(bundle: FeatureBundle, num_boost_round: int = 120) -> RiskModel:
    import lightgbm as lgb

    feats = [c for c in bundle.feature_columns if c not in EXCLUDE]
    X = bundle.features[feats].to_numpy(dtype=float)
    los = bundle.features["los_days"].to_numpy(dtype=float)
    threshold = float(np.median(los))
    y = (los > threshold).astype(int)

    booster = lgb.train(
        {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "num_leaves": 16,
            "learning_rate": 0.05,
            "min_data_in_leaf": 5,
            "feature_pre_filter": False,
        },
        lgb.Dataset(X, y, feature_name=feats),
        num_boost_round=num_boost_round,
    )
    preds = booster.predict(X)
    return RiskModel(booster, X, y, preds, feats, list(bundle.features.index), threshold)


def _try_import_shap():
    """Best-effort SHAP import; works around occasional torch/dynamo issues."""
    try:
        import torch  # noqa: F401
        try:
            from torch._dynamo import eval_frame as _ef
            if not hasattr(_ef, "skip_code"):
                _ef.skip_code = lambda *a, **k: None
        except Exception:  # noqa: BLE001
            pass
    except ImportError:
        pass
    import shap
    return shap


def explain_patient(model: RiskModel, patid: str) -> pd.DataFrame:
    """Return a per-feature contribution table for one infant.

    Uses SHAP TreeExplainer when available, else falls back to global LightGBM
    gain (clearly labeled via the ``method`` column)."""
    i = model.patient_index(patid)
    x = model.X[i]
    try:
        shap = _try_import_shap()
        expl = shap.TreeExplainer(model.booster)
        sv = np.asarray(expl.shap_values(x.reshape(1, -1)))
        if sv.ndim == 3:        # (classes, n, feats)
            sv = sv[-1]
        sv = sv.flatten()
        method = "shap"
    except Exception:  # noqa: BLE001
        sv = model.booster.feature_importance(importance_type="gain").astype(float)
        sv = sv / (sv.sum() + 1e-9)
        method = "gain"

    df = pd.DataFrame(
        {"feature": model.feature_names, "value": x, "contribution": sv, "method": method}
    )
    df["abs"] = df["contribution"].abs()
    return df.sort_values("abs", ascending=False).drop(columns="abs").reset_index(drop=True)
