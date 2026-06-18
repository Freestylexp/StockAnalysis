"""Portfolio JSON storage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import Portfolio

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.json"
STOCKS_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "stocks_cache.json"
STOCKS_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "stocks_seed.json"
HISTORY_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "history_cache"


def load_portfolio(path: Path | None = None) -> Portfolio:
    file_path = path or DEFAULT_PATH
    if not file_path.exists():
        return Portfolio()
    with open(file_path, encoding="utf-8") as f:
        return Portfolio.from_dict(json.load(f))


def save_portfolio(portfolio: Portfolio, path: Path | None = None) -> None:
    file_path = path or DEFAULT_PATH
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(portfolio.to_dict(), f, ensure_ascii=False, indent=2)


def load_stocks_cache() -> list[dict[str, str]]:
    """Load cached stock list from disk, merged with seed data."""
    stocks: dict[str, str] = {}

    if STOCKS_SEED_PATH.exists():
        with open(STOCKS_SEED_PATH, encoding="utf-8") as f:
            for item in json.load(f):
                stocks[item["code"]] = item["name"]

    if STOCKS_CACHE_PATH.exists():
        with open(STOCKS_CACHE_PATH, encoding="utf-8") as f:
            for item in json.load(f):
                stocks[item["code"]] = item["name"]

    # Include portfolio holdings/watchlist
    pf = load_portfolio()
    for h in pf.holdings:
        stocks[h.code] = h.name or stocks.get(h.code, h.code)
    for w in pf.watchlist:
        stocks[w.code] = w.name or stocks.get(w.code, w.code)

    return [{"code": c, "name": n} for c, n in sorted(stocks.items())]


def save_stocks_cache(stocks: list[dict[str, str]]) -> None:
    STOCKS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STOCKS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)


def load_history_cache(code: str, days: int) -> "pd.DataFrame | None":
    import pandas as pd

    path = HISTORY_CACHE_DIR / f"{code}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, parse_dates=["日期"])
        if df.empty:
            return None
        # 缓存超过 1 天则仍尝试刷新，但可兜底展示
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if (datetime.now() - mtime).days > 2:
            return None
        return df.tail(days).copy()
    except Exception:
        return None


def save_history_cache(code: str, df) -> None:
    HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_CACHE_DIR / f"{code}.csv"
    df.to_csv(path, index=False)
