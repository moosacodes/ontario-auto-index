from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlparse

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
    image_urls: tuple[str, ...] = ()
    municipality: str | None = None
    body_style: str | None = None
    exterior_colour: str | None = None
    transmission: str | None = None
    drivetrain: str | None = None
    fuel_type: str | None = None
    vin: str | None = None


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

    @classmethod
    def defaults(cls, client: httpx.AsyncClient | None = None) -> AdapterRegistry:
        registry = cls()
        registry.register(ZopSoftwareAdapter(client))
        registry.register(JsonLdInventoryAdapter(client))
        return registry


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
        endpoint = f"https://{config['host']}/collections/{config['collection']}/documents/search"
        payload: dict[str, object] = {}
        hits: list[dict[str, object]] = []
        page_number = 1
        while True:
            response = await self.client.get(
                endpoint,
                params={**query, "page": page_number},
                headers={"x-typesense-api-key": config["api_key"]},
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("hits", [])
            if not isinstance(batch, list):
                raise TypeError("Typesense response did not contain a hits list")
            hits.extend(item for item in batch if isinstance(item, dict))
            found = int(payload.get("found", len(hits)))
            if not batch or len(hits) >= found:
                break
            page_number += 1
        payload["hits"] = hits
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
                    image_urls=_image_urls(
                        item,
                        config.get("image_domain") or str(page.url),
                    ),
                    municipality=_first_string(item, "city", "municipality", "location_city"),
                    body_style=_first_string(item, "body_style", "body"),
                    exterior_colour=_first_string(item, "exterior_color", "exterior_colour", "color"),
                    transmission=_first_string(item, "transmission"),
                    drivetrain=_first_string(item, "drivetrain", "drive_train"),
                    fuel_type=_first_string(item, "fuel_type", "fuel"),
                    vin=_first_string(item, "vin"),
                )
            )
        return listings


class JsonLdInventoryAdapter:
    """Portable adapter for small dealers publishing Schema.org Vehicle/Product data."""

    key = "schemaorg-jsonld"

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
        response = await self.client.get(url)
        response.raise_for_status()
        dealer_id = _slug(urlparse(str(response.url)).netloc.removeprefix("www."))
        dealer_name = _page_name(response.text, dealer_id)
        records: list[RawListing] = []
        for item in _json_ld_items(extract_json_ld(response.text)):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if not any(value in {"Vehicle", "Car", "Product"} for value in types):
                continue
            vehicle = item.get("vehicle") if isinstance(item.get("vehicle"), dict) else item
            if not isinstance(vehicle, dict):
                continue
            listing_url = _string(item.get("url") or vehicle.get("url"))
            if not listing_url:
                continue
            offer = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            brand = vehicle.get("brand")
            make = brand.get("name") if isinstance(brand, dict) else brand
            mileage = vehicle.get("mileageFromOdometer")
            if isinstance(mileage, dict):
                mileage = mileage.get("value")
            image_item = dict(vehicle)
            image_item["image"] = item.get("image") or vehicle.get("image")
            records.append(RawListing(
                dealer_id=dealer_id,
                dealer_name=dealer_name,
                listing_url=urljoin(str(response.url), listing_url),
                original=OriginalValues(
                    year=_string(vehicle.get("vehicleModelDate") or vehicle.get("modelDate")),
                    make=_string(make),
                    model=_string(vehicle.get("model")),
                    mileage=_string(mileage),
                    price=_string(offer.get("price")),
                ),
                trim=_string(vehicle.get("vehicleConfiguration")),
                source_id=_string(item.get("sku") or vehicle.get("vehicleIdentificationNumber")) or listing_url,
                source_values=item,
                image_urls=_image_urls(image_item, str(response.url)),
                body_style=_string(vehicle.get("bodyType")),
                exterior_colour=_string(vehicle.get("color")),
                transmission=_string(vehicle.get("vehicleTransmission")),
                drivetrain=_string(vehicle.get("driveWheelConfiguration")),
                fuel_type=_string(vehicle.get("fuelType")),
                vin=_string(vehicle.get("vehicleIdentificationNumber")),
            ))
        return records


def _json_ld_items(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    pending: list[object] = list(documents)
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            items.append(value)
            for key in ("@graph", "itemListElement"):
                nested = value.get(key)
                if isinstance(nested, list):
                    pending.extend(nested)
                elif isinstance(nested, dict):
                    pending.append(nested)
        elif isinstance(value, list):
            pending.extend(value)
    return items


def _page_name(html: str, fallback: str) -> str:
    title = LexborHTMLParser(html).css_first("title")
    if title:
        name = re.split(r"[-|:]", title.text(strip=True), maxsplit=1)[0].strip()
        if name:
            return name
    return fallback


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
    image_match = re.search(r'"IMAGE_DOMAIN":\s*"(?P<image>[^"]+)"', html)
    return {
        "client_domain": values["client"],
        "collection": values["collection"],
        "api_key": values["key"],
        "host": values["host"],
        "image_domain": image_match.group("image") if image_match else "",
    }


def _string(value: object) -> str | None:
    return None if value is None or value == "" else str(value)


def _first_string(item: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _string(item.get(key))
        if value:
            return value
    return None


def _image_urls(item: dict[str, object], base_url: str) -> tuple[str, ...]:
    """Extract only URLs explicitly published by the inventory source."""
    candidates: list[object] = []
    for key in ("images", "image_urls", "photos", "photo", "image", "featured_image", "thumbnail"):
        value = item.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif value:
            candidates.append(value)
    urls: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("url") or candidate.get("src")
        if not isinstance(candidate, str):
            continue
        # Several dealer platforms serialize galleries as semicolon-delimited strings.
        for source in re.split(r"\s*[;|]\s*", candidate):
            if not source:
                continue
            if source.startswith("/"):
                parsed_base = urlparse(base_url)
                url = f"{parsed_base.scheme}://{parsed_base.netloc}{source}"
            else:
                url = urljoin(base_url.rstrip("/") + "/", source)
            if url.startswith(("http://", "https://")) and url not in urls:
                urls.append(url)
    return tuple(urls[:12])


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
