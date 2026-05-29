import streamlit as st

from robocop import SITES, sql

st.set_page_config(page_title="Notes Viewer", page_icon=":material/description:",
                   layout="wide")
st.title(":material/description: Notes Viewer")


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

sources = sorted(cat["source_file"].dropna().unique())
c1, c2 = st.columns(2)
c1.metric("Notes", f"{len(cat):,}", help="Text not loaded — fetched per note")
c2.metric("Source files", len(sources))

f1, f2 = st.columns(2)
id_filter = f1.text_input("Filter by note id contains")
source = f2.selectbox("Source file", ["(all)"] + sources)

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
    row = view[view["note_id"].astype(str) == note_id].iloc[0]
    with st.container(border=True):
        st.badge(f"id {note_id}", icon=":material/tag:")
        st.badge(f"{int(row['note_len']):,} chars", icon=":material/format_size:")
        st.badge(row["source_file"], icon=":material/draft:")
        st.text_area("Note text", text, height=460, label_visibility="collapsed")
