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
release snapshot from five live sources is included after live ingestion
verification. Recreate it with:

```powershell
ontario-auto-index --database data\registry.sqlite3 registry-import data\dealers.json
ontario-auto-index --database data\registry.sqlite3 ingest --dealer ottawa-auto-sales
ontario-auto-index --database data\registry.sqlite3 snapshot data\raw-vehicles.json
```

Use `--dealer all` to ingest every registry entry currently marked `inventory`
or `verified`. Platform-specific Typesense and portable Schema.org JSON-LD
adapters both preserve source-published photos and specifications.

The CLI also provides `registry-export`, `registry-verify`, and `validate`.
The registry and generated working files remain local; only the bounded,
validated static release belongs in the website output.

The committed release is deployable to GitHub Pages through the Actions
workflow. Pages is public and is not an access-control boundary.

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
