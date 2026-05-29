# NICU data tools

Browse the structured CSV tables, run SQL (DuckDB), and read clinical notes.

```bash
pip install -e .
streamlit run app/streamlit_app.py --server.port 8501
```

Set `CAIDF_DATA_ROOT` if the data is not at the default path.

The Notes Viewer builds a one-time Parquet index of each site's notes (so
listing and reading a note is fast instead of re-scanning the heavy CSVs).
It is stored in `ROBOCOP_CACHE` (default `~/.cache/robocop`) and rebuilt only
when the source note files change.
