import streamlit as st

from robocop import SITES, sql

st.set_page_config(page_title="Notes Viewer", page_icon=":material/description:",
                   layout="wide")
st.title("Notes Viewer")


@st.cache_resource
def get_con():
    return sql.connect()


@st.cache_data(show_spinner="Preparing notes (one-time per site)…")
def prepare(site: str) -> int:
    con = get_con()
    sql.notes_parquet(con, site)        # build the columnar cache once
    return sql.note_count(con, site)


site = st.sidebar.selectbox("Site", SITES)
con = get_con()

try:
    total = prepare(site)
except Exception as e:
    st.error(str(e))
    st.stop()

if not total:
    st.warning("No notes found for this site.")
    st.stop()

st.caption(f"{total:,} notes")

mode = st.radio("Find a note", ["Search text", "By ID", "Browse"], horizontal=True)
note_id = None

if mode == "Search text":
    term = st.text_input("Search within note text", placeholder="e.g. caffeine apnea")
    if term:
        with st.spinner("Searching…"):
            hits = sql.search_note_text(con, site, term)
        if len(hits):
            st.caption(f"Showing up to {len(hits)} matches")
            snip = dict(zip(hits["note_id"], hits["snippet"]))
            note_id = st.selectbox(
                "Matches", hits["note_id"].tolist(),
                format_func=lambda i: f"{i} — {snip.get(i, '')[:80]}",
            )
        else:
            st.info("No notes contain that text.")

elif mode == "By ID":
    term = st.text_input("Note ID (full or partial)")
    if term:
        ids = sql.search_note_ids(con, site, term)
        note_id = st.selectbox("Matches", ids) if ids else None
        if not ids:
            st.info("No matching id.")

else:  # Browse
    i = st.number_input("Note #", min_value=1, max_value=total, value=1, step=1)
    note_id = sql.note_id_at(con, site, int(i) - 1)

if note_id:
    text = sql.get_note(con, site, note_id)
    with st.container(border=True):
        st.badge(f"note_id {note_id}", icon=":material/tag:")
        st.text_area("Note", text, height=460, label_visibility="collapsed")
