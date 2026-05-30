# robocop — NICU Patient Similarity & Cohort Intelligence

A local clinical-intelligence dashboard for the **CAIDF Year 2 (2026) Hackathon**
MU (University of Missouri) **NICU** dataset. Everything runs on the machine:
**DuckDB** (structured queries), **FAISS** (note vectors), **Ollama** (LLM +
embeddings). No data leaves the box.

The dataset's column descriptions repeatedly point at one goal — **patient
similarity** — so that is the centerpiece, surrounded by the supporting analytics
a clinician or researcher actually needs.

> Ships with a **synthetic, schema-faithful** generator (no PHI) where
> gestational age coherently drives length of stay, diagnoses, medications,
> ventilation, and note content — so similarity / risk / graph all show real
> signal. Drop real MU CSVs into `data/raw/` and the same pipeline runs unchanged.

## Pages

| Page | What it does |
|------|--------------|
| 🏥 Cohort Overview | GA / LOS distributions, top diagnoses · meds · procedures (DuckDB) |
| 📈 Patient Timeline | Every event (dx, labs, meds, procedures, vitals, vent, pain, feeds, notes) on one day-of-life axis + weight curve |
| 🧬 **Patient Similarity** | Find similar infants by a blend of **structured features + note embeddings**, with a per-factor "why" and a confidence score |
| 📝 Note Search | Semantic search over notes → timeline of matches → matched-section highlight → full note |
| 🔎 Ask the Data | Natural language → **local LLM writes DuckDB SQL** (grounded in the column descriptions), editable + safe; plus a SQL console |
| 🕸️ Phenotype Graph | Patient–diagnosis graph + patient-similarity projection + phenotype communities |
| ⚠️ Risk Prediction | LightGBM predicting **prolonged stay**, SHAP per-infant (LightGBM-gain fallback) |
| 💬 RAG Q&A | Note-grounded answers from a local LLM, citing patient IDs + dates |
| 🏷️ NLP Extraction | NICU-vocabulary regex tagger + optional LLM JSON entity extraction |
| ⚙️ System & Health | DuckDB / index / Ollama status |

## Architecture

```
resources/column_descriptions.txt   # the provided schema doc (LLM grounding)
src/robocop/
  config.py        # paths + model names (env-overridable)
  schema.py        # parse column descriptions -> catalog + LLM prompt
  synth.py         # GA-driven synthetic MU NICU data (CSVs + NOTE.csv)
  ingest.py        # CSVs -> DuckDB (mu_nicu views)
  features.py      # one-row-per-infant feature table (backs similarity/risk/graph)
  similarity.py    # patient-similarity engine (structured + note centroids)
  phenotype.py     # patient-diagnosis graph + communities (NetworkX)
  risk.py          # LightGBM prolonged-stay model + SHAP
  timeline.py      # unified per-infant event log
  nicu_vocab.py    # NICU regex entity extractor
  text2sql.py      # NL -> Ollama SQL, read-only validator, run
  embeddings.py    # Ollama embeddings client (+ disk cache)
  notes_index.py   # offset-preserving chunker, FAISS build/search, centroids
  llm.py           # Ollama chat / streaming / RAG / extraction (stdlib only)
app/
  streamlit_app.py # nav + entry point
  services.py      # cached resources (con, index, features, engines, models)
  views/*.py       # one module per page
scripts/build_index.py   # synth -> DuckDB -> FAISS
tests/                   # schema, SQL validator, chunker, analytics
```

## Setup

Requires a running **Ollama** with a coder model and an embedding model:

```bash
ollama pull qwen3-coder:30b
ollama pull mxbai-embed-large
pip install -r requirements.txt
```

## Build data + index, then run

```bash
python scripts/build_index.py                 # synth -> DuckDB -> FAISS embeddings
python scripts/build_index.py --skip-embed    # data + DuckDB only (no Ollama)
streamlit run app/streamlit_app.py
```

Most pages (overview, timeline, similarity, phenotype, risk, SQL, NER) work with
**`--skip-embed`** and no Ollama. Note Search, RAG, the LLM extractor, and the
note-embedding blend of Patient Similarity need Ollama (embeddings + chat).

## Configuration (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server |
| `ROBOCOP_CODER_MODEL` | `qwen3-coder:30b` | text-to-SQL / chat / RAG |
| `ROBOCOP_EMBED_MODEL` | `mxbai-embed-large` | note embeddings |
| `ROBOCOP_DATA_DIR` | `./data` | data root |
| `ROBOCOP_SQL_LIMIT` | `200` | default LIMIT injected into queries |
| `ROBOCOP_SITE` / `ROBOCOP_COHORT` | `MU` / `NICU` | narrowing layer for real data |

## Tests

```bash
pytest -q
```

Covers schema parsing, the read-only SQL validator, the offset-preserving note
chunker + FAISS search (stubbed embedder), and the full analytics layer
(features → similarity → phenotype → risk → timeline → NER) on generated data —
all without Ollama.

## Safety

- Generated/edited SQL is validated to a single read-only `SELECT`/`WITH`
  (DDL/DML rejected, LIMIT injected) and DuckDB is opened read-only.
- CSVs load as text so documented null sentinels (`/n`, `//N`) survive; the LLM
  is told to guard numeric casts with `TRY_CAST`.
- Synthetic data only — no PHI.
