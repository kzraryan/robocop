# robocop — MU NICU Data Viewer

A local data viewer for the **CAIDF Year 2 (2026) Hackathon** MU (University of
Missouri) **NICU** dataset. It has two parts:

1. **Text-to-SQL.** You type a question (and can hand-edit the result); a local
   coding LLM (via Ollama) writes a **DuckDB SQL** query grounded in the official
   column descriptions, validated read-only, then run in-app.
2. **Clinical-note semantic search.** MU clinical notes are chunked and embedded
   so you can search them — globally or per patient — and get a **timeline** of
   the most relevant notes. Click a hit to see the **matched section**, then
   expand the **full note** with the match highlighted.

Everything runs locally: **DuckDB** (embedded), **FAISS** (vectors), **Ollama**
(LLM + embeddings). No data leaves the machine.

> The shipped data is **synthetic** and schema-faithful (no PHI). Drop real MU
> CSVs into `data/raw/` and the same pipeline works unchanged.

## Layout

```
resources/column_descriptions.txt   # the provided schema doc (LLM grounding)
src/robocop/
  config.py        # paths + model names (all env-overridable)
  schema.py        # parse column descriptions -> schema catalog + LLM prompt
  synth.py         # synthetic MU NICU data generator (CSVs + NOTE.csv)
  ingest.py        # load CSVs -> DuckDB (mu_nicu views)
  text2sql.py      # NL -> Ollama SQL, read-only validator, run
  embeddings.py    # Ollama embeddings client (+ disk cache)
  notes_index.py   # offset-preserving chunker, FAISS build/search
app/streamlit_app.py   # the 2-tab UI
scripts/build_index.py # synth data -> DuckDB -> FAISS index
tests/                 # schema parse, SQL validator, chunker/search
```

## Setup

Requires a running **Ollama** server with a coder model and an embedding model:

```bash
ollama pull qwen3-coder:30b
ollama pull mxbai-embed-large
pip install -r requirements.txt
```

## Build the data + index

```bash
python scripts/build_index.py                 # synth -> DuckDB -> FAISS
python scripts/build_index.py --skip-embed    # data + DuckDB only (no Ollama)
python scripts/build_index.py --patients 300  # more synthetic infants
```

## Run

```bash
streamlit run app/streamlit_app.py
```

- **Query data:** e.g. *"infants born before 28 weeks who received caffeine"* →
  generated SQL appears in an editable box; run it, view/download results. PATIDs
  in the result are offered to the notes tab.
- **Search notes:** e.g. *"feeding intolerance and abdominal distension"* →
  timeline + ranked matches; expand to see the matched section and full note.

## Configuration (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server |
| `ROBOCOP_CODER_MODEL` | `qwen3-coder:30b` | text-to-SQL model |
| `ROBOCOP_EMBED_MODEL` | `mxbai-embed-large` | note embeddings |
| `ROBOCOP_DATA_DIR` | `./data` | data root |
| `ROBOCOP_SQL_LIMIT` | `200` | default LIMIT injected into queries |
| `ROBOCOP_SITE` / `ROBOCOP_COHORT` | `MU` / `NICU` | narrowing layer for real data |

## Tests

```bash
pytest -q
```

Covers schema parsing, the read-only SQL validator (rejects non-SELECT / multiple
statements, injects LIMIT), and the offset-preserving chunker + FAISS search
(with a stubbed embedder, so no Ollama needed).

## Safety notes

- Generated/edited SQL is validated to a **single read-only `SELECT`/`WITH`**
  before execution; DDL/DML keywords are rejected and the DuckDB connection is
  opened read-only.
- CSVs are loaded as text so documented null sentinels (`/n`, `//N`) survive; the
  LLM is instructed to guard numeric casts (`TRY_CAST(... )`).
