import streamlit as st

from robocop import SITES, data, ui
from robocop.config import DATA_ROOT

ui.setup("Home", "🩺")
ui.sidebar_brand()

site = st.sidebar.selectbox("Site", SITES)

ui.header(
    "NICU Clinical Workspace",
    subtitle=f"CAIDF de-identified clinical data · {DATA_ROOT}",
    badges=["De-identified", "Cohort: NICU", f"Site: {site}"],
)


@st.cache_data(show_spinner="Scanning files…")
def overview(site: str):
    inv = data.inventory(site)
    return inv, len(data.structured_files(site)), len(data.note_files(site))


inv, n_tables, n_notefiles = overview(site)
total_mb = inv["size_mb"].sum() if len(inv) else 0.0
size_label = f"{total_mb/1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"

ui.kpis([
    ("Sites", len(SITES), "MU · UIC · Iowa"),
    ("Files on disk", f"{len(inv):,}", site),
    ("Structured tables", n_tables, "queryable via SQL"),
    ("Note files", n_notefiles, "free-text clinical notes"),
    ("Data volume", size_label, f"{site} NICU tree"),
])

ui.section("Workspace", "Tools")
ui.nav_cards([
    ("🗄️", "Data Browser & SQL",
     "Browse every structured table and run DuckDB SQL directly against the "
     "CSVs — no full load. Open it from the sidebar."),
    ("📝", "Notes Viewer",
     "Scan the note catalog (ids + length only, text not loaded) and open any "
     "single note in a clean reading pane."),
])

ui.section("Inventory", f"Files in the {site} NICU tree")
if len(inv):
    st.dataframe(inv, use_container_width=True, height=460)
else:
    st.warning("No files found for this site. Check `CAIDF_DATA_ROOT`.")
