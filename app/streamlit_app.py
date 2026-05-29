import streamlit as st

from robocop import SITES, data
from robocop.config import DATA_ROOT

st.set_page_config(page_title="NICU data tools", layout="wide")

st.title("NICU data tools")
st.caption(f"Data root: `{DATA_ROOT}`")
st.write("Use the pages in the sidebar: **Data Browser** to query tables, "
         "**Notes Viewer** to read clinical notes.")


@st.cache_data(show_spinner="Scanning files…")
def inventory(site: str):
    return data.inventory(site)


site = st.selectbox("Site", SITES)
inv = inventory(site)
if len(inv):
    st.write(f"**{len(inv)}** files · **{inv['size_mb'].sum():.1f} MB**")
    st.dataframe(inv, use_container_width=True, height=480)
else:
    st.warning("No files found for this site.")
