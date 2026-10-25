from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .registry import Dealer

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

ONTARIO_DEALER_QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="CA-ON"]->.ontario;
nwr["shop"="car"](area.ontario);
out center tags;
"""


@dataclass(frozen=True)
class DiscoveryReport:
    source: str
    examined: int
    accepted: int
    without_website: int


class OpenStreetMapDiscovery:
    """Province-wide seed discovery using attributed OpenStreetMap data."""

    source_url = "https://www.openstreetmap.org/copyright"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(
            timeout=240,
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
            headers={"User-Agent": "OntarioAutoIndex/0.2 (+https://github.com/)"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def discover(self) -> tuple[list[Dealer], DiscoveryReport]:
        last_error: Exception | None = None
        payload: dict[str, object] | None = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                response = await self.client.post(endpoint, data={"data": ONTARIO_DEALER_QUERY})
                response.raise_for_status()
                payload = response.json()
                break
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                await asyncio.sleep(1)
        if payload is None:
            raise RuntimeError(f"all Overpass endpoints failed: {last_error}")

        elements = payload.get("elements", [])
        records: list[Dealer] = []
        missing = 0
        for element in elements if isinstance(elements, list) else []:
            if not isinstance(element, dict) or not isinstance(element.get("tags"), dict):
                continue
            tags = element["tags"]
            website = _website(tags)
            if not website:
                missing += 1
                continue
            name = _text(tags.get("name") or tags.get("operator") or tags.get("brand"))
            if not name:
                continue
            municipality = _text(tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")) or "Ontario"
            domain = canonical_domain(website)
            if not domain:
                continue
            element_type = _text(element.get("type")) or "element"
            element_id = _text(element.get("id")) or domain
            records.append(Dealer(
                dealer_id=_slug(f"{name}-{municipality}"),
                name=name,
                municipality=municipality,
                website_url=website,
                inventory_url=website,
                discovery_source_url=f"https://www.openstreetmap.org/{element_type}/{element_id}",
                adapter_key=None,
                status="discovered",
                canonical_domain=domain,
                province="ON",
                address=_address(tags),
                postal_code=_text(tags.get("addr:postcode")),
                latitude=_coordinate(element, "lat"),
                longitude=_coordinate(element, "lon"),
                notes="Geographic seed from OpenStreetMap; website and inventory require verification. © OpenStreetMap contributors (ODbL).",
            ))
        return records, DiscoveryReport("openstreetmap-overpass", len(elements), len(records), missing)


def canonical_domain(url: str) -> str:
    candidate = url if "://" in url else f"https://{url}"
    host = (urlparse(candidate).hostname or "").lower().removeprefix("www.")
    return host.rstrip(".")


def deduplicate_dealers(records: list[Dealer]) -> list[Dealer]:
    """Merge source records by canonical website domain, retaining richer metadata."""
    by_domain: dict[str, Dealer] = {}
    for record in records:
        domain = record.canonical_domain or canonical_domain(record.website_url)
        if not domain:
            continue
        record.canonical_domain = domain
        current = by_domain.get(domain)
        if current is None:
            by_domain[domain] = record
            continue
        if current.municipality == "Ontario" and record.municipality != "Ontario":
            current.municipality = record.municipality
        current.address = current.address or record.address
        current.postal_code = current.postal_code or record.postal_code
        current.latitude = current.latitude or record.latitude
        current.longitude = current.longitude or record.longitude
    return sorted(by_domain.values(), key=lambda item: item.dealer_id)


def _website(tags: dict[str, object]) -> str | None:
    value = _text(tags.get("contact:website") or tags.get("website") or tags.get("url"))
    if not value:
        return None
    return value if "://" in value else f"https://{value}"


def _address(tags: dict[str, object]) -> str | None:
    parts = [_text(tags.get("addr:housenumber")), _text(tags.get("addr:street"))]
    joined = " ".join(part for part in parts if part)
    return joined or None


def _coordinate(element: dict[str, object], key: str) -> float | None:
    value = element.get(key)
    if value is None and isinstance(element.get("center"), dict):
        value = element["center"].get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _text(value: object) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
