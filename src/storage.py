"""Portfolio JSON storage."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Portfolio

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.json"


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
