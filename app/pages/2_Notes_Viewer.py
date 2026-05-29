import streamlit as st

from robocop import SITES, sql

st.set_page_config(page_title="Notes Viewer", layout="wide")
st.title("Notes Viewer")


@st.cache_resource
def get_con():
    return sql.connect()


@st.cache_data(show_spinner="Loading note list…")
def catalog(site: str):
    return sql.note_catalog(get_con(), site)


site = st.sidebar.selectbox("Site", SITES)

try:
    cat = catalog(site)
except Exception as e:
    st.error(str(e))
    st.stop()

if not len(cat):
    st.warning("No notes found for this site.")
    st.stop()

st.caption(f"{len(cat):,} notes (text not loaded)")

c1, c2 = st.columns(2)
id_filter = c1.text_input("Filter by note id contains")
sources = sorted(cat["source_file"].dropna().unique())
source = c2.selectbox("Source file", ["(all)"] + sources)

view = cat
if id_filter:
    view = view[view["note_id"].astype(str).str.contains(id_filter, case=False, na=False)]
if source != "(all)":
    view = view[view["source_file"] == source]
view = view.sort_values("note_len", ascending=False)

st.dataframe(view, use_container_width=True, height=300)

ids = view["note_id"].astype(str).tolist()
if not ids:
    st.info("No notes match the filter.")
    st.stop()

note_id = st.selectbox("Select a note", ids)
if note_id:
    text = sql.get_note(get_con(), site, note_id)
    st.text_area("Note text", text, height=480)
