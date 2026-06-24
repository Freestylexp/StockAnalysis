"""Portfolio floating P&L and recent-day change analysis."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .market import fetch_history, fetch_realtime_quotes, normalize_code
from .models import Holding, Portfolio

PNL_LOOKBACK_DAYS = 5
PNL_COMPARE_OFFSETS = (1, 3, 5)


def _fmt_money(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.2f}"


def _fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _close_series(hist: pd.DataFrame) -> pd.Series:
    if hist is None or hist.empty or "收盘" not in hist.columns:
        return pd.Series(dtype=float)
    df = hist.copy()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期")
    closes = pd.to_numeric(df["收盘"], errors="coerce")
    closes.index = df["日期"].values
    return closes.dropna()


def _pnl_at_price(cost: float, shares: float, price: float) -> tuple[float, float]:
    if cost <= 0 or shares <= 0 or price <= 0:
        return 0.0, 0.0
    pnl = (price - cost) * shares
    pnl_pct = (price / cost - 1) * 100
    return pnl, pnl_pct


def compute_holding_pnl_trend(
    holding: Holding,
    hist: pd.DataFrame | None = None,
    current_price: float | None = None,
) -> dict[str, Any]:
    """Compute per-holding floating P&L and recent-day changes."""
    code = normalize_code(holding.code)
    cost = float(holding.cost_price)
    shares = float(holding.shares)

    if hist is None or hist.empty:
        hist = fetch_history(code, days=40)
    closes = _close_series(hist)

    if current_price is None or current_price <= 0:
        current_price = float(closes.iloc[-1]) if not closes.empty else 0.0

    current_pnl, current_pnl_pct = _pnl_at_price(cost, shares, current_price)

    # Build daily series from historical closes; replace last bar with live price when available
    price_points: list[tuple[str, float]] = []
    if not closes.empty:
        for dt, price in closes.tail(PNL_LOOKBACK_DAYS).items():
            price_points.append((pd.Timestamp(dt).strftime("%Y-%m-%d"), float(price)))
        if price_points and current_price > 0:
            price_points[-1] = (price_points[-1][0], current_price)

    daily: list[dict[str, Any]] = []
    prev_pnl: float | None = None
    for date_str, price in price_points:
        pnl, pnl_pct = _pnl_at_price(cost, shares, price)
        pnl_delta = pnl - prev_pnl if prev_pnl is not None else 0.0
        daily.append({
            "date": date_str,
            "price": price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "pnl_delta": pnl_delta,
        })
        prev_pnl = pnl

    changes: dict[int, dict[str, float]] = {}
    if not closes.empty and cost > 0 and current_price > 0:
        for offset in PNL_COMPARE_OFFSETS:
            if len(closes) > offset:
                old_price = float(closes.iloc[-(offset + 1)])
                old_pnl, old_pnl_pct = _pnl_at_price(cost, shares, old_price)
                changes[offset] = {
                    "pnl_delta": current_pnl - old_pnl,
                    "pnl_pct_delta": current_pnl_pct - old_pnl_pct,
                    "price_delta_pct": (current_price / old_price - 1) * 100 if old_price else 0,
                }

    return {
        "code": code,
        "name": holding.name or code,
        "shares": shares,
        "cost_price": cost,
        "current_price": current_price,
        "current_pnl": current_pnl,
        "current_pnl_pct": current_pnl_pct,
        "daily": daily,
        "changes": changes,
    }


def compute_portfolio_pnl_summary(portfolio: Portfolio) -> dict[str, Any]:
    """Aggregate portfolio P&L and recent-day changes across holdings."""
    if not portfolio.holdings:
        return {
            "holdings": [],
            "daily": [],
            "changes": {},
            "total_cost": 0.0,
            "total_market_value": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
        }

    codes = [normalize_code(h.code) for h in portfolio.holdings]
    quotes = fetch_realtime_quotes(codes)

    holding_trends: list[dict[str, Any]] = []
    total_cost = 0.0
    total_market_value = 0.0

    for h in portfolio.holdings:
        code = normalize_code(h.code)
        quote = quotes.get(code, {})
        current_price = float(quote.get("price") or 0)
        trend = compute_holding_pnl_trend(h, current_price=current_price or None)
        holding_trends.append(trend)
        total_cost += h.cost_price * h.shares
        total_market_value += trend["current_price"] * h.shares

    total_pnl = total_market_value - total_cost
    total_pnl_pct = (total_market_value / total_cost - 1) * 100 if total_cost > 0 else 0.0

    daily_map: dict[str, dict[str, float]] = {}
    for trend in holding_trends:
        for row in trend["daily"]:
            key = row["date"]
            if key not in daily_map:
                daily_map[key] = {"pnl": 0.0, "pnl_delta": 0.0}
            daily_map[key]["pnl"] += row["pnl"]
            daily_map[key]["pnl_delta"] += row["pnl_delta"]

    daily = [
        {"date": d, **daily_map[d]}
        for d in sorted(daily_map.keys())
    ][-PNL_LOOKBACK_DAYS:]

    changes: dict[int, dict[str, float]] = {}
    for offset in PNL_COMPARE_OFFSETS:
        old_total_pnl = sum(
            t["current_pnl"] - t["changes"].get(offset, {}).get("pnl_delta", 0)
            for t in holding_trends
        )
        old_total_pct = (old_total_pnl / total_cost * 100) if total_cost > 0 else 0.0
        changes[offset] = {
            "pnl_delta": total_pnl - old_total_pnl,
            "pnl_pct_delta": total_pnl_pct - old_total_pct,
        }

    return {
        "holdings": holding_trends,
        "daily": daily,
        "changes": changes,
        "total_cost": total_cost,
        "total_market_value": total_market_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


def format_portfolio_pnl_section(summary: dict[str, Any]) -> list[str]:
    """Render portfolio P&L summary as Markdown lines."""
    if not summary.get("holdings"):
        return []

    lines = [
        "## 持仓盈亏概览（含近日变化）",
        "",
        f"- **组合成本**: {summary['total_cost']:,.2f} 元",
        f"- **组合市值**: {summary['total_market_value']:,.2f} 元",
        f"- **总浮动盈亏**: {_fmt_money(summary['total_pnl'])} 元（{_fmt_pct(summary['total_pnl_pct'])}）",
        "",
        "### 近几日盈亏变化（组合）",
        "",
        "| 周期 | 盈亏变化 | 说明 |",
        "|------|----------|------|",
    ]

    labels = {1: "近 1 日", 3: "近 3 日", 5: "近 5 日"}
    for offset in PNL_COMPARE_OFFSETS:
        ch = summary.get("changes", {}).get(offset, {})
        delta = ch.get("pnl_delta", 0)
        lines.append(
            f"| {labels[offset]} | {_fmt_money(delta)} 元 | "
            f"浮动盈亏较 {offset} 个交易日前 {'增加' if delta >= 0 else '减少'} |"
        )

    if summary.get("daily"):
        lines += [
            "",
            "### 近 5 个交易日浮动盈亏",
            "",
            "| 日期 | 组合浮动盈亏 | 较前日变化 |",
            "|------|--------------|------------|",
        ]
        for row in summary["daily"]:
            lines.append(
                f"| {row['date']} | {_fmt_money(row['pnl'])} 元 | {_fmt_money(row['pnl_delta'])} 元 |"
            )

    lines += [
        "",
        "### 个股近日盈亏变化",
        "",
        "| 股票 | 代码 | 现价 | 总浮动盈亏 | 近1日 | 近3日 | 近5日 |",
        "|------|------|------|------------|-------|-------|-------|",
    ]
    for t in summary["holdings"]:
        c1 = _fmt_money(t["changes"].get(1, {}).get("pnl_delta", 0))
        c3 = _fmt_money(t["changes"].get(3, {}).get("pnl_delta", 0))
        c5 = _fmt_money(t["changes"].get(5, {}).get("pnl_delta", 0))
        lines.append(
            f"| {t['name']} | {t['code']} | {t['current_price']:.2f} | "
            f"{_fmt_money(t['current_pnl'])} 元 | {c1} | {c3} | {c5} |"
        )

    lines.append("")
    return lines


def format_holding_pnl_lines(trend: dict[str, Any]) -> list[str]:
    """Render per-stock recent P&L lines for report sections."""
    if not trend or trend.get("cost_price", 0) <= 0:
        return []

    lines = ["- **近日盈亏变化**:"]
    for offset in PNL_COMPARE_OFFSETS:
        ch = trend.get("changes", {}).get(offset, {})
        delta = ch.get("pnl_delta", 0)
        price_chg = ch.get("price_delta_pct", 0)
        label = {1: "近 1 日", 3: "近 3 日", 5: "近 5 日"}[offset]
        if offset in trend.get("changes", {}):
            lines.append(
                f"  - {label}：盈亏 {_fmt_money(delta)} 元，股价 {_fmt_pct(price_chg)}"
            )
        else:
            lines.append(f"  - {label}：数据不足")

    if trend.get("daily"):
        recent = trend["daily"][-3:]
        parts = [f"{r['date']} {_fmt_money(r['pnl_delta'])}元" for r in recent]
        lines.append(f"  - 逐日较前日：{' · '.join(parts)}")

    return lines
