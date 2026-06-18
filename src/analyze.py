"""Stock analysis and report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .market import (
    compute_indicators,
    fetch_history,
    fetch_realtime_quotes,
    get_stock_name,
    normalize_code,
)
from .models import Holding, Portfolio, WatchItem
from .recommend import compute_price_plan, discover_buy_candidates
from .storage import load_portfolio


def _signal_from_indicators(
    ind: dict[str, Any],
    holding: bool = False,
    cost_price: float = 0,
    pnl_pct: float | None = None,
) -> tuple[str, str, list[str]]:
    """Generate profit-oriented action signal."""
    reasons: list[str] = []
    score = 0

    price = ind.get("price", 0)
    ma5, ma10, ma20 = ind.get("ma5"), ind.get("ma10"), ind.get("ma20")
    high_20 = ind.get("high_20d", 0)
    rsi = ind.get("rsi", 50)
    vol_ratio = ind.get("volume_ratio", 1)
    change_5d = ind.get("change_5d", 0)
    change_20d = ind.get("change_20d", 0)

    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            score += 3
            reasons.append("均线多头排列，主升趋势，以持有/加仓扩大盈利为主")
        elif ma5 < ma10 < ma20:
            score -= 2
            reasons.append("均线空头，短期难盈利，等待反转信号")
        elif price > ma20:
            score += 1
            reasons.append(f"站上 MA20（{ma20:.2f}），中期趋势支撑盈利预期")

    if vol_ratio > 1.3 and change_5d > 0:
        score += 2
        reasons.append(f"放量上涨（量比 {vol_ratio:.1f}），资金推动，盈利概率提升")

    if high_20 and price >= high_20 * 0.97:
        score += 1
        reasons.append(f"接近 20 日高点 {high_20:.2f}，突破后盈利空间打开")

    if rsi < 35 and change_20d < -10:
        score += 1
        reasons.append(f"RSI={rsi:.1f} 超卖 + 20日跌 {change_20d:.1f}%，具备反弹盈利机会")

    if change_20d > 20:
        score -= 1
        reasons.append(f"近20日涨 {change_20d:.1f}%，追高风险上升，等回调再介入")

    if holding and pnl_pct is not None:
        if pnl_pct > 15:
            action = "持有 / 分批止盈"
            strategy = (
                f"浮盈 {pnl_pct:.1f}%，趋势未破则持有；"
                f"到达成本 +8%（{cost_price * 1.08:.2f}）减 1/3，+15% 再减 1/3"
            )
        elif pnl_pct > 5:
            action = "持有待涨"
            strategy = f"浮盈 {pnl_pct:.1f}%，趋势向好，持有看第二止盈位 {cost_price * 1.15:.2f} 元"
        elif pnl_pct > -5:
            action = "持有 / 等待突破盈利"
            strategy = f"接近成本，突破 {cost_price * 1.05:.2f} 元后持有看 {cost_price * 1.12:.2f} 元止盈"
        elif pnl_pct > -15:
            action = "持有 / 反弹加仓扭亏"
            strategy = (
                f"浮亏 {pnl_pct:.1f}%，若 RSI 超卖且出现阳线，可小仓加仓摊低成本，"
                f"目标回本 {cost_price:.2f} 元后止盈 +8%"
            )
        else:
            action = "摊低成本 / 博反弹盈利"
            strategy = (
                f"深套 {pnl_pct:.1f}%，在超卖区小仓加仓摊低成本，"
                f"反弹至 {cost_price:.2f} 元回本，不割肉等待盈利机会"
            )
        if score >= 2 and pnl_pct < 10:
            action = "持有加仓 / 扩大盈利"
            reasons.append("技术面转强，回调时可加仓扩大盈利")
        return action, strategy, reasons

    # 非持仓
    if score >= 3:
        action = "买入 / 盈利机会"
        strategy = "趋势+动量俱佳，可分批建仓，目标 +8%~15%"
    elif score >= 1:
        action = "关注 / 等回调买入"
        strategy = "有盈利潜力，等回调至 MA20 附近低吸，目标 +10%"
    else:
        action = "暂不介入"
        strategy = "短期盈利概率低，等待更好入场点"

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

    # 实时行情不可用时，用历史收盘价兜底
    if not quote and ind:
        quote = {
            "code": code,
            "name": name,
            "price": ind.get("price", 0),
            "change_pct": ind.get("change_5d", 0) / 5 if ind.get("change_5d") else 0,
            "prev_close": ind.get("price", 0),
        }

    if hist.empty and not ind:
        raise RuntimeError("无法获取历史数据，请检查网络连接后重试")

    pnl_pct = None
    pnl_amount = None
    if holding and cost_price > 0 and quote.get("price"):
        pnl_pct = (quote["price"] / cost_price - 1) * 100
        pnl_amount = (quote["price"] - cost_price) * shares

    action, strategy, reasons = _signal_from_indicators(
        ind, holding=holding, cost_price=cost_price, pnl_pct=pnl_pct,
    )
    price_plan = compute_price_plan(ind, quote, cost_price=cost_price, holding=holding)

    if price_plan.get("rebound_signal") and holding and pnl_pct is not None and pnl_pct < 0:
        action = "摊低成本 / 博反弹盈利"
    elif price_plan.get("rebound_signal"):
        action = "买入 / 超卖反弹机会"

    if holding and pnl_pct is not None:
        if pnl_pct > 10:
            reasons.append(f"浮盈 {pnl_pct:.1f}%，按止盈计划分批兑现，保留底仓吃后面涨幅")
        elif pnl_pct < -8:
            reasons.append(f"浮亏 {pnl_pct:.1f}%，优先策略是摊低成本+等反弹扭亏，而非割肉")

    # Merge detailed strategy from price plan
    if price_plan.get("summary"):
        strategy = price_plan["summary"]

    return {
        "code": code,
        "name": name or quote.get("name", code),
        "quote": quote,
        "indicators": ind,
        "history": hist,
        "action": action,
        "strategy": strategy,
        "price_plan": price_plan,
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

    # --- Daily buy recommendations ---
    max_rec = portfolio.settings.get("max_new_recommendations", 5)
    lines += ["## 三、今日买入推荐", ""]
    lines.append("*基于全市场扫描：趋势、超卖反弹、均线支撑等维度，不限于新股*")
    lines.append("")

    existing_codes = {normalize_code(h.code) for h in portfolio.holdings}
    existing_codes |= {normalize_code(w.code) for w in portfolio.watchlist}

    candidates = discover_buy_candidates(exclude_codes=existing_codes, limit=max_rec)
    rec_count = 0
    for cand in candidates:
        result = analyze_stock(cand["code"], cand["name"], holding=False)
        result["reasons"] = list(dict.fromkeys(cand.get("reasons", []) + result.get("reasons", [])))
        lines += _format_stock_section(result, is_holding=False, is_recommendation=True)
        rec_count += 1

    if rec_count == 0:
        lines.append("*今日扫描暂无高置信度买入推荐，建议以持仓管理为主*")
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
    lines.append(f"- **持仓策略**:")
    for line in result["strategy"].split("\n"):
        if line.strip():
            lines.append(f"  {line.strip()}")

    plan = result.get("price_plan") or {}
    if plan.get("profit_targets"):
        lines.append("- **盈利目标价**:")
        for t in plan["profit_targets"]:
            lines.append(f"  - **{t['price']:.2f}** 元：{t['label']} — {t['action']}（{t['reason']}）")
    if plan.get("add_zones"):
        lines.append("- **加仓博盈利**:")
        for z in plan["add_zones"][:4]:
            lines.append(f"  - {z['label']}：**{z['low']:.2f} – {z['high']:.2f}** 元 — {z['reason']}")
    if plan.get("take_profit_targets"):
        lines.append("- **止盈卖出参考**:")
        for t in plan["take_profit_targets"][:3]:
            lines.append(f"  - **{t['price']:.2f}** 元：{t['label']} — {t['action']}")
    if plan.get("stop_loss"):
        lines.append(f"- **风控底线**：**{plan['stop_loss']:.2f}** 元（极端情况止损，非主策略）")
    for n in plan.get("notes", []):
        lines.append(f"  {n}")

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
