import streamlit as st

from robocop import SITES, sql, ui

ui.setup("Notes Viewer", "📝")
ui.sidebar_brand()


@st.cache_resource
def get_con():
    return sql.connect()


@st.cache_data(show_spinner="Loading note list…")
def catalog(site: str):
    return sql.note_catalog(get_con(), site)


site = st.sidebar.selectbox("Site", SITES)

ui.header(
    "Notes Viewer",
    subtitle=f"Free-text clinical notes · {site} NICU",
    badges=["De-identified", "Text loaded on demand", f"Site: {site}"],
)

try:
    cat = catalog(site)
except Exception as e:
    st.error(str(e))
    st.stop()

if not len(cat):
    st.warning("No notes found for this site.")
    st.stop()

sources = sorted(cat["source_file"].dropna().unique())
ui.kpis([
    ("Notes", f"{len(cat):,}", "text not loaded"),
    ("Source files", len(sources), "split for size"),
    ("Longest note", f"{int(cat['note_len'].max()):,}", "characters"),
])

ui.section("Catalog", "Find a note")
c1, c2 = st.columns(2)
id_filter = c1.text_input("Filter by note id contains")
source = c2.selectbox("Source file", ["(all)"] + sources)

view = cat
if id_filter:
    view = view[view["note_id"].astype(str).str.contains(id_filter, case=False, na=False)]
if source != "(all)":
    view = view[view["source_file"] == source]
view = view.sort_values("note_len", ascending=False)

st.caption(f"{len(view):,} of {len(cat):,} notes match")
st.dataframe(view, use_container_width=True, height=300)

ids = view["note_id"].astype(str).tolist()
if not ids:
    st.info("No notes match the filter.")
    st.stop()

ui.section("Reader", "Selected note")
note_id = st.selectbox("Select a note", ids)
if note_id:
    text = sql.get_note(get_con(), site, note_id)
    row = view[view["note_id"].astype(str) == note_id].iloc[0]
    ui.note_pane(text, tags=[
        f"id: {note_id}",
        f"{int(row['note_len']):,} chars",
        f"src: {row['source_file']}",
    ])
    with st.expander("Raw text (copyable)"):
        st.text_area("Note text", text, height=320, label_visibility="collapsed")
