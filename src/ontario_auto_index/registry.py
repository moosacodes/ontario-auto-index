from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
from selectolax.lexbor import LexborHTMLParser


@dataclass
class Dealer:
    dealer_id: str
    name: str
    municipality: str
    website_url: str
    inventory_url: str
    discovery_source_url: str
    adapter_key: str | None
    status: str
    platform: str | None = None
    robots_url: str | None = None
    robots_allows_general: bool | None = None
    last_checked_at: str | None = None
    notes: str = ""


class DealerRegistry:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS dealers (
                dealer_id TEXT PRIMARY KEY, name TEXT NOT NULL, municipality TEXT NOT NULL,
                website_url TEXT NOT NULL, inventory_url TEXT NOT NULL,
                discovery_source_url TEXT NOT NULL, adapter_key TEXT, status TEXT NOT NULL,
                platform TEXT, robots_url TEXT, robots_allows_general INTEGER,
                last_checked_at TEXT, notes TEXT NOT NULL)"""
            )

    def upsert(self, dealer: Dealer) -> None:
        fields = asdict(dealer)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """INSERT INTO dealers VALUES (:dealer_id,:name,:municipality,:website_url,
                :inventory_url,:discovery_source_url,:adapter_key,:status,:platform,:robots_url,
                :robots_allows_general,:last_checked_at,:notes)
                ON CONFLICT(dealer_id) DO UPDATE SET
                name=excluded.name, municipality=excluded.municipality,
                website_url=excluded.website_url, inventory_url=excluded.inventory_url,
                discovery_source_url=excluded.discovery_source_url, adapter_key=excluded.adapter_key,
                status=excluded.status, platform=excluded.platform, robots_url=excluded.robots_url,
                robots_allows_general=excluded.robots_allows_general,
                last_checked_at=excluded.last_checked_at, notes=excluded.notes""",
                fields,
            )

    def all(self) -> list[Dealer]:
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute("SELECT * FROM dealers ORDER BY dealer_id").fetchall()
        return [Dealer(*row) for row in rows]

    def export(self, output: Path) -> None:
        records = [asdict(dealer) for dealer in self.all()]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    def import_file(self, source: Path) -> int:
        records = json.loads(source.read_text(encoding="utf-8"))
        for record in records:
            self.upsert(Dealer(**record))
        return len(records)

    async def verify(self, dealer: Dealer) -> Dealer:
        checked = datetime.now(UTC).isoformat()
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "OntarioAutoIndex/0.1 (+personal research)"},
        ) as client:
            response = await client.get(dealer.inventory_url)
            response.raise_for_status()
            html = response.text
            robots_url = urljoin(str(response.url), "/robots.txt")
            robots = await client.get(robots_url)
        parser = LexborHTMLParser(html)
        platform = identify_platform(html)
        robot_parser = RobotFileParser()
        robot_parser.set_url(robots_url)
        robot_parser.parse(robots.text.splitlines())
        dealer.last_checked_at = checked
        dealer.robots_url = robots_url
        dealer.robots_allows_general = robot_parser.can_fetch(
            "OntarioAutoIndex/0.1", dealer.inventory_url
        )
        dealer.platform = platform
        dealer.status = "inventory" if dealer.robots_allows_general and parser.css_first("body") else "restricted"
        return dealer


def identify_platform(html: str) -> str:
    lowered = html.lower()
    if "typesense_host" in lowered and "zopsoftware" in lowered:
        return "zopsoftware-typesense"
    if "wp-content" in lowered:
        return "wordpress"
    return "unknown"


def import_csv(registry: DealerRegistry, source: Path) -> int:
    with source.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    for record in records:
        registry.upsert(Dealer(**record))
    return len(records)
