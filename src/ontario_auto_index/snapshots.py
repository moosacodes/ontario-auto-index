from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .models import Vehicle

SCHEMA_VERSION = 2


def _json_value(value: object) -> object:
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "as_tuple"):
        return str(value)
    return value


def vehicle_dict(vehicle: Vehicle) -> dict[str, object]:
    return {key: _json_value(value) for key, value in asdict(vehicle).items()}


def write_snapshot(vehicles: Iterable[Vehicle], output: Path) -> dict[str, object]:
    ordered = sorted(vehicles, key=lambda item: (item.source_dealer_id, item.id))
    invalid = [vehicle.id for vehicle in ordered if vehicle.validation_status != "valid"]
    if invalid:
        raise ValueError(f"refusing to publish invalid vehicles: {invalid[:5]}")
    payload = json.dumps(
        [vehicle_dict(vehicle) for vehicle in ordered],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(output, "wb", compresslevel=9, mtime=0) as stream:
        stream.write(payload)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "file": output.name,
        "sha256": digest,
        "bytes": output.stat().st_size,
        "vehicle_count": len(ordered),
    }


def write_partitioned_snapshots(vehicles: Iterable[Vehicle], output_dir: Path) -> dict[str, object]:
    grouped: dict[str, list[Vehicle]] = {}
    for vehicle in vehicles:
        grouped.setdefault(vehicle.source_dealer_id, []).append(vehicle)
    partitions: list[dict[str, object]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for dealer_id, records in sorted(grouped.items()):
        filename = f"{dealer_id}.json.gz"
        compressed = write_snapshot(records, output_dir / filename)
        json_filename = f"{dealer_id}.json"
        json_path = output_dir / json_filename
        json_path.write_text(
            json.dumps([vehicle_dict(record) for record in sorted(records, key=lambda item: item.id)],
                       ensure_ascii=True, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        partitions.append({
            "dealer_id": dealer_id,
            "file": json_filename,
            "compressed_file": filename,
            "vehicle_count": compressed["vehicle_count"],
            "sha256": compressed["sha256"],
        })
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "partitions": partitions,
        "vehicle_count": sum(int(item["vehicle_count"]) for item in partitions),
    }
    (output_dir.parent / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest
