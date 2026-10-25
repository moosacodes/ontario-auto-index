# Ontario Auto Index

Ontario Auto Index is a static-first, batch-generated search index for publicly
listed vehicle inventory at Ontario dealerships. It is designed for personal
use and a small number of family members, with coverage and source accuracy
prioritized over convenience.

## Status

The repository currently contains the Phase 1 foundation:

- A documented data, discovery, publication, and deployment architecture.
- A Python ingestion package with strict normalization and validation contracts.
- A Vite/React/TypeScript frontend foundation that loads partitioned snapshots.
- GitHub Actions workflow foundations for CI and controlled batch processing.

No dealership is considered supported until an adapter has successfully
ingested and validated real listings from that dealership. This repository does
not contain fabricated inventory.

## Local development

### Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

### Frontend

```powershell
npm install
npm run dev
```

The frontend accepts a generated data directory at `public/data`. A small
sample is intentionally not included: empty-state behavior is safer than
mistaking test data for live inventory.

## Project layout

```text
src/ontario_auto_index/  ingestion, schema, adapters, validation, snapshots
tests/                    deterministic unit tests
web/                      Vite React frontend
workflows/                GitHub Actions
docs/                     operational notes and runbooks
```

See [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_SCHEMA.md](DATA_SCHEMA.md), and
[DEPLOYMENT.md](DEPLOYMENT.md) before enabling scheduled collection.

## Safety and scope

Only publicly accessible, permitted sources should be collected. Respect
robots.txt, terms of service, rate limits, copyright, and applicable law.
Credentials, private contact details, restricted inventory, and secrets must
never enter snapshots or the repository. GitHub Pages is public hosting and is
not an access-control boundary.
