"""Shared UI helpers: a global stylesheet, page headers, the sidebar brand &
status panel, and small renderers (note highlighting, entity tagging).

The look targets a warm, professional light theme (see ``.streamlit/config.toml``)
with a Claude-style coral accent. Everything here is presentational; pages stay
focused on data.
"""

from __future__ import annotations

import html

import streamlit as st

# ── palette (kept in sync with .streamlit/config.toml) ──────────────────────
# Warm light theme: cream paper canvas, near-black ink, coral accent.
ACCENT = "#d97757"          # coral accent (matches primaryColor)
ACCENT_SOFT = "#a85636"     # darker coral — readable as small text on light bg
BG = "#faf9f5"              # paper canvas (matches backgroundColor)
CARD = "#f0eee6"            # cards / panels (matches secondaryBackgroundColor)
BORDER = "#dcd8cc"          # hairline borders
TEXT = "#28261d"            # warm near-black ink (matches textColor)
MUTED = "#6b6757"           # muted label text, accessible on the paper canvas


_CSS = f"""
<style>
/* ---- canvas: use the full width, tighten default padding ---------------- */
.block-container {{
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 100% !important;
}}
[data-testid="stMain"] .block-container {{ padding-left: 3rem; padding-right: 3rem; }}

/* ---- typography --------------------------------------------------------- */
html, body, [class*="css"] {{ font-feature-settings: "ss01","cv01"; }}
h1, h2, h3 {{ letter-spacing: -0.01em; font-weight: 650; }}

/* ---- branded page header ------------------------------------------------ */
.rc-header {{
    display: flex; align-items: center; gap: 0.85rem;
    padding: 0 0 0.6rem 0; margin-bottom: 1.2rem;
    border-bottom: 1px solid {BORDER};
}}
.rc-header .rc-icon {{
    font-size: 1.7rem; line-height: 1;
    width: 2.9rem; height: 2.9rem; flex: 0 0 2.9rem;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, {ACCENT}33, {ACCENT}11);
    border: 1px solid {ACCENT}55; border-radius: 0.7rem;
}}
.rc-header .rc-text {{ display: flex; flex-direction: column; gap: 0.1rem; }}
.rc-header .rc-title {{ font-size: 1.45rem; font-weight: 680; line-height: 1.15; color: {TEXT}; }}
.rc-header .rc-sub {{ font-size: 0.9rem; color: {MUTED}; line-height: 1.35; max-width: 70ch; }}

/* ---- metrics as cards --------------------------------------------------- */
[data-testid="stMetric"] {{
    background: {CARD}; border: 1px solid {BORDER};
    border-radius: 0.7rem; padding: 0.9rem 1.1rem;
}}
[data-testid="stMetricLabel"] {{ color: {MUTED}; }}
[data-testid="stMetricValue"] {{ font-weight: 670; }}

/* ---- sidebar: brand mark above the nav ---------------------------------- */
[data-testid="stSidebar"] {{ border-right: 1px solid {BORDER}; }}
[data-testid="stSidebarNav"]::before {{
    content: "R";
    display: flex; align-items: center; justify-content: center;
    width: 2.1rem; height: 2.1rem; margin: 0.2rem 1rem 0.1rem;
    font-size: 1.2rem; font-weight: 800; color: #ffffff;
    background: linear-gradient(135deg, {ACCENT}, {ACCENT_SOFT});
    border-radius: 0.55rem; letter-spacing: 0;
}}
[data-testid="stSidebarNav"]::after {{
    content: "NICU Patient Intelligence";
    display: block; font-size: 0.72rem; color: {MUTED};
    padding: 0 1rem 0.6rem; text-transform: uppercase; letter-spacing: 0.06em;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {ACCENT}22; border-radius: 0.5rem;
}}

/* ---- status pills in the sidebar ---------------------------------------- */
.rc-status {{ display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; font-size: 0.85rem; }}
.rc-dot {{ width: 0.55rem; height: 0.55rem; border-radius: 50%; flex: 0 0 auto; }}
.rc-dot.ok {{ background: #5fb87a; box-shadow: 0 0 0 3px #5fb87a22; }}
.rc-dot.off {{ background: #c25b52; box-shadow: 0 0 0 3px #c25b5222; }}
.rc-status .rc-k {{ color: {MUTED}; }}
.rc-status .rc-v {{ color: {TEXT}; margin-left: auto; font-variant-numeric: tabular-nums; }}

/* ---- tabs, buttons, tables --------------------------------------------- */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.25rem; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 0.5rem 0.5rem 0 0; }}
.stButton button, .stDownloadButton button {{ font-weight: 600; border-radius: 0.55rem; }}
[data-testid="stDataFrame"] {{ border-radius: 0.6rem; overflow: hidden; }}

/* ---- callout used for unavailable / heads-up states --------------------- */
.rc-note {{
    background: {CARD}; border: 1px solid {BORDER}; border-left: 3px solid {ACCENT};
    border-radius: 0.55rem; padding: 0.9rem 1.1rem; margin: 0.4rem 0 1rem;
    color: {TEXT}; font-size: 0.9rem; line-height: 1.5;
}}
.rc-note code {{ background: {BG}; padding: 0.05rem 0.35rem; border-radius: 0.3rem; }}
</style>
"""


def inject_css() -> None:
    """Inject the global stylesheet. Call once per script run, early."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """A consistent branded header for every page."""
    icon_html = f"<div class='rc-icon'>{html.escape(icon)}</div>" if icon else ""
    st.markdown(
        f"<div class='rc-header'>{icon_html}"
        f"<div class='rc-text'><div class='rc-title'>{html.escape(title)}</div>"
        f"<div class='rc-sub'>{html.escape(subtitle)}</div></div></div>",
        unsafe_allow_html=True,
    )


def callout(body_md: str) -> None:
    """A styled heads-up box for unavailable features (nicer than st.warning).

    ``body_md`` may contain inline ``code`` spans which are rendered verbatim.
    """
    st.markdown(f"<div class='rc-note'>{body_md}</div>", unsafe_allow_html=True)


def status_row(label: str, ok: bool, value: str = "") -> None:
    dot = "ok" if ok else "off"
    st.markdown(
        f"<div class='rc-status'><span class='rc-dot {dot}'></span>"
        f"<span class='rc-k'>{html.escape(label)}</span>"
        f"<span class='rc-v'>{html.escape(value)}</span></div>",
        unsafe_allow_html=True,
    )


# ── note rendering ──────────────────────────────────────────────────────────
def highlight(text: str, start: int, end: int) -> str:
    """HTML for ``text`` with the ``[start:end]`` span highlighted (dark theme)."""
    pre, mid, post = text[:start], text[start:end], text[end:]
    return (
        "<div style='white-space:pre-wrap;font-family:ui-monospace,monospace;"
        f"font-size:0.85rem;line-height:1.6;color:{TEXT};background:{BG};"
        f"border:1px solid {BORDER};border-radius:0.5rem;padding:0.8rem 1rem'>"
        f"{html.escape(pre)}"
        f"<mark style='background:{ACCENT};color:#1a1916;border-radius:3px;"
        f"padding:0 3px'>{html.escape(mid)}</mark>"
        f"{html.escape(post)}</div>"
    )


def entity_html(text: str, ents) -> str:
    """Render a note with NICU entities tagged (dark theme)."""
    base = f"line-height:1.8;color:{TEXT}"
    if not ents:
        return f"<div style='{base}'>{html.escape(text)}</div>"
    spans = sorted(ents, key=lambda e: e["start"])
    out, cur = [], 0
    for s in spans:
        st_, en = int(s["start"]), int(s["end"])
        if st_ < cur:
            continue
        out.append(html.escape(text[cur:st_]))
        out.append(
            f"<span style='background:{ACCENT}33;border:1px solid {ACCENT}66;"
            "border-radius:3px;padding:0 3px' "
            f"title='{html.escape(s['canonical'])}'>{html.escape(text[st_:en])}"
            f"<sup style='color:{ACCENT_SOFT};font-size:0.7em'> "
            f"{html.escape(s['canonical'])}</sup></span>"
        )
        cur = en
    out.append(html.escape(text[cur:]))
    return f"<div style='{base}'>{''.join(out)}</div>"


def need_con(con) -> bool:
    if con is None:
        callout(
            "<b>DuckDB not found.</b> Build the local warehouse first: "
            "run <code>python scripts/build_index.py</code>."
        )
        return False
    return True
