from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from .discovery import canonical_domain
from .registry import Dealer, identify_platform

INVENTORY_PATHS = (
    "/inventory/", "/used-inventory/", "/vehicles/", "/cars/",
    "/used-cars/", "/pre-owned/", "/inventory/used/",
)


@dataclass(frozen=True)
class VerificationSummary:
    checked: int
    verified: int
    restricted: int
    broken: int
    platforms: dict[str, int]


class DealerVerifier:
    def __init__(self, concurrency: int = 12, timeout: float = 20) -> None:
        self.semaphore = asyncio.Semaphore(concurrency)
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
            transport=httpx.AsyncHTTPTransport(retries=2),
            headers={"User-Agent": "OntarioAutoIndex/0.2 (+personal research; respects robots.txt)"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def verify_all(self, dealers: list[Dealer]) -> tuple[list[Dealer], VerificationSummary]:
        verified = await asyncio.gather(*(self.verify(item) for item in dealers))
        platforms: dict[str, int] = {}
        for dealer in verified:
            platform = dealer.platform or "unknown"
            platforms[platform] = platforms.get(platform, 0) + 1
        return verified, VerificationSummary(
            checked=len(verified),
            verified=sum(item.status in {"verified", "inventory"} for item in verified),
            restricted=sum(item.status == "restricted" for item in verified),
            broken=sum(item.status == "broken" for item in verified),
            platforms=platforms,
        )

    async def verify(self, dealer: Dealer) -> Dealer:
        async with self.semaphore:
            checked = datetime.now(UTC).isoformat()
            dealer.last_checked_at = checked
            dealer.canonical_domain = canonical_domain(dealer.website_url)
            try:
                home = await self.client.get(dealer.website_url)
                home.raise_for_status()
                robots_url = urljoin(str(home.url), "/robots.txt")
                robots = await self.client.get(robots_url)
                parser = RobotFileParser(robots_url)
                parser.parse(robots.text.splitlines() if robots.is_success else [])
                candidates = _inventory_candidates(str(home.url), dealer.inventory_url, home.text)
                selected: httpx.Response | None = None
                for candidate in candidates:
                    if robots.is_success and not parser.can_fetch("OntarioAutoIndex/0.2", candidate):
                        continue
                    try:
                        response = await self.client.get(candidate)
                    except httpx.HTTPError:
                        continue
                    if response.is_success and "text/html" in response.headers.get("content-type", "text/html"):
                        selected = response
                        if _inventory_evidence(response.text):
                            break
                dealer.robots_url = robots_url
                dealer.robots_allows_general = selected is not None
                if selected is None:
                    dealer.status = "restricted" if robots.is_success else "broken"
                    dealer.failure_count += 1
                    dealer.last_error = "no permitted reachable inventory candidate"
                    return dealer
                dealer.inventory_url = str(selected.url)
                combined = home.text + "\n" + selected.text
                dealer.platform = identify_platform(combined)
                dealer.adapter_key = _adapter_for(dealer.platform)
                dealer.status = "verified" if _inventory_evidence(selected.text) else "unsupported"
                dealer.last_success_at = checked
                dealer.failure_count = 0
                dealer.last_error = None
                return dealer
            except (httpx.HTTPError, OSError, ValueError) as error:
                dealer.status = "broken"
                dealer.failure_count += 1
                dealer.last_error = str(error)[:500]
                return dealer


def _inventory_candidates(home_url: str, configured: str, html: str) -> list[str]:
    candidates = [configured, home_url]
    lowered = html.lower()
    for path in INVENTORY_PATHS:
        if path in lowered:
            candidates.insert(0, urljoin(home_url, path))
    candidates.extend(urljoin(home_url, path) for path in INVENTORY_PATHS)
    return list(dict.fromkeys(candidates))


def _inventory_evidence(html: str) -> bool:
    lowered = html.lower()
    markers = ("vehicle", "inventory", "mileage", "odometer", "stock #", "stock-number", "typesense_host")
    return sum(marker in lowered for marker in markers) >= 2


def _adapter_for(platform: str) -> str | None:
    if platform in {"zopsoftware-typesense", "schemaorg-jsonld", "html-inventory"}:
        return platform
    return None
