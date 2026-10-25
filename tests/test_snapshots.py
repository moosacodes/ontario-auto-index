from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ontario_auto_index.models import OriginalValues, PriceConditions, Vehicle
from ontario_auto_index.snapshots import write_partitioned_snapshots


def test_partitioned_snapshot_writes_manifest_and_gzip(tmp_path) -> None:
    vehicle = Vehicle(
        id="dealer:1",
        source_dealer_id="dealer",
        dealer_name="Example",
        listing_url="https://example.test/1",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_verified_at=datetime(2026, 1, 1, tzinfo=UTC),
        original=OriginalValues("2020", "Honda", "Civic", "1", "$1"),
        year=2020,
        make="Honda",
        model="Civic",
        trim=None,
        mileage_km=1,
        price_cad=Decimal(1),
        price_conditions=PriceConditions(None, False, False, None),
        validation_status="valid",
    )
    manifest = write_partitioned_snapshots([vehicle], tmp_path / "partitions")
    assert manifest["vehicle_count"] == 1
    assert (tmp_path / "partitions" / "dealer.json.gz").exists()
    assert (tmp_path / "manifest.json").exists()


def test_invalid_snapshot_is_rejected(tmp_path) -> None:
    from ontario_auto_index.snapshots import write_snapshot

    vehicle = Vehicle(
        id="dealer:invalid",
        source_dealer_id="dealer",
        dealer_name="Example",
        listing_url="https://example.test/invalid",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_verified_at=datetime(2026, 1, 1, tzinfo=UTC),
        original=OriginalValues(None, None, None, None, None),
        year=None,
        make=None,
        model=None,
        trim=None,
        mileage_km=None,
        price_cad=None,
        price_conditions=PriceConditions(None, False, False, None),
        validation_status="invalid",
    )
    with pytest.raises(ValueError, match="invalid"):
        write_snapshot([vehicle], tmp_path / "invalid.json.gz")
