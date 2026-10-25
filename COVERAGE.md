# Coverage

Coverage is an evidence-backed measurement, not a marketing claim.

## Phase 2/3 evaluation — 2026-10-25

Ten Ontario dealership candidates were identified from current dealership
websites and directory/search evidence, then their inventory endpoints were
checked directly. One source currently has a working adapter and produced a
valid live snapshot:

| Result | Count | Details |
|---|---:|---|
| Candidate dealership websites checked | 10 | Ottawa, Toronto, North York, Markham, and Hamilton |
| Working adapters | 1 | Reusable Zop Software/Typesense adapter |
| Supported dealership sources | 3 | Ottawa Auto Sales, Right Way Auto, Wayne's Auto World |
| Live valid listings published | 39 | 9 + 6 + 24 records observed at run time |
| Broken sources | 4 | 404 or DNS failure at the evaluated inventory URL |
| Accessible but unsupported | 2 | Auto Rover and Rockcliff Auto require endpoint/browser evaluation |
| Restricted | 1 | Downtown Toyota used inventory returned HTTP 403 |

The working sources exposed public inventory pages, public search-only
configurations, and records containing source listing paths, price, odometer,
year, make, model, trim, VIN, and dealer identity. Their robots files allowed
the general user-agent path at evaluation time, but named bot rules were also
present where checked; this is recorded in the registry and is not a blanket
reuse authorization. The checked-in snapshot is limited to these three sources
and their original listing links.

The other nine candidates are recorded in `data/dealers.json` with their
status, platform evidence, endpoint result, and limitation. They are not
claimed as supported. No scheduled crawling has been enabled.

Report at every release:

- registry dealers by status and municipality;
- verified inventory sources and supported adapter/platform;
- successful, failed, restricted, and skipped crawl counts;
- records ingested, rejected, and published;
- age of the oldest successful crawl;
- known directory, platform, and geographic gaps.

The project must not claim complete provincial coverage until the registry
method, source population, crawl results, and unresolved gaps are reproducible.
