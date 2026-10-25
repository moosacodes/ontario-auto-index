# Coverage

Coverage is an evidence-backed measurement, not a marketing claim.

## Phase 2/3 evaluation — 2026-10-25

Ten Ontario dealership candidates were identified from current dealership
websites and directory/search evidence, then their inventory endpoints were
checked directly. The expanded London batch added two working sources and
produced a substantially larger valid live snapshot:

| Result | Count | Details |
|---|---:|---|
| Candidate dealership websites checked | 17 | Ottawa, Toronto, North York, Markham, Hamilton, London, Kitchener, and Windsor |
| Additional authoritative discovery candidates seeded | 13 | Toyota, Honda, and Ford locator sources; not yet crawl-verified |
| Working adapters | 1 | Reusable Zop Software/Typesense adapter |
| Supported dealership sources | 5 | Ottawa Auto Sales, Right Way Auto, Wayne's Auto World, 5 Star Dealers, Titanium Auto |
| Live valid listings published | 440 | 332 + 69 in London; 9 + 6 + 24 in Ottawa/Hamilton |
| Broken sources | 4 | 404 or DNS failure at the evaluated inventory URL |
| Accessible but unsupported | 6 | Auto Rover, Rockcliff Auto, AutoPark, Dundas Auto, Sherwood Auto, and additional dynamic sources |
| Restricted | 5 | Downtown Toyota, Heffner Toyota, AutoHouse Kitchener, MacMaster, Chelsea Auto returned HTTP 403 |

The working sources exposed public inventory pages, public search-only
configurations, and records containing source listing paths, price, odometer,
year, make, model, trim, VIN, and dealer identity. Their robots files allowed
the general user-agent path at evaluation time, but named bot rules were also
present where checked; this is recorded in the registry and is not a blanket
reuse authorization. The checked-in snapshot contains five sources and their
original listing links. The London sources contributed 401 records in this
evaluation; this is still a measured sample, not a claim that London or
Ontario inventory is complete.

The other evaluated candidates are recorded in `data/dealers.json` with their
status, platform evidence, endpoint result, and limitation. They are not
claimed as supported. Scheduled refresh is enabled only for the five verified
inventory sources.

This is still not provincial coverage. The next discovery batch must import and
evaluate the UCDA/OMVIC population systematically rather than treating the
13 manufacturer-locator candidates as a complete list.

Report at every release:

- registry dealers by status and municipality;
- verified inventory sources and supported adapter/platform;
- successful, failed, restricted, and skipped crawl counts;
- records ingested, rejected, and published;
- age of the oldest successful crawl;
- known directory, platform, and geographic gaps.

The project must not claim complete provincial coverage until the registry
method, source population, crawl results, and unresolved gaps are reproducible.
The live refresh workflow now republishes supported sources every six hours,
but refresh frequency does not expand source coverage. The current release
contains 440 measured listings from five dealerships; registry expansion and
platform evaluation are required to grow that number without inventing or
copying unverified inventory.
