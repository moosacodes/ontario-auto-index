from __future__ import annotations

import asyncio
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

    def supports(self, key: str | None) -> bool:
        return bool(key and key in self._adapters)

    @classmethod
    def defaults(cls, client: httpx.AsyncClient | None = None) -> AdapterRegistry:
        registry = cls()
        registry.register(ZopSoftwareAdapter(client))
        registry.register(JsonLdInventoryAdapter(client))
        registry.register(DealerCityAdapter(client))
        for key in ("html-inventory", "wordpress", "strathcom"):
            registry.register(HtmlInventoryAdapter(key, client))
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
            transport=httpx.AsyncHTTPTransport(retries=2),
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
            transport=httpx.AsyncHTTPTransport(retries=2),
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
        records = _json_ld_records(response.text, str(response.url), dealer_id, dealer_name)
        if records:
            return records
        parser = LexborHTMLParser(response.text)
        links: list[str] = []
        for anchor in parser.css("a[href]"):
            href = anchor.attributes.get("href", "")
            absolute = urljoin(str(response.url), href)
            path = urlparse(absolute).path.lower()
            if (any(marker in path for marker in ("/vehicle", "/inventory/", "/used/", "/cars/"))
                    and re.search(r"\d", path) and absolute not in links):
                links.append(absolute)
        semaphore = asyncio.Semaphore(8)

        async def read_detail(detail_url: str) -> list[RawListing]:
            async with semaphore:
                try:
                    detail = await self.client.get(detail_url)
                    detail.raise_for_status()
                except httpx.HTTPError:
                    return []
                return _json_ld_records(detail.text, str(detail.url), dealer_id, dealer_name)

        batches = await asyncio.gather(*(read_detail(link) for link in links[:300]))
        unique: dict[str, RawListing] = {}
        for record in (item for batch in batches for item in batch):
            unique[record.source_id or record.listing_url] = record
        return list(unique.values())


def _json_ld_records(html: str, base_url: str, dealer_id: str, dealer_name: str) -> list[RawListing]:
    records: list[RawListing] = []
    for item in _json_ld_items(extract_json_ld(html)):
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
                listing_url=urljoin(base_url, listing_url),
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
                image_urls=_image_urls(image_item, base_url),
                body_style=_string(vehicle.get("bodyType")),
                exterior_colour=_string(vehicle.get("color")),
                transmission=_string(vehicle.get("vehicleTransmission")),
                drivetrain=_string(vehicle.get("driveWheelConfiguration")),
                fuel_type=_string(vehicle.get("fuelType")),
                vin=_string(vehicle.get("vehicleIdentificationNumber")),
            ))
    return records


class DealerCityAdapter:
    """Read DealerCity/SM360's public inventory listing endpoint."""

    key = "dealercity"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            transport=httpx.AsyncHTTPTransport(retries=2),
            headers={"User-Agent": "OntarioAutoIndex/0.2 (+personal research)"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def listings(self, url: str) -> list[RawListing]:
        page = await self.client.get(url)
        page.raise_for_status()
        api_paths = re.findall(r'data-listing-api-url=["\']([^"\']+)["\']', page.text)
        used_path = next((path for path in api_paths if "used-inventory" in path), None)
        if not used_path:
            used_path = "/en/used-inventory/api/listing"
        endpoint = urljoin(str(page.url), used_path)
        first = await self.client.get(endpoint)
        first.raise_for_status()
        payload = first.json()
        vehicles = list(payload.get("vehicles", []))
        pagination = payload.get("pagination", {})
        pages = int(pagination.get("numberOfPages", 1)) if isinstance(pagination, dict) else 1
        for page_number in range(2, min(pages, 100) + 1):
            response = await self.client.get(endpoint, params={"page": page_number})
            response.raise_for_status()
            batch = response.json().get("vehicles", [])
            if isinstance(batch, list):
                vehicles.extend(batch)
        dealer_id = _slug(urlparse(str(page.url)).netloc.removeprefix("www."))
        dealer_name = _page_name(page.text, dealer_id)
        records: list[RawListing] = []
        for item in vehicles:
            if not isinstance(item, dict):
                continue
            make = item.get("make") if isinstance(item.get("make"), dict) else {}
            model = item.get("model") if isinstance(item.get("model"), dict) else {}
            make_name = _string(make.get("displayName") or make.get("name"))
            model_name = _string(model.get("name"))
            year = _string(item.get("year"))
            vehicle_id = _string(item.get("vehicleId"))
            if not all((make_name, model_name, year, vehicle_id)):
                continue
            make_slug = _string(make.get("slug")) or _slug(make_name)
            model_slug = _string(model.get("slug")) or _slug(model_name)
            language = "/fr/" if "/fr/" in used_path else "/en/"
            detail_slug = _slug(f"{year}-{make_name}-{model_name}")
            listing_url = urljoin(str(page.url), f"{language}used-inventory/{make_slug}/{model_slug}/{detail_slug}-id{vehicle_id}")
            multimedia = item.get("multimedia") if isinstance(item.get("multimedia"), dict) else {}
            pictures = multimedia.get("picturesWithCompleteUrl", [])
            images = tuple(str(value) for value in pictures[:12] if isinstance(value, str)) if isinstance(pictures, list) else ()
            body = item.get("bodyStyle") if isinstance(item.get("bodyStyle"), dict) else {}
            colour = item.get("exteriorColor") if isinstance(item.get("exteriorColor"), dict) else {}
            fuel = item.get("fuel") if isinstance(item.get("fuel"), dict) else {}
            organization = item.get("primaryOrganizationUnit") if isinstance(item.get("primaryOrganizationUnit"), dict) else {}
            records.append(RawListing(
                dealer_id=dealer_id,
                dealer_name=dealer_name,
                listing_url=listing_url,
                original=OriginalValues(
                    year=year,
                    make=make_name,
                    model=model_name,
                    mileage=_string(item.get("odometer")),
                    price=_string(item.get("salePrice") or item.get("listPrice")),
                ),
                trim=_string(item.get("trim")),
                source_id=_string(item.get("serialNo")) or vehicle_id,
                source_values=item,
                image_urls=images,
                municipality=_string(organization.get("city")),
                body_style=_string(body.get("name")),
                exterior_colour=_string(colour.get("colorDescription") or colour.get("colorDescriptionEn")),
                transmission=_string(item.get("transmission")),
                drivetrain=_string(item.get("driveTrain")),
                fuel_type=_string(fuel.get("name")),
                vin=_string(item.get("serialNo")),
            ))
        return records


class HtmlInventoryAdapter:
    """Conservative adapter for server-rendered inventory and vehicle detail pages."""

    def __init__(self, key: str = "html-inventory", client: httpx.AsyncClient | None = None) -> None:
        self.key = key
        self.client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            transport=httpx.AsyncHTTPTransport(retries=2),
            headers={"User-Agent": "OntarioAutoIndex/0.2 (+personal research)"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def listings(self, url: str) -> list[RawListing]:
        first = await self.client.get(url)
        first.raise_for_status()
        dealer_id = _slug(urlparse(str(first.url)).netloc.removeprefix("www."))
        dealer_name = _page_name(first.text, dealer_id)
        pages = [first]
        parser = LexborHTMLParser(first.text)
        pagination = []
        for anchor in parser.css("a[href]"):
            href = anchor.attributes.get("href", "")
            if re.search(r"(?:/page/\d+|[?&](?:page|product-page)=\d+)", href):
                pagination.append(urljoin(str(first.url), href))
        for page_url in list(dict.fromkeys(pagination))[:12]:
            try:
                page = await self.client.get(page_url)
                if page.is_success:
                    pages.append(page)
            except httpx.HTTPError:
                continue
        links: list[str] = []
        for page in pages:
            for anchor in LexborHTMLParser(page.text).css("a[href]"):
                href = anchor.attributes.get("href", "")
                label = anchor.text(strip=True)
                absolute = urljoin(str(page.url), href)
                path = urlparse(absolute).path.lower()
                if (re.search(r"\b(?:19|20)\d{2}\b", label)
                        and any(marker in path for marker in ("inventory", "vehicle", "cars", "product"))
                        and absolute not in links):
                    links.append(absolute)
        semaphore = asyncio.Semaphore(8)

        async def parse_link(link: str) -> RawListing | None:
            async with semaphore:
                try:
                    detail = await self.client.get(link)
                    detail.raise_for_status()
                except httpx.HTTPError:
                    return None
                json_records = _json_ld_records(detail.text, str(detail.url), dealer_id, dealer_name)
                complete = [item for item in json_records if item.original.year and item.original.make and item.original.model]
                return complete[0] if complete else _html_detail_record(
                    detail.text, str(detail.url), dealer_id, dealer_name
                )

        results = await asyncio.gather(*(parse_link(link) for link in links[:500]))
        unique: dict[str, RawListing] = {}
        for record in (item for item in results if item is not None):
            unique[record.source_id or record.listing_url] = record
        return list(unique.values())


def _html_detail_record(
    html: str, url: str, dealer_id: str, dealer_name: str
) -> RawListing | None:
    parser = LexborHTMLParser(html)
    heading = parser.css_first("h1")
    title = heading.text(strip=True) if heading else ""
    match = re.search(
        r"\b(?P<year>(?:19|20)\d{2})\s+(?P<make>[A-Za-z][A-Za-z-]+)\s+(?P<model>[A-Za-z0-9][A-Za-z0-9 .-]*?)(?:\s[-|–]|$)",
        title,
    )
    if not match:
        match = re.search(r"\b(?P<year>(?:19|20)\d{2})\s+(?P<make>[A-Za-z][A-Za-z-]+)\s+(?P<model>[A-Za-z0-9][A-Za-z0-9.-]+)", title)
    if not match:
        return None
    text = parser.body.text(separator=" ", strip=True) if parser.body else parser.text()
    price_meta = parser.css_first('meta[property="product:price:amount"]')
    price = price_meta.attributes.get("content") if price_meta else None
    price = price or _label_value(text, r"(?:price|our price)", r"\$[\d,]+(?:\.\d{2})?") or _search(text, r"\$[\d,]+(?:\.\d{2})?")
    mileage = _label_value(text, r"(?:kilometers|kilometres|mileage|odometer)", r"[\d, ]+\s*(?:km|kilometres)?")
    vin = _label_value(text, r"vin", r"[A-HJ-NPR-Z0-9]{17}")
    trim = _label_value(text, r"trim", r"[^|]{1,80}")
    image_urls: list[str] = []
    for node in parser.css('meta[property="og:image"], meta[name="twitter:image"], img[src]'):
        source = node.attributes.get("content") or node.attributes.get("src")
        if source:
            image = urljoin(url, source)
            if image.startswith(("http://", "https://")) and image not in image_urls:
                image_urls.append(image)
    return RawListing(
        dealer_id=dealer_id,
        dealer_name=dealer_name,
        listing_url=url,
        original=OriginalValues(match["year"], match["make"], match["model"].strip(), mileage, price),
        trim=trim,
        source_id=vin or url,
        image_urls=tuple(image_urls[:12]),
        body_style=_label_value(text, r"body(?: type| style)?", r"[A-Za-z -]{2,30}"),
        exterior_colour=_label_value(text, r"exterior colou?r", r"[A-Za-z -]{2,30}"),
        transmission=_label_value(text, r"transmission", r"[A-Za-z -]{2,30}"),
        fuel_type=_label_value(text, r"fuel type", r"[A-Za-z -]{2,30}"),
        vin=vin,
    )


def _label_value(text: str, label: str, value: str) -> str | None:
    return _search(text, rf"\b(?:{label})\b\s*[:|-]?\s*(?P<value>{value})", "value")


def _search(text: str, pattern: str, group: str | int = 0) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(group).strip() if match else None


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
