# robocop — CAIDF Year 2 2026 Hackathon (NICU cohort)

Toolkit for the **NICU cohort** of the CAIDF de-identified clinical dataset:
load structured tables + free-text notes across the three sites (UIC, Iowa, MU),
search/summarize notes with **local LLMs (Ollama)**, and ship a demo in
Streamlit.

> **Workflow:** edit & commit on your laptop → `git pull` on the GPU server →
> run there. The data and the A100 live on the server; this repo carries **code
> only — never the data.**

## Event at a glance
- **Fri May 29 & Sat May 30, 8 AM–6 PM.** Fri: kickoff, explore data, pick focus,
  "Special Twist #1" at 11 AM, build prototype. Sat: refine, build the **PPT
  pitch (≤5 min, may include video/audio)**, record in the pitch room.
  **Deadline to submit: Sat 6 PM.**
- Cohort: **NICU** (13,904 infants 0–1 yr; data through 2024-07-31).
- See `docs/DATA.md` (data map) and `docs/SERVER.md` (compute & models).

## Quick start (on the server)
```bash
conda activate hackathon                      # Python 3.11 env, all deps present
git clone <this-repo> robocop && cd robocop   # or: git pull
pip install -e . --no-deps                    # makes `import robocop` work
cp .env.example .env                           # adjust CAIDF_DATA_ROOT if needed

python scripts/env_check.py                    # confirm GPU + Ollama + packages
python scripts/data_inventory.py               # see what data is actually on disk
python scripts/smoke_test.py                   # data loads + Ollama answers
streamlit run app/streamlit_app.py --server.port 8501   # the demo
```
`pip install -e . --no-deps` only registers the package — it won't touch the
curated conda env.

## Layout
```
src/robocop/
  config.py   data root, per-site NICU paths, model defaults (env-overridable)
  data.py     discover + load CSVs (robust to messy/uncertain file names)
  notes.py    detect id/text cols, clean, chunk free-text notes
  llm.py      Ollama chat / generate / embed (local, no API keys)
  rag.py      FAISS dense + BM25 sparse + hybrid search over notes
scripts/      env_check · data_inventory · smoke_test
app/          streamlit_app.py  (inventory · notes search · ask-the-notes)
notebooks/    01_nicu_eda.py    (jupytext percent format — review-friendly)
docs/         DATA.md · SERVER.md
```

## Usage sketch
```python
from robocop import data, notes, rag, llm

df  = notes.normalize(data.load_notes("Iowa"))        # tidy note_id / text
idx = rag.NoteIndex.build(df["text"].tolist(),         # local embeddings + BM25
                          metadata=df.to_dict("records"))
hits = idx.search_hybrid("apnea of prematurity caffeine", k=5)

answer = llm.chat("Summarize the NICU course.", system="You are a clinical NLP assistant.")
```

## Data handling rules
- De-identified, but **treat as sensitive**: keep it on the server.
- `.gitignore` blocks `*.csv/*.xlsx/*.parquet/...` and `data/`, `artifacts/`,
  FAISS indices, etc. To commit a *tiny* lookup/example file, force it
  deliberately: `git add -f path/to/small_example.csv`.
- Don't paste raw note text into the public pitch deck.

## Config (env vars, see `.env.example`)
`CAIDF_DATA_ROOT` · `OLLAMA_HOST` · `ROBOCOP_CHAT_MODEL` ·
`ROBOCOP_EMBED_MODEL` · `ROBOCOP_ST_EMBED_MODEL`.
