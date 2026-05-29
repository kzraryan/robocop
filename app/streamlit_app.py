import streamlit as st

from robocop import SITES, data
from robocop.config import DATA_ROOT

st.set_page_config(page_title="NICU data tools", page_icon=":material/monitoring:",
                   layout="wide")

st.title(":material/monitoring: NICU data tools")
st.caption(f"De-identified · cohort NICU · data root `{DATA_ROOT}`")

site = st.selectbox("Site", SITES)


@st.cache_data(show_spinner="Scanning files…")
def inventory(site: str):
    return data.inventory(site)


inv = inventory(site)
total_mb = inv["size_mb"].sum() if len(inv) else 0.0
size = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"

c1, c2, c3 = st.columns(3)
c1.metric("Files", f"{len(inv):,}")
c2.metric("Data volume", size)
c3.metric("Sites", len(SITES))

st.subheader("Tools")
l, r = st.columns(2)
l.page_link("pages/1_Data_Browser.py", label="Data Browser & SQL",
            icon=":material/database:")
r.page_link("pages/2_Notes_Viewer.py", label="Notes Viewer",
            icon=":material/description:")

st.subheader("Files")
if len(inv):
    st.dataframe(inv, use_container_width=True, height=460)
else:
    st.warning("No files found for this site. Check `CAIDF_DATA_ROOT`.")
