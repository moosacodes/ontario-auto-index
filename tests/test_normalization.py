from datetime import UTC, datetime
from decimal import Decimal

from ontario_auto_index.adapters import RawListing
from ontario_auto_index.models import OriginalValues
from ontario_auto_index.normalization import deduplicate, normalize_listing


def test_normalization_preserves_originals_and_converts_known_values() -> None:
    record = normalize_listing(
        RawListing(
            dealer_id="example",
            dealer_name="Example Motors",
            listing_url="https://example.test/vehicle/1",
            original=OriginalValues("2018", "Honda", "Civic", "12,345", "$18,500"),
            trim="EX",
            source_id="1",
        ),
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert record.year == 2018
    assert record.mileage_km == 12345
    assert record.price_cad == Decimal(18500)
    assert record.original.price == "$18,500"


def test_deduplication_is_source_aware() -> None:
    first = normalize_listing(
        RawListing("dealer-a", "A", "https://a.test/1", OriginalValues("2020", "Ford", "F150", None, None), source_id="1")
    )
    second = normalize_listing(
        RawListing("dealer-b", "B", "https://b.test/1", OriginalValues("2020", "Ford", "F150", None, None), source_id="1")
    )
    assert len(deduplicate([first, second])) == 2
