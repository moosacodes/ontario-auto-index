# Data schema

Schema version: `1`

## Vehicle

Each published vehicle has:

- `id`: stable source-aware identifier;
- `source_dealer_id`, `dealer_name`, `listing_url`;
- `observed_at`, `last_verified_at`;
- `original`: extracted strings exactly as observed;
- normalized `year`, `make`, `model`, `trim`, `mileage_km`, `price_cad`;
- `price_conditions`: source text and flags such as finance/lease/plus-tax;
- `validation_status`.

Missing source values are `null`, never guessed. The original extraction is
retained to support audits and corrections.

## Registry and manifest

Registry records contain status, source, adapter, and crawl-health fields.
Manifests contain schema version, release ID, generation timestamp, file list,
byte sizes, SHA-256 checksums, and vehicle counts. JSON is serialized with
sorted keys and stable ordering before compression.

## Retention

Compact price history stores `(vehicle_id, observed_at, price_cad)` only.
Operational failures and checkpoints are workflow artifacts or temporary SQLite
tables, not Git commits per vehicle.
