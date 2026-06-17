"""Data models for portfolio management."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Holding:
    code: str
    name: str = ""
    shares: float = 0
    cost_price: float = 0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Holding:
        return cls(
            code=data["code"],
            name=data.get("name", ""),
            shares=float(data.get("shares", 0)),
            cost_price=float(data.get("cost_price", 0)),
            notes=data.get("notes", ""),
        )


@dataclass
class WatchItem:
    code: str
    name: str = ""
    notes: str = ""
    added_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatchItem:
        return cls(
            code=data["code"],
            name=data.get("name", ""),
            notes=data.get("notes", ""),
            added_at=data.get("added_at", ""),
        )


@dataclass
class Portfolio:
    holdings: list[Holding] = field(default_factory=list)
    watchlist: list[WatchItem] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "holdings": [h.to_dict() for h in self.holdings],
            "watchlist": [w.to_dict() for w in self.watchlist],
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        return cls(
            holdings=[Holding.from_dict(h) for h in data.get("holdings", [])],
            watchlist=[WatchItem.from_dict(w) for w in data.get("watchlist", [])],
            settings=data.get("settings", {}),
        )
