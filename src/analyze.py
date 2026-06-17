"""Stock analysis and report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .market import (
    compute_indicators,
    discover_hot_stocks,
    fetch_history,
    fetch_realtime_quotes,
    get_stock_name,
    normalize_code,
)
from .models import Holding, Portfolio, WatchItem
from .storage import load_portfolio


def _signal_from_indicators(ind: dict[str, Any], holding: bool = False) -> tuple[str, str, list[str]]:
    """Generate action signal and reasoning from indicators."""
    reasons: list[str] = []
    score = 0  # positive = bullish, negative = bearish

    price = ind.get("price", 0)
    ma5, ma10, ma20 = ind.get("ma5"), ind.get("ma10"), ind.get("ma20")
    rsi = ind.get("rsi", 50)
    vol_ratio = ind.get("volume_ratio", 1)
    change_5d = ind.get("change_5d", 0)
    change_20d = ind.get("change_20d", 0)

    # MA trend
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            score += 2
            reasons.append("均线多头排列（MA5 > MA10 > MA20），趋势向上")
        elif ma5 < ma10 < ma20:
            score -= 2
            reasons.append("均线空头排列，趋势偏弱")
        elif price > ma20:
            score += 1
            reasons.append(f"股价站上 MA20（{ma20:.2f}），中期支撑有效")
        else:
            score -= 1
            reasons.append(f"股价跌破 MA20（{ma20:.2f}），中期承压")

    # RSI
    if rsi > 75:
        score -= 2
        reasons.append(f"RSI={rsi:.1f}，超买区域，注意回调风险")
    elif rsi < 25:
        score += 2
        reasons.append(f"RSI={rsi:.1f}，超卖区域，可能存在反弹机会")
    elif 40 <= rsi <= 60:
        reasons.append(f"RSI={rsi:.1f}，处于中性区间")

    # Volume
    if vol_ratio > 1.5:
        if change_5d > 0:
            score += 1
            reasons.append(f"放量上涨（量比 {vol_ratio:.1f}），资金关注度提升")
        else:
            score -= 1
            reasons.append(f"放量下跌（量比 {vol_ratio:.1f}），抛压较重")

    # Momentum
    if change_20d > 15:
        score -= 1
        reasons.append(f"近20日涨幅 {change_20d:.1f}%，短期涨幅较大，注意获利回吐")
    elif change_20d < -15:
        score += 1
        reasons.append(f"近20日跌幅 {change_20d:.1f}%，超跌后或有修复空间")

    # Determine action
    if holding:
        if score >= 2:
            action = "持有 / 可考虑加仓"
            strategy = "趋势良好，可继续持有；若回调至 MA20 附近可分批加仓，止损设于 MA60 下方"
        elif score <= -2:
            action = "减仓 / 观望"
            strategy = "趋势转弱，建议减仓至半仓以下；若跌破关键支撑位考虑清仓止损"
        else:
            action = "持有观望"
            strategy = "信号中性，维持现有仓位，等待趋势明朗后再做操作"
    else:
        if score >= 2:
            action = "关注 / 可考虑买入"
            strategy = "技术面偏多，可列入买入计划；建议分批建仓，首次不超过计划仓位的 30%，止损 -8%"
        elif score <= -2:
            action = "暂不介入"
            strategy = "技术面偏弱，暂不建议买入，继续观察等待更好入场点"
        else:
            action = "继续观察"
            strategy = "信号不明确，保持关注，等待放量突破或回调企稳信号"

    return action, strategy, reasons


def analyze_stock(code: str, name: str = "", holding: bool = False, cost_price: float = 0, shares: float = 0) -> dict[str, Any]:
    """Full analysis for a single stock."""
    code = normalize_code(code)
    if not name:
        name = get_stock_name(code) or code

    quotes = fetch_realtime_quotes([code])
    quote = quotes.get(code, {})
    hist = fetch_history(code)
    ind = compute_indicators(hist)

    action, strategy, reasons = _signal_from_indicators(ind, holding=holding)

    pnl_pct = None
    pnl_amount = None
    if holding and cost_price > 0 and quote.get("price"):
        pnl_pct = (quote["price"] / cost_price - 1) * 100
        pnl_amount = (quote["price"] - cost_price) * shares
        if pnl_pct > 20:
            reasons.append(f"持仓浮盈 {pnl_pct:.1f}%，可考虑部分止盈锁定利润")
        elif pnl_pct < -10:
            reasons.append(f"持仓浮亏 {pnl_pct:.1f}%，注意止损纪律")

    return {
        "code": code,
        "name": name or quote.get("name", code),
        "quote": quote,
        "indicators": ind,
        "action": action,
        "strategy": strategy,
        "reasons": reasons,
        "pnl_pct": pnl_pct,
        "pnl_amount": pnl_amount,
        "shares": shares,
        "cost_price": cost_price,
    }


def generate_report(portfolio: Portfolio | None = None) -> str:
    """Generate full daily analysis report in Markdown."""
    portfolio = portfolio or load_portfolio()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        f"# A股每日投资分析报告",
        f"",
        f"**生成时间**: {today}",
        f"",
        f"> 免责声明：本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。",
        f"",
    ]

    # --- Holdings ---
    lines += ["## 一、持仓分析", ""]
    if not portfolio.holdings:
        lines.append("*暂无持仓，使用 `python -m src.cli add-holding` 添加*")
        lines.append("")
    else:
        for h in portfolio.holdings:
            result = analyze_stock(h.code, h.name, holding=True, cost_price=h.cost_price, shares=h.shares)
            lines += _format_stock_section(result, is_holding=True)

    # --- Watchlist ---
    lines += ["## 二、关注股分析", ""]
    if not portfolio.watchlist:
        lines.append("*暂无关注股，使用 `python -m src.cli add-watch` 添加*")
        lines.append("")
    else:
        for w in portfolio.watchlist:
            result = analyze_stock(w.code, w.name, holding=False)
            lines += _format_stock_section(result, is_holding=False)

    # --- New recommendations ---
    max_rec = portfolio.settings.get("max_new_recommendations", 5)
    lines += ["## 三、今日新股推荐", ""]
    hot = discover_hot_stocks(limit=max_rec + 5)

    existing_codes = {normalize_code(h.code) for h in portfolio.holdings}
    existing_codes |= {normalize_code(w.code) for w in portfolio.watchlist}

    rec_count = 0
    for stock in hot:
        if stock["code"] in existing_codes:
            continue
        result = analyze_stock(stock["code"], stock["name"], holding=False)
        if "买入" in result["action"] or "关注" in result["action"]:
            lines += _format_stock_section(result, is_holding=False, is_recommendation=True)
            rec_count += 1
        if rec_count >= max_rec:
            break

    if rec_count == 0:
        lines.append("*今日暂无符合条件的新股推荐*")
        lines.append("")

    # --- Summary ---
    lines += [
        "## 四、操作建议汇总",
        "",
        "| 股票 | 代码 | 操作建议 |",
        "|------|------|----------|",
    ]

    for h in portfolio.holdings:
        result = analyze_stock(h.code, h.name, holding=True, cost_price=h.cost_price, shares=h.shares)
        lines.append(f"| {result['name']} | {result['code']} | {result['action']} |")

    for w in portfolio.watchlist:
        result = analyze_stock(w.code, w.name, holding=False)
        lines.append(f"| {result['name']} | {result['code']} | {result['action']} |")

    lines += ["", "---", "*报告由 stock-portfolio-agent 自动生成*"]
    return "\n".join(lines)


def _format_stock_section(result: dict[str, Any], is_holding: bool = False, is_recommendation: bool = False) -> list[str]:
    """Format a single stock analysis section."""
    quote = result.get("quote", {})
    ind = result.get("indicators", {})
    lines = []

    title = result["name"]
    if is_recommendation:
        title = f"⭐ {title}"
    lines.append(f"### {title}（{result['code']}）")
    lines.append("")

    if quote:
        lines.append(f"- **最新价**: {quote.get('price', 'N/A')} 元")
        lines.append(f"- **涨跌幅**: {quote.get('change_pct', 0):.2f}%")
        if quote.get("turnover_rate"):
            lines.append(f"- **换手率**: {quote['turnover_rate']:.2f}%")
        if quote.get("pe"):
            lines.append(f"- **市盈率**: {quote['pe']:.1f}")

    if is_holding and result.get("cost_price"):
        lines.append(f"- **持仓**: {result.get('shares', 0)} 股，成本 {result['cost_price']:.2f} 元")
        if result.get("pnl_pct") is not None:
            sign = "+" if result["pnl_pct"] >= 0 else ""
            lines.append(f"- **浮动盈亏**: {sign}{result['pnl_pct']:.2f}%（{sign}{result.get('pnl_amount', 0):.2f} 元）")

    if ind:
        ma_parts = [f"MA5={ind.get('ma5', 0):.2f}", f"MA20={ind.get('ma20', 0):.2f}"]
        if ind.get("ma60"):
            ma_parts.append(f"MA60={ind['ma60']:.2f}")
        lines.append(f"- **技术指标**: {', '.join(ma_parts)}, RSI={ind.get('rsi', 0):.1f}")

    lines.append(f"- **操作建议**: **{result['action']}**")
    lines.append(f"- **持仓策略**: {result['strategy']}")

    if result.get("reasons"):
        lines.append("- **分析理由**:")
        for r in result["reasons"]:
            lines.append(f"  - {r}")

    lines.append("")
    return lines


def save_report(report: str, output_dir: str | Path | None = None) -> Path:
    """Save report to file."""
    output_dir = Path(output_dir or "reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y-%m-%d')}.md"
    path = output_dir / filename
    path.write_text(report, encoding="utf-8")
    return path
