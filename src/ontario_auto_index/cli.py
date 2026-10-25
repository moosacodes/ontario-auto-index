from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, replace
from pathlib import Path

import httpx

from .adapters import AdapterRegistry
from .discovery import OpenStreetMapDiscovery, deduplicate_dealers
from .normalization import deduplicate, normalize_listing
from .registry import DealerRegistry
from .snapshots import write_partitioned_snapshots
from .verification import DealerVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ontario-auto-index")
    parser.add_argument("--database", type=Path, default=Path("data/registry.sqlite3"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("registry-import")
    import_parser.add_argument("source", type=Path)
    subparsers.add_parser("registry-export").add_argument("output", type=Path)
    subparsers.add_parser("registry-verify")
    discover = subparsers.add_parser("discover")
    discover.add_argument("--output", type=Path, default=Path("data/discovered-dealers.json"))
    verify = subparsers.add_parser("verify")
    verify.add_argument("--limit", type=int)
    verify.add_argument("--status", default="discovered")
    verify.add_argument("--concurrency", type=int, default=12)
    verify.add_argument("--output", type=Path, default=Path("data/verification-report.json"))
    subparsers.add_parser("report")
    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--dealer", required=True)
    ingest.add_argument("--output", type=Path, default=Path("data/raw-vehicles.json"))
    ingest.add_argument("--failures", type=Path, default=Path("data/ingestion-failures.json"))
    validate = subparsers.add_parser("validate")
    validate.add_argument("source", type=Path)
    validate.add_argument("--output", type=Path, default=Path("data/validated-vehicles.json"))
    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("source", type=Path)
    snapshot.add_argument("--output", type=Path, default=Path("public/data/partitions/inventory.json.gz"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = DealerRegistry(args.database)
    if args.command == "registry-import":
        print(f"imported {registry.import_file(args.source)} dealers")
    elif args.command == "registry-export":
        registry.export(args.output)
    elif args.command == "registry-verify":
        asyncio.run(_verify(registry))
    elif args.command == "discover":
        asyncio.run(_discover(registry, args.output))
    elif args.command == "verify":
        asyncio.run(_verify_batch(registry, args.status, args.limit, args.concurrency, args.output))
    elif args.command == "report":
        _report(registry)
    elif args.command == "ingest":
        asyncio.run(_ingest(registry, args.dealer, args.output, args.failures))
    elif args.command == "validate":
        _validate(args.source, args.output)
    elif args.command == "snapshot":
        _snapshot(args.source, args.output)
    return 0


async def _verify(registry: DealerRegistry) -> None:
    for dealer in registry.all():
        try:
            registry.upsert(await registry.verify(dealer))
            print(f"{dealer.dealer_id}: {dealer.status} ({dealer.platform})")
        except (httpx.HTTPError, OSError, ValueError) as error:
            dealer.status = "broken"
            dealer.notes = f"verification failed: {error}"
            registry.upsert(dealer)
            print(f"{dealer.dealer_id}: broken ({error})")


async def _discover(registry: DealerRegistry, output: Path) -> None:
    source = OpenStreetMapDiscovery()
    try:
        records, report = await source.discover()
    finally:
        await source.close()
    existing = registry.all()
    merged = deduplicate_dealers(existing + records)
    for dealer in merged:
        registry.upsert(dealer)
    registry.export(output)
    print(json.dumps(asdict(report) | {"registry_total": len(registry.all())}, indent=2))


async def _verify_batch(
    registry: DealerRegistry, status: str, limit: int | None, concurrency: int, output: Path
) -> None:
    candidates = [item for item in registry.all() if status == "all" or item.status == status]
    if limit is not None:
        candidates = candidates[:limit]
    verifier = DealerVerifier(concurrency)
    try:
        records, summary = await verifier.verify_all(candidates)
    finally:
        await verifier.close()
    for dealer in records:
        registry.upsert(dealer)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))


def _report(registry: DealerRegistry) -> None:
    dealers = registry.all()
    statuses: dict[str, int] = {}
    platforms: dict[str, int] = {}
    municipalities: set[str] = set()
    for dealer in dealers:
        statuses[dealer.status] = statuses.get(dealer.status, 0) + 1
        platforms[dealer.platform or "unclassified"] = platforms.get(dealer.platform or "unclassified", 0) + 1
        municipalities.add(dealer.municipality)
    print(json.dumps({
        "dealers": len(dealers), "municipalities": len(municipalities),
        "statuses": statuses, "platforms": platforms,
    }, indent=2, sort_keys=True))


async def _ingest(registry: DealerRegistry, dealer_id: str, output: Path, failures_output: Path) -> None:
    dealers = [dealer for dealer in registry.all() if dealer_id == "all" and dealer.status in {"inventory", "verified"} or dealer.dealer_id == dealer_id]
    if not dealers:
        raise ValueError(f"dealer not found or not ingestible: {dealer_id}")
    collected = []
    failures: list[dict[str, str]] = []
    crawled = 0
    for dealer in dealers:
        adapters = AdapterRegistry.defaults()
        adapter_key = dealer.adapter_key or dealer.platform
        if not adapters.supports(adapter_key):
            failures.append({"dealer_id": dealer.dealer_id, "reason": f"unsupported platform: {adapter_key or 'unclassified'}"})
            continue
        adapter = adapters.get(adapter_key)
        try:
            raw = await adapter.listings(dealer.inventory_url)
            if not raw:
                failures.append({"dealer_id": dealer.dealer_id, "reason": "adapter returned no evidenced listings"})
                continue
            crawled += 1
        except (httpx.HTTPError, OSError, ValueError) as error:
            failures.append({"dealer_id": dealer.dealer_id, "reason": str(error)[:500]})
            continue
        finally:
            close = getattr(adapter, "close", None)
            if close:
                await close()
        collected.extend(
            normalize_listing(replace(item, dealer_id=dealer.dealer_id, dealer_name=dealer.name, municipality=item.municipality or dealer.municipality))
            for item in raw
        )
    vehicles = deduplicate(collected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(item) for item in vehicles], default=str, indent=2), encoding="utf-8")
    failures_output.parent.mkdir(parents=True, exist_ok=True)
    failures_output.write_text(json.dumps(failures, indent=2), encoding="utf-8")
    print(json.dumps({"dealers_selected": len(dealers), "dealers_crawled": crawled, "failures": len(failures), "vehicles": len(vehicles)}))


def _validate(source: Path, output: Path) -> None:
    records = json.loads(source.read_text(encoding="utf-8"))
    valid = [item for item in records if item.get("validation_status") == "valid"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(valid, indent=2), encoding="utf-8")
    print(f"validated {len(valid)} of {len(records)} vehicles")


def _snapshot(source: Path, output: Path) -> None:
    from datetime import datetime
    from decimal import Decimal

    from .models import OriginalValues, PriceConditions, Vehicle

    vehicles = []
    for item in json.loads(source.read_text(encoding="utf-8")):
        item["observed_at"] = datetime.fromisoformat(item["observed_at"])
        item["last_verified_at"] = datetime.fromisoformat(item["last_verified_at"])
        item["price_cad"] = Decimal(item["price_cad"]) if item["price_cad"] else None
        item["original"] = OriginalValues(**item["original"])
        item["price_conditions"] = PriceConditions(**item["price_conditions"])
        vehicles.append(Vehicle(**item))
    print(json.dumps(write_partitioned_snapshots(vehicles, output.parent), indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
