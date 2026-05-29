"""Shared UI kit for the NICU Clinical Workspace Streamlit app.

A small, dependency-free design layer so the pages look like a professional,
provider-facing clinical tool rather than raw Streamlit. Everything here is
presentation only — no data access — so it stays cheap to import and safe to
call on every rerun.

Usage in a page::

    from robocop import ui
    ui.setup("Data Browser", "🗄️")        # page config + global styles
    ui.sidebar_brand()                      # branded sidebar header
    ui.header("Data Browser & SQL",
              subtitle="CAIDF de-identified data · MU",
              badges=["De-identified", "Cohort: NICU"])
    ui.kpis([("Tables", 12, "structured"), ("Notes", "48,210", "text not loaded")])
"""

from __future__ import annotations

import html

import streamlit as st

# --- palette ------------------------------------------------------------------
PRIMARY = "#0E7490"        # teal-700
PRIMARY_DARK = "#155E75"   # teal-800

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root{
  --rc-primary:#0E7490; --rc-primary-dark:#155E75; --rc-primary-50:#ECFEFF;
  --rc-text:#0F172A; --rc-muted:#64748B; --rc-border:#E2E8F0;
  --rc-surface:#FFFFFF; --rc-canvas:#F8FAFC;
}
.stApp{ background:var(--rc-canvas); }
html, body, .stApp, [data-testid="stMarkdownContainer"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
}
.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:1320px; }

/* strip Streamlit chrome for a product feel */
[data-testid="stDecoration"], #MainMenu, footer{ display:none !important; }
header[data-testid="stHeader"]{ background:transparent; }

/* ---- branded app header ---- */
.rc-header{ display:flex; align-items:center; justify-content:space-between;
  gap:16px; flex-wrap:wrap;
  background:linear-gradient(120deg,#0E7490 0%,#155E75 100%); color:#fff;
  padding:18px 24px; border-radius:16px; margin-bottom:22px;
  box-shadow:0 8px 24px rgba(14,116,144,.20); }
.rc-h-left{ display:flex; align-items:center; gap:16px; }
.rc-logo{ width:46px; height:46px; border-radius:12px; background:rgba(255,255,255,.16);
  display:flex; align-items:center; justify-content:center; font-size:24px; }
.rc-title{ font-size:22px; font-weight:700; line-height:1.15; }
.rc-subtitle{ font-size:13px; opacity:.85; margin-top:3px; }
.rc-pills{ display:flex; gap:8px; flex-wrap:wrap; }
.rc-pill{ background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.28);
  padding:5px 12px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; }

/* ---- KPI cards ---- */
.rc-kpis{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:14px; margin:4px 0 22px; }
.rc-kpi{ background:var(--rc-surface); border:1px solid var(--rc-border);
  border-top:3px solid var(--rc-primary); border-radius:14px; padding:16px 18px;
  box-shadow:0 1px 2px rgba(15,23,42,.04); }
.rc-kpi-label{ font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--rc-muted); font-weight:700; }
.rc-kpi-value{ font-size:26px; font-weight:700; color:var(--rc-text); margin-top:4px; }
.rc-kpi-sub{ font-size:12px; color:var(--rc-muted); margin-top:2px; }

/* ---- section headings ---- */
.rc-section{ margin:14px 0 10px; }
.rc-kicker{ font-size:11px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--rc-primary); font-weight:700; }
.rc-section-title{ font-size:18px; font-weight:700; color:var(--rc-text); margin:2px 0 0; }

/* ---- info / nav cards ---- */
.rc-cards{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }
.rc-card{ background:var(--rc-surface); border:1px solid var(--rc-border);
  border-radius:14px; padding:18px 20px; }
.rc-card .rc-ico{ font-size:22px; }
.rc-card h4{ margin:8px 0 6px; font-size:16px; color:var(--rc-text); }
.rc-card p{ margin:0; font-size:13px; color:var(--rc-muted); line-height:1.55; }

/* ---- clinical note reading pane ---- */
.rc-note{ background:var(--rc-surface); border:1px solid var(--rc-border);
  border-radius:14px; overflow:hidden; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.rc-note-head{ display:flex; gap:8px; flex-wrap:wrap; padding:12px 16px;
  border-bottom:1px solid var(--rc-border); background:#F8FAFC; }
.rc-tag{ font-size:12px; font-weight:600; color:var(--rc-primary-dark);
  background:var(--rc-primary-50); border:1px solid #CFFAFE;
  padding:4px 10px; border-radius:999px; }
.rc-note-body{ padding:18px 22px; white-space:pre-wrap; font-size:14px;
  line-height:1.65; color:#1E293B; max-height:600px; overflow:auto; }

/* ---- widget polish ---- */
.stButton>button[kind="primary"]{ background:var(--rc-primary); border:none;
  border-radius:10px; font-weight:600; }
.stButton>button[kind="primary"]:hover{ background:var(--rc-primary-dark); }
[data-testid="stSidebar"]{ border-right:1px solid var(--rc-border); }
[data-testid="stDataFrame"]{ border:1px solid var(--rc-border); border-radius:12px; }
.stTextArea textarea, .stTextInput input{ border-radius:10px; }

/* ---- sidebar brand ---- */
.rc-sb-brand{ display:flex; align-items:center; gap:11px; padding:4px 2px 14px;
  border-bottom:1px solid var(--rc-border); margin-bottom:12px; }
.rc-sb-logo{ width:36px; height:36px; border-radius:10px; background:var(--rc-primary);
  color:#fff; display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:18px; }
.rc-sb-name{ font-weight:700; color:var(--rc-text); font-size:15px; line-height:1.1; }
.rc-sb-tag{ font-size:11px; color:var(--rc-muted); }
</style>
"""


def setup(page_title: str, page_icon: str = "🩺", layout: str = "wide") -> None:
    """Set page config and inject the global stylesheet. Call first on a page."""
    st.set_page_config(page_title=f"{page_title} · NICU Workspace",
                       page_icon=page_icon, layout=layout)
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand(name: str = "robocop", tag: str = "NICU Clinical Workspace") -> None:
    """Render the branded product mark at the top of the sidebar."""
    st.sidebar.markdown(
        f"""<div class="rc-sb-brand">
          <div class="rc-sb-logo">✚</div>
          <div><div class="rc-sb-name">{html.escape(name)}</div>
          <div class="rc-sb-tag">{html.escape(tag)}</div></div>
        </div>""",
        unsafe_allow_html=True,
    )


def header(title: str, subtitle: str = "", badges: list[str] | None = None,
           icon: str = "🩺") -> None:
    """Render the branded gradient app header."""
    pills = "".join(f'<span class="rc-pill">{html.escape(str(b))}</span>'
                    for b in (badges or []))
    sub = f'<div class="rc-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""<div class="rc-header">
          <div class="rc-h-left">
            <div class="rc-logo">{icon}</div>
            <div><div class="rc-title">{html.escape(title)}</div>{sub}</div>
          </div>
          <div class="rc-pills">{pills}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def kpis(items: list[tuple]) -> None:
    """Render a row of KPI cards. Each item is ``(label, value, sub="")``."""
    cards = ""
    for it in items:
        label, value = it[0], it[1]
        sub = it[2] if len(it) > 2 else ""
        cards += (
            f'<div class="rc-kpi"><div class="rc-kpi-label">{html.escape(str(label))}</div>'
            f'<div class="rc-kpi-value">{html.escape(str(value))}</div>'
            f'<div class="rc-kpi-sub">{html.escape(str(sub))}</div></div>'
        )
    st.markdown(f'<div class="rc-kpis">{cards}</div>', unsafe_allow_html=True)


def section(kicker: str, title: str = "") -> None:
    """Render a section heading: a small colored kicker over a title."""
    t = f'<div class="rc-section-title">{html.escape(title)}</div>' if title else ""
    st.markdown(
        f'<div class="rc-section"><span class="rc-kicker">{html.escape(kicker)}</span>{t}</div>',
        unsafe_allow_html=True,
    )


def nav_cards(items: list[tuple]) -> None:
    """Render descriptive cards. Each item is ``(icon, title, description)``."""
    cards = ""
    for icon, title, desc in items:
        cards += (
            f'<div class="rc-card"><div class="rc-ico">{icon}</div>'
            f'<h4>{html.escape(title)}</h4><p>{html.escape(desc)}</p></div>'
        )
    st.markdown(f'<div class="rc-cards">{cards}</div>', unsafe_allow_html=True)


def note_pane(text: str, tags: list[str] | None = None) -> None:
    """Render a clinical note in a styled, scrollable reading pane."""
    head = ""
    if tags:
        chips = "".join(f'<span class="rc-tag">{html.escape(str(t))}</span>' for t in tags)
        head = f'<div class="rc-note-head">{chips}</div>'
    body = html.escape(text or "(empty note)")
    st.markdown(
        f'<div class="rc-note">{head}<div class="rc-note-body">{body}</div></div>',
        unsafe_allow_html=True,
    )
