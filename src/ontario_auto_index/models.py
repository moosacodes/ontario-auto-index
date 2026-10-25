from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

ValidationStatus = Literal["valid", "invalid", "needs_review"]


@dataclass(frozen=True)
class OriginalValues:
    year: str | None
    make: str | None
    model: str | None
    mileage: str | None
    price: str | None


@dataclass(frozen=True)
class PriceConditions:
    text: str | None
    is_finance_only: bool
    is_lease_only: bool
    includes_tax: bool | None


@dataclass(frozen=True)
class Vehicle:
    id: str
    source_dealer_id: str
    dealer_name: str
    listing_url: str
    observed_at: datetime
    last_verified_at: datetime
    original: OriginalValues
    year: int | None
    make: str | None
    model: str | None
    trim: str | None
    mileage_km: int | None
    price_cad: Decimal | None
    price_conditions: PriceConditions
    validation_status: ValidationStatus


def validate_vehicle(vehicle: Vehicle) -> list[str]:
    errors: list[str] = []
    parsed = urlparse(vehicle.listing_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append("listing_url must be an absolute HTTP(S) URL")
    if not vehicle.source_dealer_id or not vehicle.dealer_name:
        errors.append("dealer provenance is required")
    if vehicle.year is not None and not 1886 <= vehicle.year <= datetime.now().year + 2:
        errors.append("year is outside the plausible range")
    if vehicle.mileage_km is not None and vehicle.mileage_km < 0:
        errors.append("mileage cannot be negative")
    if vehicle.price_cad is not None and vehicle.price_cad < 0:
        errors.append("price cannot be negative")
    if vehicle.last_verified_at < vehicle.observed_at:
        errors.append("last_verified_at cannot precede observed_at")
    return errors
