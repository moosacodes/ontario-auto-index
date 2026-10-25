from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .models import Vehicle

SCHEMA_VERSION = 1


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
