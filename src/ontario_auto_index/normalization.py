from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from .adapters import RawListing
from .models import PriceConditions, Vehicle, validate_vehicle


def normalize_listing(raw: RawListing, observed_at: datetime | None = None) -> Vehicle:
    observed = observed_at or datetime.now(UTC)
    year = _int(raw.original.year)
    mileage = _int(raw.original.mileage)
    price = _decimal(raw.original.price)
    vehicle = Vehicle(
        id=f"{raw.dealer_id}:{raw.source_id or raw.listing_url}",
        source_dealer_id=raw.dealer_id,
        dealer_name=raw.dealer_name,
        listing_url=raw.listing_url,
        observed_at=observed,
        last_verified_at=observed,
        original=raw.original,
        year=year,
        make=_clean(raw.original.make),
        model=_clean(raw.original.model),
        trim=_clean(raw.trim),
        mileage_km=mileage,
        price_cad=price,
        price_conditions=PriceConditions(raw.price_conditions_text, False, False, None),
        validation_status="valid",
        image_urls=raw.image_urls,
        municipality=_clean(raw.municipality),
        body_style=_clean(raw.body_style),
        exterior_colour=_clean(raw.exterior_colour),
        transmission=_clean(raw.transmission),
        drivetrain=_clean(raw.drivetrain),
        fuel_type=_clean(raw.fuel_type),
        vin=_clean(raw.vin),
    )
    return replace(vehicle, validation_status="valid" if not validate_vehicle(vehicle) else "invalid")


def deduplicate(vehicles: list[Vehicle]) -> list[Vehicle]:
    by_key: dict[str, Vehicle] = {}
    for vehicle in vehicles:
        key = _identity_key(vehicle)
        current = by_key.get(key)
        if current is None or vehicle.last_verified_at > current.last_verified_at:
            by_key[key] = vehicle
    return sorted(by_key.values(), key=lambda item: (item.source_dealer_id, item.id))


def _identity_key(vehicle: Vehicle) -> str:
    source_id = vehicle.id.split(":", 1)[-1]
    if source_id:
        return f"{vehicle.source_dealer_id}:{source_id}"
    content = "|".join((vehicle.listing_url, vehicle.make or "", vehicle.model or ""))
    return sha256(content.encode()).hexdigest()


def _clean(value: str | None) -> str | None:
    return value.strip() or None if value else None


def _int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d[\d, ]*", value)
    return int(match.group(0).replace(",", "").replace(" ", "")) if match else None


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(re.sub(r"[^0-9.]", "", value))
    except InvalidOperation:
        return None
