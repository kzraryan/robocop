import streamlit as st

from robocop import SITES, sql

st.set_page_config(page_title="Data Browser", page_icon=":material/database:",
                   layout="wide")
st.title("Data Browser & SQL")


@st.cache_resource(show_spinner="Registering tables…")
def load(site: str):
    con = sql.connect()
    views = sql.register_site(con, site)
    return con, views


site = st.sidebar.selectbox("Site", SITES)
con, views = load(site)

if not views:
    st.warning("No structured tables found for this site.")
    st.stop()

names = sorted(views)
st.sidebar.metric("Tables", len(names))
view = st.sidebar.radio("Tables", names)

st.subheader(view)
st.caption(views[view])
with st.expander("Schema"):
    st.dataframe(sql.table_schema(con, view), use_container_width=True)
st.caption("Preview · first 100 rows")
st.dataframe(sql.table_preview(con, view), use_container_width=True, height=320)

st.divider()
st.subheader("SQL")
with st.expander("Tables you can query"):
    st.write(", ".join(names))
query = st.text_area("SQL query", f"SELECT * FROM {view} LIMIT 100", height=140)
if st.button("Run", type="primary") and query.strip():
    try:
        res = sql.run(con, query)
        st.success(f"{len(res):,} rows")
        st.dataframe(res, use_container_width=True, height=420)
    except Exception as e:
        st.error(str(e))
