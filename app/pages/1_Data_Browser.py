import streamlit as st

from robocop import SITES, sql, ui

ui.setup("Data Browser", "🗄️")
ui.sidebar_brand()


@st.cache_resource(show_spinner="Registering tables…")
def load(site: str):
    con = sql.connect()
    views = sql.register_site(con, site)
    return con, views


site = st.sidebar.selectbox("Site", SITES)
con, views = load(site)

ui.header(
    "Data Browser & SQL",
    subtitle=f"DuckDB over structured CSVs · {site} NICU",
    badges=["De-identified", "DuckDB", f"Site: {site}"],
)

if not views:
    st.warning("No structured tables found for this site.")
    st.stop()

names = sorted(views)
st.sidebar.markdown(f"**{len(names)}** tables")
view = st.sidebar.radio("Tables", names)

schema = sql.table_schema(con, view)
ui.kpis([
    ("Tables", len(names), f"{site} structured"),
    ("Selected", view, "current table"),
    ("Columns", len(schema), "in selected table"),
])

ui.section("Table", view)
st.caption(views[view])
with st.expander("Schema"):
    st.dataframe(schema, use_container_width=True)
st.dataframe(sql.table_preview(con, view), use_container_width=True, height=340)

st.divider()
ui.section("SQL console", "Query the structured tables")
st.caption("Available tables: " + ", ".join(names))
query = st.text_area("Query", f"SELECT * FROM {view} LIMIT 100", height=140,
                     label_visibility="collapsed")
if st.button("Run query", type="primary") and query.strip():
    try:
        res = sql.run(con, query)
        st.success(f"{len(res):,} rows")
        st.dataframe(res, use_container_width=True, height=440)
    except Exception as e:
        st.error(str(e))
