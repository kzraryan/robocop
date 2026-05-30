"""End-to-end checks for the analytics layer on freshly generated synthetic data
(no Ollama needed): features, similarity, phenotype graph, risk, timeline, NER."""

import duckdb
import pytest

from robocop import features, ingest, nicu_vocab, phenotype, risk, similarity, synth, timeline


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    frames = synth.generate(n_patients=60, seed=3)
    synth.write_csvs(frames, out_dir=d / "raw")
    db = ingest.build(raw_dir=d / "raw", db_path=d / "mu.duckdb")
    c = ingest.connect(db, read_only=True)
    yield c
    c.close()


def test_features_shape_and_signal(con):
    fb = features.build_features(con)
    assert len(fb.features) == 60
    assert "ga_weeks" in fb.feature_columns and "dx_rds" in fb.feature_columns
    # prematurity should drive length of stay (strong negative correlation)
    assert fb.features["ga_weeks"].corr(fb.features["los_days"]) < -0.4


def test_similarity_returns_explained_neighbors(con):
    fb = features.build_features(con)
    eng = similarity.SimilarityEngine(fb)
    p = fb.features.index[0]
    nbrs = eng.most_similar(p, k=5)
    assert len(nbrs) == 5
    assert all(n.patid != p for n in nbrs)
    # scores sorted descending
    assert nbrs == sorted(nbrs, key=lambda n: -n.score)
    assert all("similarity" in n.as_row() for n in nbrs)
    assert 0.0 <= eng.confidence(nbrs) <= 1.0


def test_phenotype_communities(con):
    fb = features.build_features(con)
    pg = phenotype.build_phenotype_graph(fb)
    assert pg.bipartite.number_of_nodes() > 60
    assert len(pg.communities) >= 1
    profiles = pg.community_profiles()
    assert all("top_conditions" in p for p in profiles)


def test_risk_model_separates_classes(con):
    fb = features.build_features(con)
    rm = risk.train_risk_model(fb)
    assert "los_days" not in rm.feature_names  # no leakage
    gap = rm.preds[rm.y == 1].mean() - rm.preds[rm.y == 0].mean()
    assert gap > 0.3
    ex = risk.explain_patient(rm, rm.patids[0])
    assert {"feature", "value", "contribution", "method"} <= set(ex.columns)


def test_timeline_multi_category(con):
    fb = features.build_features(con)
    p = fb.features.index[0]
    ev = timeline.patient_events(con, p)
    assert not ev.empty
    assert ev["dol"].min() >= 0
    assert ev["category"].nunique() >= 3


def test_nicu_ner_non_overlapping():
    text = "Infant with RDS on CPAP; sepsis work-up with blood culture, started ampicillin."
    ents = nicu_vocab.extract_entities(text)
    cans = {e["canonical"] for e in ents}
    assert "respiratory distress syndrome" in cans
    assert "CPAP" in cans and "ampicillin" in cans
    # non-overlapping spans
    spans = sorted((e["start"], e["end"]) for e in ents)
    assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1))
