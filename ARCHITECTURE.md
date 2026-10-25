# Architecture

## Principles

1. Source evidence is retained alongside every normalized value.
2. A crawl failure is an operational failure, never evidence that a vehicle was sold.
3. Invalid or incomplete batches are rejected before publication.
4. Generated artifacts are bounded, deterministic, compressed, and published atomically.
5. The repository is source code and release artifacts, not an unbounded vehicle database.

## Data flow

`dealer registry -> deterministic shard -> adapter -> raw listing evidence ->
normalization -> validation -> SQLite staging -> partitioned JSON.gz ->
manifest/checksums -> static site`

The runner filesystem is disposable. A workflow uploads artifacts between jobs;
no job assumes a persistent disk. Publication uses a temporary staging
directory, validates the manifest, then replaces the published artifact set as
one release.

## Components

- **Discovery**: registry maintenance and source classification. Discovery
  records evidence and confidence but does not imply crawl support.
- **Adapters**: small platform/source-specific implementations behind a common
  interface. An adapter emits raw values and the original URL; it never invents
  missing values.
- **Normalizer**: converts source values into canonical types while preserving
  original extracted text.
- **Validator**: rejects impossible values, missing provenance, invalid URLs,
  stale publication timestamps, and duplicate identity collisions.
- **Snapshot builder**: stable sort, stable JSON serialization, gzip, checksums,
  schema version, and manifest generation.
- **Frontend**: downloads only the manifest and selected partition/index files,
  then searches locally. IndexedDB stores saved vehicles and searches.

## Scale strategy

The first delivery uses partitioned gzip JSON. At 10,000 vehicles, a small
number of make partitions is sufficient. At 100,000 or 500,000 vehicles,
partitions should be selected by make and a deterministic hash bucket, with a
compact search index and paginated result loading. The browser must never fetch
the complete province-wide dataset during initial page load.

## Budget guardrails

- Keep the repository source-only plus a small, current release artifact.
- Enforce a 100 MB generated-release warning and a 250 MB hard publication
  limit in validation.
- Retain at most the current release and one rollback release in Pages/object
  storage; retain workflow logs only for the GitHub-configured period.
- Measure Actions minutes, artifact bytes, and request counts monthly before
  increasing schedules.

If release artifacts exceed repository/Pages limits, use a free-tier object
store only after documenting egress, retention, public URL, CORS, availability,
and deletion limits in [DEPLOYMENT.md](DEPLOYMENT.md). Git remains unsuitable
for vehicle history.
