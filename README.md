# NICU data tools

Browse the structured CSV tables, run SQL (DuckDB), and read clinical notes.

```bash
pip install -e .
streamlit run app/streamlit_app.py --server.port 8501
```

Set `CAIDF_DATA_ROOT` if the data is not at the default path.

The app uses a clinical-provider theme (`.streamlit/config.toml`) and a shared
UI kit (`robocop.ui`: branded header, KPI cards, sections, note reading pane)
so the three pages — Home, Data Browser & SQL, Notes Viewer — stay consistent.
