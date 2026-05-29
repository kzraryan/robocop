import streamlit as st

from robocop import SITES, data
from robocop.config import DATA_ROOT

st.set_page_config(page_title="NICU data tools", page_icon=":material/clinical_notes:",
                   layout="wide")

st.title("NICU data tools")
st.caption(f"De-identified clinical data · {DATA_ROOT}")

site = st.selectbox("Site", SITES)


@st.cache_data(show_spinner=False)
def counts(site: str):
    return len(data.structured_files(site)), len(data.note_files(site))


n_tables, n_notefiles = counts(site)
c1, c2 = st.columns(2)
c1.metric("Structured tables", n_tables)
c2.metric("Note files", n_notefiles)

st.subheader("Open a tool")
a, b = st.columns(2)
with a:
    st.page_link("pages/1_Data_Browser.py", label="Data Browser & SQL",
                 icon=":material/database:")
    st.caption("Preview structured tables and run DuckDB SQL.")
with b:
    st.page_link("pages/2_Notes_Viewer.py", label="Notes Viewer",
                 icon=":material/description:")
    st.caption("Search and read individual clinical notes.")

with st.expander("All files in this site"):
    inv = data.inventory(site)
    if len(inv):
        st.dataframe(inv, use_container_width=True, height=400)
    else:
        st.warning("No files found. Check `CAIDF_DATA_ROOT`.")
