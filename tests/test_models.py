from datetime import UTC, datetime
from decimal import Decimal

from ontario_auto_index.models import OriginalValues, PriceConditions, Vehicle, validate_vehicle


def make_vehicle(**changes: object) -> Vehicle:
    values: dict[str, object] = {
        "id": "dealer-1:listing-1",
        "source_dealer_id": "dealer-1",
        "dealer_name": "Example Motors",
        "listing_url": "https://example.test/vehicle/1",
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_verified_at": datetime(2026, 1, 1, tzinfo=UTC),
        "original": OriginalValues("2020", "Honda", "Civic", "10,000 km", "$20,000"),
        "year": 2020,
        "make": "Honda",
        "model": "Civic",
        "trim": None,
        "mileage_km": 10000,
        "price_cad": Decimal(20000),
        "price_conditions": PriceConditions(None, False, False, None),
        "validation_status": "valid",
    }
    values.update(changes)
    return Vehicle(**values)  # type: ignore[arg-type]


def test_valid_vehicle_has_no_errors() -> None:
    assert validate_vehicle(make_vehicle()) == []


def test_invalid_url_is_rejected() -> None:
    assert "listing_url must be an absolute HTTP(S) URL" in validate_vehicle(
        make_vehicle(listing_url="/vehicle/1")
    )
