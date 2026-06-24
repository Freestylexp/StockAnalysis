"""A-share market data via akshare."""

from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Callable

import akshare as ak
import pandas as pd
import requests

PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}


def _sina_symbol(code: str) -> str:
    code = normalize_code(code)
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    return f"{prefix}{code}"


def _eastmoney_secid(code: str) -> str:
    code = normalize_code(code)
    market = "1" if code.startswith(("6", "9")) else "0"
    return f"{market}.{code}"


@contextmanager
def _without_proxy_env():
    saved = {k: os.environ.pop(k, None) for k in PROXY_ENV_KEYS if k in os.environ}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def _detect_system_proxy() -> str | None:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        return proxy
    try:
        out = subprocess.check_output(["scutil", "--proxy"], text=True, stderr=subprocess.DEVNULL)
        if "HTTPEnable : 1" not in out:
            return None
        host_m = re.search(r"HTTPProxy : ([\d.]+)", out)
        port_m = re.search(r"HTTPPort : (\d+)", out)
        if host_m and port_m:
            return f"http://{host_m.group(1)}:{port_m.group(1)}"
    except Exception:
        pass
    return None


def _http_get(url: str, params: dict | None = None, encoding: str = "utf-8") -> requests.Response:
    """Try direct connection first, then system proxy."""
    last_error: Exception | None = None
    for use_proxy in (False, True):
        session = requests.Session()
        if use_proxy:
            proxy = _detect_system_proxy()
            if not proxy:
                continue
            session.proxies = {"http": proxy, "https": proxy}
        else:
            session.trust_env = False
        try:
            resp = session.get(
                url,
                params=params,
                headers=DEFAULT_HEADERS,
                timeout=20,
            )
            resp.encoding = encoding
            if resp.status_code == 200 and resp.text.strip():
                return resp
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("empty response")


def _run_akshare(func: Callable, *args, **kwargs):
    with _without_proxy_env():
        return func(*args, **kwargs)


def _quote_dict(
    code: str,
    name: str,
    price: float,
    prev_close: float,
    *,
    source: str,
    open_price: float = 0,
    high: float = 0,
    low: float = 0,
    volume: float = 0,
    turnover: float = 0,
    turnover_rate: float | None = None,
) -> dict[str, Any]:
    change_amount = price - prev_close if prev_close else 0
    change_pct = (price / prev_close - 1) * 100 if prev_close else 0
    return {
        "code": normalize_code(code),
        "name": name or code,
        "price": price,
        "change_pct": change_pct,
        "change_amount": change_amount,
        "volume": volume,
        "turnover": turnover,
        "high": high or price,
        "low": low or price,
        "open": open_price or price,
        "prev_close": prev_close or price,
        "turnover_rate": turnover_rate,
        "pe": None,
        "pb": None,
        "market_cap": None,
        "source": source,
    }


def _fetch_eastmoney_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for code in codes:
        try:
            resp = _http_get(
                "https://push2.eastmoney.com/api/qt/stock/get",
                params={
                    "secid": _eastmoney_secid(code),
                    "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170",
                    "ut": "fa5fd1943c7b388f047f38105475f868",
                },
            )
            payload = resp.json().get("data") or {}
            price = float(payload.get("f43") or 0) / 100
            if price <= 0:
                continue
            prev_close = float(payload.get("f60") or 0) / 100 or price
            change_pct = float(payload.get("f170") or 0) / 100
            result[normalize_code(code)] = _quote_dict(
                code,
                str(payload.get("f58") or ""),
                price,
                prev_close,
                source="eastmoney",
                open_price=float(payload.get("f46") or 0) / 100,
                high=float(payload.get("f44") or 0) / 100,
                low=float(payload.get("f45") or 0) / 100,
                volume=float(payload.get("f47") or 0),
                turnover=float(payload.get("f48") or 0),
            )
            if change_pct:
                result[normalize_code(code)]["change_pct"] = change_pct
        except Exception:
            continue
    return result


def _fetch_tencent_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    symbols = [_sina_symbol(c) for c in codes]
    resp = _http_get(f"http://qt.gtimg.cn/q={','.join(symbols)}", encoding="gbk")
    result: dict[str, dict[str, Any]] = {}
    for line in resp.text.strip().split(";"):
        line = line.strip()
        if not line or "~" not in line:
            continue
        m = re.search(r'v_\w+="(.+)"', line)
        if not m:
            continue
        parts = m.group(1).split("~")
        if len(parts) < 5:
            continue
        code = normalize_code(parts[2])
        price = float(parts[3] or 0)
        if price <= 0:
            continue
        prev_close = float(parts[4] or 0) or price
        change_pct = float(parts[32]) if len(parts) > 32 and parts[32] else ((price / prev_close - 1) * 100 if prev_close else 0)
        result[code] = _quote_dict(
            code,
            parts[1],
            price,
            prev_close,
            source="tencent",
            open_price=float(parts[5] or 0) if len(parts) > 5 else price,
        )
        result[code]["change_pct"] = change_pct
    return result


def _fetch_sina_history(code: str, days: int = 120) -> pd.DataFrame:
    """Fallback: daily K-line from Sina."""
    symbol = _sina_symbol(code)
    try:
        resp = _http_get(
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
            params={"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(min(days + 10, 1023))},
        )
        data = json.loads(resp.text)
        if not data:
            return pd.DataFrame()
        rows = []
        for item in data:
            rows.append({
                "日期": item.get("day", ""),
                "开盘": float(item.get("open", 0)),
                "最高": float(item.get("high", 0)),
                "最低": float(item.get("low", 0)),
                "收盘": float(item.get("close", 0)),
                "成交量": float(item.get("volume", 0)),
            })
        df = pd.DataFrame(rows)
        df["日期"] = pd.to_datetime(df["日期"])
        return df.tail(days).copy()
    except Exception:
        return pd.DataFrame()


def _fetch_tencent_history(code: str, days: int = 120) -> pd.DataFrame:
    """Fallback: daily K-line via akshare Tencent source."""
    try:
        df = _run_akshare(
            ak.stock_zh_a_hist_tx,
            symbol=_sina_symbol(code),
            start_date=(datetime.now() - timedelta(days=days + 60)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={"date": "日期", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "amount": "成交量"})
        return df.tail(days).copy()
    except Exception:
        return pd.DataFrame()


def _fetch_sina_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """Fallback: fetch quotes from Sina Finance API."""
    symbols = [_sina_symbol(c) for c in codes]
    url = f"http://hq.sinajs.cn/list={','.join(symbols)}"
    resp = _http_get(url, encoding="gbk")

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
            "source": "sina",
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
    from .storage import load_stocks_cache

    for item in load_stocks_cache():
        if item["code"] == code:
            return item["name"]
    try:
        df = _run_akshare(ak.stock_individual_info_em, symbol=code)
        row = df[df["item"] == "股票简称"]
        if not row.empty:
            return str(row.iloc[0]["value"])
    except Exception:
        pass
    return ""


def _fetch_akshare_spot_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    try:
        df = _run_akshare(ak.stock_zh_a_spot_em)
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        for code in codes:
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
                "source": "akshare",
            }
    except Exception:
        pass
    return result


def _fetch_quotes_from_history(codes: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for code in codes:
        code = normalize_code(code)
        hist = fetch_history(code, days=10)
        if hist is None or hist.empty:
            continue
        close = pd.to_numeric(hist["收盘"], errors="coerce")
        if close.empty:
            continue
        price = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else price
        if price <= 0:
            continue
        result[code] = _quote_dict(
            code,
            get_stock_name(code),
            price,
            prev_close,
            source="history",
        )
    return result


def fetch_realtime_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch realtime quotes for given stock codes with multi-source fallbacks."""
    if not codes:
        return {}

    normalized = [normalize_code(c) for c in codes]
    missing = list(normalized)
    result: dict[str, dict[str, Any]] = {}

    fetchers = (
        _fetch_tencent_quotes,
        _fetch_sina_quotes,
        _fetch_eastmoney_quotes,
        _fetch_akshare_spot_quotes,
    )
    for fetcher in fetchers:
        if not missing:
            break
        try:
            batch = fetcher(missing)
            result.update(batch)
            missing = [c for c in missing if c not in result]
        except Exception:
            continue

    if missing:
        history_quotes = _fetch_quotes_from_history(missing)
        result.update(history_quotes)

    return {c: result[c] for c in normalized if c in result}


def _load_stale_history_cache(code: str, days: int) -> pd.DataFrame:
    from .storage import HISTORY_CACHE_DIR
    path = HISTORY_CACHE_DIR / f"{normalize_code(code)}.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["日期"])
        return df.tail(days).copy()
    except Exception:
        return pd.DataFrame()


def fetch_history(code: str, days: int = 120) -> pd.DataFrame:
    """Fetch daily OHLCV history with multiple fallbacks + local cache."""
    from .storage import load_history_cache, save_history_cache

    code = normalize_code(code)
    cached = load_history_cache(code, days)
    if cached is not None and not cached.empty:
        return cached

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    df = pd.DataFrame()

    try:
        df = _run_akshare(
            ak.stock_zh_a_hist,
            symbol=code, period="daily",
            start_date=start, end_date=end, adjust="qfq",
        )
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        df = _fetch_tencent_history(code, days)
    if df is None or df.empty:
        df = _fetch_sina_history(code, days)

    if df is None or df.empty:
        stale = _load_stale_history_cache(code, days)
        return stale if stale is not None else pd.DataFrame()

    for col in ("开盘", "最高", "最低", "收盘", "成交量"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.tail(days).copy()
    try:
        save_history_cache(code, df)
    except Exception:
        pass
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


def fetch_stock_list() -> list[dict[str, str]]:
    """Load all A-share codes and names for search/autocomplete."""
    from .storage import load_stocks_cache, save_stocks_cache

    try:
        df = _run_akshare(ak.stock_zh_a_spot_em)
    except Exception:
        return load_stocks_cache()

    df = df.copy()
    df["代码"] = df["代码"].astype(str).str.zfill(6)
    stocks = []
    for _, r in df.iterrows():
        name = str(r.get("名称", "")).strip()
        code = str(r["代码"])
        if name and code:
            stocks.append({"code": code, "name": name})

    if stocks:
        try:
            save_stocks_cache(stocks)
        except Exception:
            pass
    return stocks or load_stocks_cache()


def search_stocks(keyword: str, stock_list: list[dict[str, str]] | None = None, limit: int = 20) -> list[dict[str, str]]:
    """Search stocks by code or name (supports partial Chinese name)."""
    keyword = keyword.strip()
    if not keyword:
        return []

    if stock_list is None:
        stock_list = fetch_stock_list()
    if not stock_list:
        return []

    kw = keyword.upper()
    exact_code: list[dict[str, str]] = []
    code_prefix: list[dict[str, str]] = []
    name_match: list[dict[str, str]] = []

    for s in stock_list:
        code = s["code"]
        name = s["name"]
        if code == kw or kw == normalize_code(keyword):
            exact_code.append(s)
        elif code.startswith(kw) or kw in code:
            code_prefix.append(s)
        elif keyword in name:
            name_match.append(s)

    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for group in (exact_code, code_prefix, name_match):
        for s in group:
            if s["code"] not in seen:
                seen.add(s["code"])
                results.append(s)
            if len(results) >= limit:
                return results
    return results


def discover_hot_stocks(limit: int = 10) -> list[dict[str, Any]]:
    """Discover trending A-shares by turnover and momentum."""
    try:
        df = _run_akshare(ak.stock_zh_a_spot_em)
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
