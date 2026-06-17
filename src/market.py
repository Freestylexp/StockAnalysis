"""A-share market data via akshare."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd
import requests


def _sina_symbol(code: str) -> str:
    code = normalize_code(code)
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    return f"{prefix}{code}"


def _fetch_sina_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """Fallback: fetch quotes from Sina Finance API."""
    symbols = [_sina_symbol(c) for c in codes]
    url = f"https://hq.sinajs.cn/list={','.join(symbols)}"
    session = requests.Session()
    session.trust_env = False
    resp = session.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
    resp.encoding = "gbk"

    result: dict[str, dict[str, Any]] = {}
    for line in resp.text.strip().split("\n"):
        m = re.match(r'var hq_str_(\w+)="(.+)";', line)
        if not m:
            continue
        parts = m.group(2).split(",")
        if len(parts) < 32:
            continue
        sym = m.group(1)
        code = sym[2:]
        price = float(parts[3] or 0)
        prev_close = float(parts[2] or 0)
        change_pct = ((price / prev_close) - 1) * 100 if prev_close else 0
        result[code] = {
            "code": code,
            "name": parts[0],
            "price": price,
            "change_pct": change_pct,
            "change_amount": price - prev_close,
            "volume": float(parts[8] or 0),
            "turnover": float(parts[9] or 0),
            "high": float(parts[4] or 0),
            "low": float(parts[5] or 0),
            "open": float(parts[1] or 0),
            "prev_close": prev_close,
            "turnover_rate": None,
            "pe": None,
            "pb": None,
            "market_cap": None,
        }
    return result


def normalize_code(code: str) -> str:
    """Normalize stock code to 6-digit format."""
    code = code.strip().upper()
    for suffix in (".SH", ".SZ", ".BJ"):
        code = code.replace(suffix, "")
    return code.zfill(6)


def get_stock_name(code: str) -> str:
    code = normalize_code(code)
    try:
        df = ak.stock_individual_info_em(symbol=code)
        row = df[df["item"] == "股票简称"]
        if not row.empty:
            return str(row.iloc[0]["value"])
    except Exception:
        pass
    return ""


def fetch_realtime_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch realtime quotes for given stock codes."""
    if not codes:
        return {}

    normalized = [normalize_code(c) for c in codes]
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        try:
            sina = _fetch_sina_quotes(normalized)
            if sina:
                return {c: sina[c] for c in normalized if c in sina}
        except Exception:
            pass
        raise RuntimeError("获取行情失败，请检查网络连接")

    df["代码"] = df["代码"].astype(str).str.zfill(6)
    result: dict[str, dict[str, Any]] = {}

    for code in normalized:
        row = df[df["代码"] == code]
        if row.empty:
            continue
        r = row.iloc[0]
        result[code] = {
            "code": code,
            "name": str(r.get("名称", "")),
            "price": float(r.get("最新价", 0) or 0),
            "change_pct": float(r.get("涨跌幅", 0) or 0),
            "change_amount": float(r.get("涨跌额", 0) or 0),
            "volume": float(r.get("成交量", 0) or 0),
            "turnover": float(r.get("成交额", 0) or 0),
            "high": float(r.get("最高", 0) or 0),
            "low": float(r.get("最低", 0) or 0),
            "open": float(r.get("今开", 0) or 0),
            "prev_close": float(r.get("昨收", 0) or 0),
            "turnover_rate": float(r.get("换手率", 0) or 0),
            "pe": float(r.get("市盈率-动态", 0) or 0) if pd.notna(r.get("市盈率-动态")) else None,
            "pb": float(r.get("市净率", 0) or 0) if pd.notna(r.get("市净率")) else None,
            "market_cap": float(r.get("总市值", 0) or 0) if pd.notna(r.get("总市值")) else None,
        }
    return result


def fetch_history(code: str, days: int = 120) -> pd.DataFrame:
    """Fetch daily OHLCV history."""
    code = normalize_code(code)
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.tail(days).copy()
    df["收盘"] = pd.to_numeric(df["收盘"], errors="coerce")
    df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
    return df


def compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """Compute basic technical indicators."""
    if df is None or df.empty or len(df) < 20:
        return {}

    close = df["收盘"]
    volume = df["成交量"]

    ma5 = close.rolling(5).mean().iloc[-1]
    ma10 = close.rolling(10).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else None

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    rsi_val = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0

    vol_ma5 = volume.rolling(5).mean().iloc[-1]
    vol_ratio = float(volume.iloc[-1] / vol_ma5) if vol_ma5 > 0 else 1.0

    price = float(close.iloc[-1])
    high_20 = float(close.tail(20).max())
    low_20 = float(close.tail(20).min())

    return {
        "price": price,
        "ma5": float(ma5),
        "ma10": float(ma10),
        "ma20": float(ma20),
        "ma60": float(ma60) if ma60 is not None else None,
        "rsi": rsi_val,
        "volume_ratio": vol_ratio,
        "high_20d": high_20,
        "low_20d": low_20,
        "change_5d": float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0,
        "change_20d": float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0,
    }


def discover_hot_stocks(limit: int = 10) -> list[dict[str, Any]]:
    """Discover trending A-shares by turnover and momentum."""
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        return []

    df = df.copy()
    df["代码"] = df["代码"].astype(str).str.zfill(6)
    df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
    df["成交额"] = pd.to_numeric(df["成交额"], errors="coerce")
    df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")

    # Filter: active stocks with positive momentum, exclude ST
    df = df[~df["名称"].str.contains("ST|退", na=False)]
    df = df[df["成交额"] > 1e8]  # > 1亿成交额
    df = df[df["涨跌幅"].between(-5, 9.5)]

    # Score: momentum + liquidity
    df["score"] = (
        df["涨跌幅"].rank(pct=True) * 0.3
        + df["成交额"].rank(pct=True) * 0.4
        + df["换手率"].rank(pct=True) * 0.3
    )
    top = df.nlargest(limit, "score")

    results = []
    for _, r in top.iterrows():
        results.append({
            "code": str(r["代码"]),
            "name": str(r["名称"]),
            "price": float(r["最新价"] or 0),
            "change_pct": float(r["涨跌幅"] or 0),
            "turnover": float(r["成交额"] or 0),
            "turnover_rate": float(r["换手率"] or 0),
        })
    return results
