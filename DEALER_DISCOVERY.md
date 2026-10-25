# Dealer discovery

## Registry contract

The registry is the source of truth for discovery state, not a promise of
coverage. Each record should include:

- stable dealer ID, legal/display name, municipality, and province;
- official directory evidence and dealership website URL;
- platform classification and adapter key;
- status: `verified`, `inventory`, `unsupported`, `restricted`, or `broken`;
- last successful crawl, last attempted crawl, failure count, and coverage notes.

## Evidence workflow

1. Seed from official and authorized directories.
2. Verify the dealer website and identify its inventory source.
3. Classify platform only from observable evidence (HTML, feeds, or documented
   vendor markers).
4. Run a permitted smoke crawl before marking `inventory`.
5. Record failures without removing the dealer or claiming vehicles are gone.
6. Review stale records and coverage gaps on a scheduled discovery run.

Independent dealers are included when their Ontario business and inventory
source can be verified. Restricted, login-only, blocked, or legally uncertain
sources remain visible as registry records but are not crawled.

## Current discovery sources

The current registry is being expanded from authoritative sources rather than
search-result guesses:

- [UCDA member dealer directory](https://ucda.ca/find-a-member-dealer/) — the
  principal independent-dealer discovery source, reported by the directory as
  covering thousands of Ontario members.
- [OMVIC registrant search](https://omvic.powerappsportals.com/registrant-search/)
  — regulatory verification source.
- [Toyota Canada dealer network](https://www.shoptoyota.ca/ontario/en/dealers).
- [Honda Canada dealer locator](https://www.honda.ca/dealer-locator).
- [Ford Canada dealer locator](https://www.ford.ca/dealerships/).
- [OntarioCars.ca](https://www.ontariocars.ca/) — a UCDA member inventory
  destination. Its public site returned HTTP 403 during this evaluation, so it
  is not treated as a source unless an authorized feed or documented
  integration is obtained.

`data/discovery-candidates.json` contains the first manufacturer-locator seed
batch. These records are deliberately `discovered`, not `inventory`: their
websites, inventory endpoints, robots policies, and extraction feasibility must
still be evaluated before collection.

The current working registry also includes live sources in London discovered
through direct website evaluation: 5 Star Dealers and Titanium Auto. Their
public Zop Software/Typesense indexes returned 332 and 69 records respectively
on 2026-10-25. The registry records those sources as `inventory`; it does not
generalize that result to other dealers using similar-looking websites.

UCDA's current directory requires an interactive Cloudflare Turnstile challenge
for searches. OMVIC's public portal is also an interactive consumer search and
does not expose a documented bulk API. The project must not bypass those
controls or scrape around them. A repeatable full-population import requires
an authorized export/feed or a permitted directory integration; until then,
manufacturer locators and individually verified dealership sites remain
separate provenance classes.

## Discovery deliverable

Phase 2 should commit registry metadata and evidence links, then demonstrate
real discovery output. It must report counts by status, platform, municipality,
and freshness. It must not report “complete Ontario coverage” without a
reproducible source inventory and gap analysis.

## Automated province-wide seed

[OpenStreetMap Ontario dealership geography](https://www.openstreetmap.org/copyright)
is used as the automated province-wide seed layer under ODbL. Published uses
retain “© OpenStreetMap contributors” attribution. The discovery command
queries the complete Ontario area rather than a hand-picked municipality list.

## Reproducible expansion run

On 2026-10-25, `ontario-auto-index discover` examined 1,806 Ontario `shop=car`
features. Of those, 416 supplied a website and domain deduplication produced a
417-record registry including pre-existing records. Verification produced:

- 282 `verified`, 4 existing `inventory`, 24 `unsupported`, 105 `broken`, and
  2 `restricted` records across 65 municipalities;
- 27 dealers successfully ingested through currently supported adapters;
- 1,139 real vehicle records published from those 27 dealers, including 1,009
  records with source-published photos;
- 259 selected dealers failed ingestion, primarily because their AutoSync,
  D2C Media, remaining HTML/JSON-LD, or unknown platforms still
  need dedicated adapters.

These are measured results, not coverage claims. The 500 verified-record goal
and 100 successfully ingested-dealer goal are not yet complete. The
1,000-listing milestone has been exceeded without generating synthetic records.

```powershell
ontario-auto-index --database data/registry.sqlite3 discover
ontario-auto-index --database data/registry.sqlite3 verify --status discovered --concurrency 12
ontario-auto-index --database data/registry.sqlite3 report
ontario-auto-index --database data/registry.sqlite3 ingest --dealer all --output data/all-vehicles.json
```
