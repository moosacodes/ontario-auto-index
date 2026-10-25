from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

import httpx
from selectolax.lexbor import LexborHTMLParser

from .models import OriginalValues


@dataclass(frozen=True)
class RawListing:
    dealer_id: str
    dealer_name: str
    listing_url: str
    original: OriginalValues
    trim: str | None = None
    price_conditions_text: str | None = None
    source_id: str | None = None
    source_values: dict[str, object] | None = None


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


def extract_json_ld(html: str) -> list[dict[str, object]]:
    """Extract object JSON-LD blocks without treating arbitrary page text as data."""
    import json

    documents: list[dict[str, object]] = []
    for node in LexborHTMLParser(html).css('script[type="application/ld+json"]'):
        try:
            value = json.loads(node.text())
        except json.JSONDecodeError:
            continue
        values = value if isinstance(value, list) else [value]
        documents.extend(item for item in values if isinstance(item, dict))
    return documents


class ZopSoftwareAdapter:
    """Read the public search index exposed by dealerships using Zop Software."""

    key = "zopsoftware-typesense"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "OntarioAutoIndex/0.1 (+personal research)"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def listings(self, url: str) -> list[RawListing]:
        page = await self.client.get(url)
        page.raise_for_status()
        config = _zop_config(page.text)
        query = {
            "q": "*",
            "query_by": "make,model,trim",
            "per_page": 250,
            "filter_by": "visibility:>0 && deleted_at:=0 && status:=[Instock]",
        }
        response = await self.client.get(
            f"https://{config['host']}/collections/{config['collection']}/documents/search",
            params=query,
            headers={"x-typesense-api-key": config["api_key"]},
        )
        response.raise_for_status()
        payload = response.json()
        dealer_id = _slug(config["client_domain"])
        dealer_name = _dealer_name(payload, page.text, dealer_id)
        listings: list[RawListing] = []
        for hit in payload.get("hits", []):
            item = hit.get("document", {})
            if not isinstance(item, dict) or not item.get("page_url"):
                continue
            listing_url = urljoin(str(page.url), str(item["page_url"]))
            original = OriginalValues(
                year=_string(item.get("year")),
                make=_string(item.get("make")),
                model=_string(item.get("model")),
                mileage=_string(item.get("odometer")),
                price=_string(item.get("price")),
            )
            listings.append(
                RawListing(
                    dealer_id=dealer_id,
                    dealer_name=dealer_name,
                    listing_url=listing_url,
                    original=original,
                    trim=_string(item.get("trim")),
                    source_id=_string(item.get("id")) or listing_url,
                    source_values={key: value for key, value in item.items()},
                )
            )
        return listings


def _zop_config(html: str) -> dict[str, str]:
    pattern = re.compile(
        r'"CLIENT_DOMAIN":\s*"(?P<client>[^"]+)".*?'
        r'"COLLECTION":\s*"(?P<collection>[^"]+)".*?'
        r'"API_KEY":\s*"(?P<key>[^"]+)".*?'
        r'"TYPESENSE_HOST":\s*"(?P<host>[^"]+)"',
        re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        raise ValueError("Zop Software inventory configuration was not found")
    values = match.groupdict()
    try:
        base64.b64decode(values["key"], validate=True)
    except (ValueError, TypeError):
        raise ValueError("Zop Software search key is not valid base64") from None
    return {
        "client_domain": values["client"],
        "collection": values["collection"],
        "api_key": values["key"],
        "host": values["host"],
    }


def _string(value: object) -> str | None:
    return None if value is None or value == "" else str(value)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _dealer_name(payload: dict[str, object], html: str, fallback: str) -> str:
    hits = payload.get("hits", [])
    if isinstance(hits, list) and hits:
        document = hits[0].get("document", {})
        if isinstance(document, dict) and document.get("location"):
            return str(document["location"])
    title = LexborHTMLParser(html).css_first("title")
    if title:
        name = re.split(r"[-|:]", title.text(strip=True), maxsplit=1)[0].strip()
        if name:
            return name
    return fallback
