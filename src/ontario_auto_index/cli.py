from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, replace
from pathlib import Path

import httpx

from .adapters import ZopSoftwareAdapter
from .normalization import deduplicate, normalize_listing
from .registry import DealerRegistry
from .snapshots import write_partitioned_snapshots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ontario-auto-index")
    parser.add_argument("--database", type=Path, default=Path("data/registry.sqlite3"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("registry-import")
    import_parser.add_argument("source", type=Path)
    subparsers.add_parser("registry-export").add_argument("output", type=Path)
    subparsers.add_parser("registry-verify")
    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--dealer", required=True)
    ingest.add_argument("--output", type=Path, default=Path("data/raw-vehicles.json"))
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
    elif args.command == "ingest":
        asyncio.run(_ingest(registry, args.dealer, args.output))
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


async def _ingest(registry: DealerRegistry, dealer_id: str, output: Path) -> None:
    dealer = next(dealer for dealer in registry.all() if dealer.dealer_id == dealer_id)
    adapter = ZopSoftwareAdapter()
    try:
        raw = await adapter.listings(dealer.inventory_url)
    finally:
        await adapter.close()
    vehicles = deduplicate([
        normalize_listing(replace(item, dealer_id=dealer.dealer_id, dealer_name=dealer.name))
        for item in raw
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(item) for item in vehicles], default=str, indent=2), encoding="utf-8")
    print(f"ingested {len(vehicles)} vehicles from {dealer.name}")


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
