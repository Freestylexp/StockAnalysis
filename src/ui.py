"""Shared UI theme and mobile-friendly components."""

from __future__ import annotations

from typing import Any

import streamlit as st

# Professional finance theme — deep navy + blue accent
THEME = {
    "primary": "#0B3D6E",
    "primary_light": "#1565C0",
    "accent": "#1E88E5",
    "surface": "#FFFFFF",
    "bg": "#F0F4F8",
    "text": "#1A2332",
    "muted": "#64748B",
    "profit": "#0F766E",
    "loss": "#DC2626",
    "border": "#E2E8F0",
    "gold": "#B8860B",
}

THEME_CSS = f"""
<style>
:root {{
  --pf-primary: {THEME["primary"]};
  --pf-accent: {THEME["accent"]};
  --pf-bg: {THEME["bg"]};
  --pf-profit: {THEME["profit"]};
  --pf-loss: {THEME["loss"]};
}}

.block-container {{
  padding-top: 1rem;
  padding-bottom: 2rem;
  max-width: 1100px;
}}

header[data-testid="stHeader"] {{
  background: linear-gradient(90deg, {THEME["primary"]} 0%, {THEME["primary_light"]} 100%);
}}

section[data-testid="stSidebar"] > div {{
  background: #FAFBFC;
  border-right: 1px solid {THEME["border"]};
}}

section[data-testid="stSidebar"] .stRadio label {{
  padding: 0.45rem 0.65rem;
  border-radius: 8px;
}}

.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, {THEME["primary"]} 0%, {THEME["accent"]} 100%);
  border: none;
  font-weight: 600;
}}

.stButton > button {{
  border-radius: 8px;
  min-height: 2.5rem;
}}

div[data-testid="stMetric"] {{
  background: {THEME["surface"]};
  border: 1px solid {THEME["border"]};
  border-radius: 12px;
  padding: 0.75rem 1rem;
  box-shadow: 0 1px 3px rgba(11, 61, 110, 0.06);
}}

.pf-hero {{
  background: linear-gradient(135deg, {THEME["primary"]} 0%, {THEME["primary_light"]} 100%);
  color: #fff;
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 8px 24px rgba(11, 61, 110, 0.18);
}}

.pf-hero h1 {{
  margin: 0;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}}

.pf-hero p {{
  margin: 0.35rem 0 0;
  opacity: 0.9;
  font-size: 0.92rem;
}}

.pf-badge {{
  display: inline-block;
  background: rgba(255,255,255,0.16);
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 999px;
  padding: 0.2rem 0.65rem;
  font-size: 0.75rem;
  margin-top: 0.6rem;
}}

.pf-section-title {{
  color: {THEME["primary"]};
  font-size: 1.05rem;
  font-weight: 700;
  margin: 1.25rem 0 0.75rem;
  padding-left: 0.65rem;
  border-left: 4px solid {THEME["accent"]};
}}

.pf-card {{
  background: {THEME["surface"]};
  border: 1px solid {THEME["border"]};
  border-radius: 14px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}}

.pf-card-head {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}}

.pf-name {{
  font-size: 1.05rem;
  font-weight: 700;
  color: {THEME["text"]};
}}

.pf-code {{
  font-size: 0.78rem;
  color: {THEME["muted"]};
  background: {THEME["bg"]};
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  white-space: nowrap;
}}

.pf-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.55rem;
}}

.pf-cell-label {{
  font-size: 0.72rem;
  color: {THEME["muted"]};
  margin-bottom: 0.1rem;
}}

.pf-cell-value {{
  font-size: 0.92rem;
  font-weight: 600;
  color: {THEME["text"]};
}}

.pf-profit {{ color: {THEME["profit"]}; }}
.pf-loss {{ color: {THEME["loss"]}; }}

.pf-metric-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-bottom: 1rem;
}}

.pf-metric-card {{
  background: {THEME["surface"]};
  border: 1px solid {THEME["border"]};
  border-radius: 12px;
  padding: 0.85rem 1rem;
  box-shadow: 0 1px 3px rgba(11, 61, 110, 0.06);
}}

.pf-metric-label {{
  font-size: 0.78rem;
  color: {THEME["muted"]};
}}

.pf-metric-value {{
  font-size: 1.35rem;
  font-weight: 700;
  color: {THEME["primary"]};
  margin-top: 0.15rem;
}}

.pf-metric-delta {{
  font-size: 0.78rem;
  margin-top: 0.15rem;
}}

.pf-disclaimer {{
  font-size: 0.75rem;
  color: {THEME["muted"]};
  text-align: center;
  padding: 0.75rem;
  border-top: 1px solid {THEME["border"]};
  margin-top: 1.5rem;
}}

@media (max-width: 768px) {{
  .block-container {{
    padding-left: 0.85rem;
    padding-right: 0.85rem;
  }}

  .pf-hero h1 {{ font-size: 1.2rem; }}
  .pf-metric-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .pf-grid {{ grid-template-columns: repeat(2, 1fr); }}

  div[data-testid="column"] {{
    min-width: unset !important;
  }}

  .stButton > button {{
    width: 100%;
    min-height: 2.75rem;
  }}

  div[data-testid="stExpander"] details summary {{
    font-size: 0.92rem;
  }}

  iframe[title="streamlit_plotly_events.plotly_chart"] {{
    min-height: 320px;
  }}
}}

@media (max-width: 480px) {{
  .pf-metric-grid {{ grid-template-columns: 1fr 1fr; }}
  .pf-grid {{ grid-template-columns: 1fr 1fr; }}
}}
</style>
"""


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", badge: str = "") -> None:
    badge_html = f'<span class="pf-badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="pf-hero">
          <h1>{title}</h1>
          <p>{subtitle}</p>
          {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(text: str) -> None:
    st.markdown(f'<div class="pf-section-title">{text}</div>', unsafe_allow_html=True)


def render_metric_grid(items: list[tuple[str, str, str | None]]) -> None:
    """Render responsive metrics using native Streamlit widgets."""
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        with col:
            if delta:
                st.metric(label, value, delta)
            else:
                st.metric(label, value)


def _pnl_class(text: str) -> str:
    if text.startswith("+") or "+%" in text:
        return "pf-profit"
    if text.startswith("-") or "-%" in text:
        return "pf-loss"
    return ""


def render_holdings_cards(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        with st.container(border=True):
            head1, head2 = st.columns([3, 1])
            head1.markdown(f"**{row.get('名称', '')}** · `{row.get('代码', '')}`")
            head2.markdown(f"**{row.get('浮动盈亏', '—')}**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("持仓", row.get("持仓", "—"))
            c2.metric("成本", row.get("成本", "—"))
            c3.metric("现价", row.get("现价", "—"))
            c4.metric("涨跌幅", row.get("涨跌幅", "—"))


def render_watchlist_cards(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        with st.container(border=True):
            head1, head2 = st.columns([3, 1])
            head1.markdown(f"**{row.get('名称', '')}** · `{row.get('代码', '')}`")
            head2.caption(row.get("添加日期", ""))
            c1, c2 = st.columns(2)
            c1.metric("现价", row.get("现价", "—"))
            c2.metric("涨跌幅", row.get("涨跌幅", "—"))


def sidebar_brand() -> None:
    st.markdown(
        f"""
        <div style="
          background: linear-gradient(135deg, {THEME['primary']} 0%, {THEME['primary_light']} 100%);
          color: white;
          padding: 0.85rem 1rem;
          border-radius: 12px;
          margin-bottom: 0.5rem;
        ">
          <div style="font-size:1.05rem;font-weight:700;">📈 持仓分析</div>
          <div style="font-size:0.78rem;opacity:0.88;margin-top:0.2rem;">A股 · 盈利导向</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
