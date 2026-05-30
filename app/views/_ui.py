"""Small shared UI helpers."""

from __future__ import annotations

import html


def highlight(text: str, start: int, end: int) -> str:
    """HTML for ``text`` with the ``[start:end]`` span highlighted."""
    pre, mid, post = text[:start], text[start:end], text[end:]
    return (
        "<div style='white-space:pre-wrap;font-family:ui-monospace,monospace;"
        "font-size:0.85rem;line-height:1.5'>"
        f"{html.escape(pre)}"
        f"<mark style='background:#ffe08a'>{html.escape(mid)}</mark>"
        f"{html.escape(post)}</div>"
    )


def entity_html(text: str, ents) -> str:
    """Render a note with NICU entities underlined/tagged."""
    if not ents:
        return f"<div style='line-height:1.7'>{html.escape(text)}</div>"
    spans = sorted(ents, key=lambda e: e["start"])
    out, cur = [], 0
    for s in spans:
        st, en = int(s["start"]), int(s["end"])
        if st < cur:
            continue
        out.append(html.escape(text[cur:st]))
        out.append(
            "<span style='background:#cfe7ff;border-radius:3px;padding:0 3px' "
            f"title='{html.escape(s['canonical'])}'>{html.escape(text[st:en])}"
            f"<sup style='color:#1a4d80;font-size:0.7em'> {html.escape(s['canonical'])}</sup>"
            "</span>"
        )
        cur = en
    out.append(html.escape(text[cur:]))
    return f"<div style='line-height:1.8'>{''.join(out)}</div>"


def need_con(con) -> bool:
    import streamlit as st
    if con is None:
        st.error("DuckDB not found. Run `python scripts/build_index.py` first.")
        return False
    return True
