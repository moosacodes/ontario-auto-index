from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import OriginalValues


@dataclass(frozen=True)
class RawListing:
    dealer_id: str
    dealer_name: str
    listing_url: str
    original: OriginalValues
    trim: str | None = None
    price_conditions_text: str | None = None


class InventoryAdapter(Protocol):
    key: str

    async def listings(self, url: str) -> list[RawListing]:
        """Return only listings evidenced by the source page."""


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, InventoryAdapter] = {}

    def register(self, adapter: InventoryAdapter) -> None:
        if adapter.key in self._adapters:
            raise ValueError(f"adapter already registered: {adapter.key}")
        self._adapters[adapter.key] = adapter

    def get(self, key: str) -> InventoryAdapter:
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise KeyError(f"unsupported adapter: {key}") from exc
