"""Detailed price plan and buy candidate discovery — profit-oriented."""

from __future__ import annotations

from typing import Any

import akshare as ak
import pandas as pd

from .market import compute_indicators, fetch_history, normalize_code


def compute_price_plan(
    ind: dict[str, Any],
    quote: dict[str, Any] | None = None,
    cost_price: float = 0,
    holding: bool = False,
) -> dict[str, Any]:
    """Compute profit-focused add/take-profit/stop price levels."""
    quote = quote or {}
    price = float(ind.get("price") or quote.get("price") or 0)
    if price <= 0:
        return {}

    ma5 = ind.get("ma5")
    ma10 = ind.get("ma10")
    ma20 = ind.get("ma20")
    ma60 = ind.get("ma60")
    low_20 = ind.get("low_20d", price * 0.92)
    high_20 = ind.get("high_20d", price * 1.08)
    rsi = ind.get("rsi", 50)
    change_20d = ind.get("change_20d", 0)
    change_5d = ind.get("change_5d", 0)
    vol_ratio = ind.get("volume_ratio", 1)

    pnl_pct = ((price / cost_price - 1) * 100) if cost_price > 0 else None
    in_profit = pnl_pct is not None and pnl_pct > 0
    in_loss = pnl_pct is not None and pnl_pct < 0

    profit_targets: list[dict[str, Any]] = []
    add_zones: list[dict[str, Any]] = []
    notes: list[str] = []

    # --- 盈利目标（核心）---
    if cost_price > 0 and holding:
        profit_targets.append({
            "price": round(cost_price, 2),
            "label": "回本价",
            "action": "解套出局或换更强标的",
            "reason": "回到成本线，无盈利时可考虑调仓",
        })
        profit_targets.append({
            "price": round(cost_price * 1.08, 2),
            "label": "第一止盈 (+8%)",
            "action": "减仓 1/3 锁定利润",
            "reason": "落袋为安，保留底仓继续博更高收益",
        })
        profit_targets.append({
            "price": round(max(cost_price * 1.15, high_20 * 0.98), 2),
            "label": "第二止盈 (+15%)",
            "action": "再减 1/3",
            "reason": "已达较好盈利区间，逐步兑现",
        })
        profit_targets.append({
            "price": round(max(cost_price * 1.25, high_20), 2),
            "label": "理想卖出价 (+25%)",
            "action": "大幅减仓/清仓",
            "reason": "超额收益目标，不宜过度贪婪",
        })
    else:
        profit_targets.append({
            "price": round(high_20, 2),
            "label": "第一目标 (20日高点)",
            "action": "到达后评估是否介入或止盈",
            "reason": "短期压力位，突破则打开上行空间",
        })
        profit_targets.append({
            "price": round(high_20 * 1.08, 2),
            "label": "第二目标 (+8% 突破)",
            "action": "趋势确认后可持有",
            "reason": "突破前高后的延伸目标",
        })

    # --- 加仓博盈利 ---
    if ma5 and ma10 and ma5 > ma10 and change_5d > 0:
        add_zones.append({
            "label": "趋势延续加仓",
            "low": round(ma5 * 0.98, 2),
            "high": round(ma5 * 1.01, 2),
            "reason": "短期趋势向上，回调 MA5 附近加仓扩大盈利",
        })

    if ma20 and price >= ma20 * 0.97 and price <= ma20 * 1.03:
        add_zones.append({
            "label": "MA20 低吸加仓",
            "low": round(ma20 * 0.98, 2),
            "high": round(ma20 * 1.02, 2),
            "reason": "回踩中期均线，低成本扩大仓位",
        })

    if high_20 and price >= high_20 * 0.97 and vol_ratio > 1.2:
        add_zones.append({
            "label": "突破前高追强",
            "low": round(high_20 * 0.99, 2),
            "high": round(high_20 * 1.03, 2),
            "reason": "放量突破 20 日高点，顺势加仓博主升",
        })

    # 套牢摊低成本博反弹盈利
    near_bottom = price <= low_20 * 1.05
    oversold = rsi < 40
    deep_drop = change_20d < -10
    stabilizing = change_5d > 0 and change_20d < 0

    rebound_signal = (oversold and deep_drop and near_bottom) or (in_loss and stabilizing and oversold)
    rebound_add = round(low_20 * 1.0, 2) if rebound_signal else None

    if rebound_signal and holding and in_loss:
        add_zones.insert(0, {
            "label": "⚡ 摊低成本博反弹",
            "low": round(price * 0.97, 2),
            "high": round(price * 1.02, 2),
            "reason": f"浮亏 {pnl_pct:.1f}%，超卖区小仓加仓摊低成本，目标先回本再看 +8%",
        })
        notes.append(
            f"⚡ **盈利策略**：当前浮亏 {pnl_pct:.1f}%，RSI={rsi:.1f} 接近超卖。"
            f"可在 **{rebound_add:.2f}** 附近加仓摊低成本，反弹至 **{cost_price:.2f}** 回本，"
            f"至 **{cost_price * 1.08:.2f}** 分批止盈。"
        )
    elif rebound_signal:
        add_zones.insert(0, {
            "label": "超卖反弹建仓",
            "low": round(rebound_add * 0.98, 2),
            "high": round(rebound_add * 1.03, 2),
            "reason": "超跌反弹机会，目标 +8%~15%",
        })

    primary_add_low = add_zones[0]["low"] if add_zones else round(price * 0.97, 2)
    primary_add_high = add_zones[0]["high"] if add_zones else round(price * 1.0, 2)

    # --- 止盈卖出（不是保守减仓，是兑现盈利）---
    take_profit_targets: list[dict[str, Any]] = []
    for t in profit_targets:
        if t["price"] > price and "止盈" in t["label"] or "目标" in t["label"] or "卖出" in t["label"]:
            take_profit_targets.append(t)

    if in_profit and cost_price > 0:
        take_profit_targets.insert(0, {
            "price": round(price * 1.05, 2),
            "label": "移动止盈",
            "action": "现价基础上再涨 5% 减 1/3",
            "reason": f"已有 {pnl_pct:.1f}% 浮盈，保护利润同时保留上涨空间",
        })

    if ma5 and price > ma5 * 1.08 and change_5d > 5:
        take_profit_targets.append({
            "price": round(price * 0.95, 2),
            "label": "移动止损线",
            "action": "回落至当前价 -5% 止盈",
            "reason": "短线急涨后设置移动止盈，锁住大部分利润",
        })

    primary_take_profit = take_profit_targets[0]["price"] if take_profit_targets else round(high_20, 2)

    # --- 止损（风险控制，不作为主策略）---
    supports = [x for x in [ma60, ma20, low_20] if x]
    stop_loss = round(min(supports) * 0.96, 2) if supports else round(price * 0.90, 2)
    if cost_price > 0 and holding and in_loss:
        stop_loss = round(min(stop_loss, cost_price * 0.88), 2)

    # --- 盈利导向汇总 ---
    summary_parts: list[str] = []

    if holding and cost_price > 0:
        if in_profit:
            summary_parts.append(
                f"**当前浮盈 {pnl_pct:.1f}%** — 持有为主，第一止盈 **{cost_price * 1.08:.2f}** 元（减 1/3），"
                f"第二止盈 **{max(cost_price * 1.15, high_20 * 0.98):.2f}** 元"
            )
        elif in_loss:
            summary_parts.append(
                f"**当前浮亏 {pnl_pct:.1f}%** — 目标先回本 **{cost_price:.2f}** 元，"
                f"回本后第一止盈 **{cost_price * 1.08:.2f}** 元"
            )
            if rebound_signal:
                summary_parts.append(
                    f"**摊低成本加仓**：{primary_add_low:.2f} – {primary_add_high:.2f} 元，"
                    "小仓试探，反弹即有机会扭亏为盈"
                )
        else:
            summary_parts.append(f"**接近成本线** — 突破 **{cost_price * 1.05:.2f}** 元可持有看 **{cost_price * 1.15:.2f}** 元")

    if add_zones and not (in_loss and not rebound_signal):
        summary_parts.append(
            f"**盈利加仓区间**：{primary_add_low:.2f} – {primary_add_high:.2f} 元（扩大盈利仓位）"
        )
    elif add_zones and rebound_signal:
        pass  # already covered
    elif in_loss and not rebound_signal:
        summary_parts.append(
            f"**等待加仓时机**：跌势未稳，暂不加仓；RSI 到 35 以下且出现阳线再考虑摊低成本"
        )

    if take_profit_targets:
        t0 = take_profit_targets[0]
        summary_parts.append(f"**止盈参考**：**{t0['price']:.2f}** 元 — {t0['action']}")

    summary_parts.append(f"**风控止损**：**{stop_loss:.2f}** 元（仅作底线，非主策略）")

    return {
        "price": price,
        "pnl_pct": pnl_pct,
        "add_low": primary_add_low,
        "add_high": primary_add_high,
        "add_zones": add_zones,
        "profit_targets": profit_targets,
        "take_profit_targets": take_profit_targets,
        "reduce_price": primary_take_profit,
        "reduce_targets": take_profit_targets,
        "stop_loss": stop_loss,
        "take_profit": primary_take_profit,
        "rebound_add": rebound_add,
        "rebound_signal": rebound_signal,
        "cost_price": cost_price if cost_price > 0 else None,
        "summary": "\n".join(f"- {s}" for s in summary_parts),
        "notes": notes,
    }


def discover_buy_candidates(
    exclude_codes: set[str] | None = None,
    limit: int = 5,
    scan_limit: int = 200,
) -> list[dict[str, Any]]:
    """Scan market for profit-potential buy candidates."""
    exclude_codes = exclude_codes or set()
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        return []

    df = df.copy()
    df["代码"] = df["代码"].astype(str).str.zfill(6)
    for col in ("涨跌幅", "成交额", "换手率", "最新价", "市盈率-动态"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[~df["名称"].str.contains("ST|退", na=False)]
    df = df[df["成交额"] > 5e7]
    df = df[~df["代码"].isin(exclude_codes)]
    df = df.nlargest(scan_limit, "成交额")

    candidates: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        code = str(row["代码"])
        name = str(row["名称"])
        try:
            hist = fetch_history(code, days=90)
            ind = compute_indicators(hist)
            if not ind:
                continue
            score, reasons = _score_buy_candidate(ind, row)
            if score < 3:
                continue
            plan = compute_price_plan(ind, {"price": ind.get("price", 0)}, holding=False)
            candidates.append({
                "code": code,
                "name": name,
                "score": score,
                "reasons": reasons,
                "price": float(row.get("最新价", 0) or ind.get("price", 0)),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
                "indicators": ind,
                "price_plan": plan,
            })
        except Exception:
            continue

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]


def _score_buy_candidate(ind: dict[str, Any], row: Any) -> tuple[int, list[str]]:
    """Score stocks by profit potential."""
    score = 0
    reasons: list[str] = []
    rsi = ind.get("rsi", 50)
    change_20d = ind.get("change_20d", 0)
    change_5d = ind.get("change_5d", 0)
    price = ind.get("price", 0)
    ma5, ma10, ma20 = ind.get("ma5"), ind.get("ma10"), ind.get("ma20")
    vol_ratio = ind.get("volume_ratio", 1)
    high_20 = ind.get("high_20d", 0)

    if ma5 and ma10 and ma20 and ma5 > ma10 > ma20:
        score += 4
        reasons.append("均线多头，主升趋势，盈利空间大")

    if high_20 and price >= high_20 * 0.95 and vol_ratio > 1.3:
        score += 3
        reasons.append("逼近/突破 20 日高点且放量，有望打开上行空间")

    if change_5d > 3 and vol_ratio > 1.2:
        score += 2
        reasons.append(f"近5日涨 {change_5d:.1f}% 且放量，短期动量强")

    if 45 <= rsi <= 65:
        score += 1
        reasons.append(f"RSI={rsi:.1f}，上涨动能健康")

    if rsi < 35 and change_20d < -12 and change_5d > 0:
        score += 3
        reasons.append(f"超跌反弹：20日跌 {change_20d:.1f}% 后开始企稳，反弹盈利机会")

    if ma20 and price > ma20 and price < ma20 * 1.08:
        score += 2
        reasons.append("站上 MA20 且未大幅偏离，趋势初成")

    turnover = float(row.get("换手率", 0) or 0)
    if 2 <= turnover <= 10:
        score += 1
        reasons.append(f"换手率 {turnover:.1f}%，资金活跃")

    return score, reasons
