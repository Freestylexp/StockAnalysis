"""Price charts for A-share stocks."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .market import fetch_history, normalize_code


def prepare_chart_data(code: str, days: int = 120) -> pd.DataFrame:
    """Return OHLCV dataframe with MA columns for charting."""
    code = normalize_code(code)
    df = fetch_history(code, days=days)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["日期"] = pd.to_datetime(df["日期"])
    close = pd.to_numeric(df["收盘"], errors="coerce")
    df["MA5"] = close.rolling(5).mean()
    df["MA10"] = close.rolling(10).mean()
    df["MA20"] = close.rolling(20).mean()
    if len(close) >= 60:
        df["MA60"] = close.rolling(60).mean()
    df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
    return df


def build_price_chart(
    code: str,
    name: str = "",
    days: int = 120,
    price_plan: dict[str, Any] | None = None,
) -> go.Figure | None:
    """Build interactive candlestick + volume chart with optional price lines."""
    df = prepare_chart_data(code, days)
    if df.empty:
        return None

    title = f"{name or code}（{code}）价格走势"
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.06, row_heights=[0.72, 0.28],
        subplot_titles=(title, "成交量"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df["日期"],
            open=df["开盘"], high=df["最高"], low=df["最低"], close=df["收盘"],
            name="K线",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
        ),
        row=1, col=1,
    )

    for col, color, label in [
        ("MA5", "#ff9800", "MA5"),
        ("MA10", "#2196f3", "MA10"),
        ("MA20", "#9c27b0", "MA20"),
        ("MA60", "#607d8b", "MA60"),
    ]:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df["日期"], y=df[col], name=label, line=dict(width=1.2, color=color)),
                row=1, col=1,
            )

    if price_plan:
        _add_price_lines(fig, price_plan)

    colors = ["#ef5350" if c >= o else "#26a69a" for c, o in zip(df["收盘"], df["开盘"])]
    fig.add_trace(
        go.Bar(x=df["日期"], y=df["成交量"], name="成交量", marker_color=colors, opacity=0.6),
        row=2, col=1,
    )

    fig.update_layout(
        height=480,
        autosize=True,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
        margin=dict(l=36, r=12, t=50, b=24),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FAFBFC",
        font=dict(family="sans-serif", size=11, color="#1A2332"),
    )
    fig.update_xaxes(type="category", row=2, col=1)
    return fig


def _add_price_lines(fig: go.Figure, plan: dict[str, Any]) -> None:
    styles = [
        ("add_low", "加仓下限", "#4caf50", "dash"),
        ("add_high", "加仓上限", "#4caf50", "dash"),
        ("take_profit", "止盈目标", "#e91e63", "dot"),
        ("stop_loss", "风控底线", "#9e9e9e", "dashdot"),
        ("rebound_add", "反弹加仓", "#ff5722", "solid"),
        ("cost_price", "持仓成本", "#795548", "solid"),
    ]
    # 绘制盈利目标线
    for i, t in enumerate(plan.get("profit_targets", [])[:3]):
        val = t.get("price")
        if val and float(val) > 0:
            fig.add_hline(
                y=float(val), line_dash="dot", line_color="#e91e63", line_width=1.2,
                annotation_text=f"{t.get('label', '目标')} {float(val):.2f}",
                annotation_position="right",
            )
    for key, label, color, dash in styles:
        val = plan.get(key)
        if val and float(val) > 0:
            fig.add_hline(
                y=float(val), line_dash=dash, line_color=color, line_width=1.5,
                annotation_text=f"{label} {float(val):.2f}",
                annotation_position="right",
            )

    for i, zone in enumerate(plan.get("add_zones", [])[:3]):
        lo, hi = zone.get("low"), zone.get("high")
        if lo and hi:
            fig.add_hrect(y0=lo, y1=hi, fillcolor="rgba(76,175,80,0.12)", line_width=0)
