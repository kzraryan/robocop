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

## Data: real MU NICU drop (default) or synthetic

By default the pipeline uses the **real** server drop at
`/media/data/caidf_data/MU/NICU` (override with `ROBOCOP_REAL_DIR`):

```
MU/NICU/
  STRUCTURED_DATA_V1/   # ENCOUNTER, CONDITION, DEMOGRAPHIC, DIAGONSIS(sic), LAB_RESULT_CM,
                        # PRESCRIBING, PROCEDURES, VITAL, OBS_CLIN_NICU_{ENTERAL_GI,PAIN_SCORES,VENT}
  2024-11-20/           # note text shards: NOTE_ID + NOTE (or DEID_NOTE_RELEASE)
  NICU_NOTE_METADATA.csv  NICU_EVENTS.csv  NICU_PROVIDERS.csv   # note PATID/date/provider links
```

The structured filenames match the column doc (the `DIAGONSIS` misspelling is
handled). `mu_nicu.NOTE` is **assembled** by joining the note text to the
metadata/provider sidecars; the linking columns are auto-detected. Everything is
loaded as text so null sentinels (`/n`, `//N`, `\N`, …) survive; numeric casts use
`TRY_CAST`.

**On the hackathon server:**

```bash
python scripts/inspect_data.py                # confirm files/headers + detected NOTE mapping (no PHI)
python scripts/build_index.py --skip-embed    # real data -> DuckDB (no Ollama)
python scripts/build_index.py --max-notes 2000  # + embeddings/FAISS (random note cap)

# Preferred for a demo: full note history of a focused cohort, so timelines and
# the similarity note-blend have continuity (richest histories chosen first).
python scripts/build_index.py --cohort-patients 100 --min-notes 50
streamlit run app/streamlit_app.py
```

`--cohort-patients N --min-notes M` keeps N patients who each have at least M
notes and embeds their full history — a longitudinal record per infant, not
`--max-notes`' scattered random rows. The **fewest**-qualifying patients are
taken first, so `--cohort-patients 10 --min-notes 50` gives ~50-note infants
rather than the few-thousand-note outliers, keeping the job small. Add
`--per-patient-cap K` to hard-bound each history to its earliest K notes, and
`--dry-run` to print the selected counts without embedding.

On real data the build **refuses to embed the whole corpus** unless you pass an
explicit scope (`--cohort-patients`, `--max-notes`, or `--all-notes`), so an
omitted flag can't silently launch a 600k-note run.

If `inspect_data.py` shows a misdetected note column, set the matching override
(e.g. `ROBOCOP_NOTE_PROVIDER_COL`, `ROBOCOP_NOTE_DATE_COL`) and rebuild.

**Synthetic demo (off-server / no real data):**

```bash
python scripts/build_index.py --synthetic --skip-embed   # generate + DuckDB
python scripts/build_index.py --synthetic                # + embeddings
streamlit run app/streamlit_app.py
```

Most pages (overview, timeline, similarity, phenotype, risk, SQL, NER) work with
**`--skip-embed`** and no Ollama. Note Search, RAG, the LLM extractor, and the
note-embedding blend of Patient Similarity need Ollama (embeddings + chat).

## Configuration (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `ROBOCOP_REAL_DIR` | `/media/data/caidf_data/MU/NICU` | real MU NICU data root |
| `ROBOCOP_NOTE_*_COL` | (auto-detect) | override a note link column (`PATID`/`DATE`/`PROVIDER`/`TEXT`/`ID`/`ENC`) |
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
