# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---
# %% [markdown]
# # NICU cohort — first look
#
# Run this as a notebook (`jupytext` opens `.py` percent files directly in
# Jupyter) or just `python notebooks/01_nicu_eda.py`. It does no heavy work —
# just enough to confirm the data loads and to orient you.
#
# Committed as `.py` (not `.ipynb`) so diffs are reviewable and no note text is
# ever saved into notebook output cells.

# %%
from robocop import SITES, data, notes
from robocop.config import DATA_ROOT

print("DATA_ROOT:", DATA_ROOT, "exists:", DATA_ROOT.exists())

# %% [markdown]
# ## What's on disk, per site

# %%
for site in SITES:
    inv = data.inventory(site)
    print(f"\n=== {site} ({len(inv)} files) ===")
    if len(inv):
        print(inv.to_string(index=False))

# %% [markdown]
# ## Structured tables (example: a site's demographics / encounters)
# Adjust the search term to whatever `inventory()` shows for your site.

# %%
try:
    demo = data.load("Iowa", "Demographics")
    print("Iowa demographics:", demo.shape)
    print(demo.head())
except Exception as e:
    print("load demo:", e)

# %% [markdown]
# ## Free-text notes — load and normalize

# %%
raw = data.load_notes("MU")
print("MU raw notes rows:", len(raw), "columns:", list(raw.columns))
if len(raw):
    nd = notes.normalize(raw)
    print("normalized:", nd.shape)
    print("median note length (chars):", int(nd["text"].str.len().median()))

# %% [markdown]
# ## Next steps
# - Pick a clinical question for the NICU cohort (e.g. predicting a discharge
#   outcome, summarizing care, surfacing risk from notes).
# - Combine structured tables (labs/vitals/meds) with note-derived features.
# - Use `robocop.rag` to retrieve relevant note passages and `robocop.llm` to
#   extract/summarize with a local model — then build the demo in
#   `app/streamlit_app.py`.
