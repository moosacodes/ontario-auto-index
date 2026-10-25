from ontario_auto_index.discovery import canonical_domain, deduplicate_dealers
from ontario_auto_index.registry import Dealer, identify_platform


def dealer(dealer_id: str, website: str, municipality: str = "Ontario") -> Dealer:
    return Dealer(
        dealer_id=dealer_id,
        name=dealer_id,
        municipality=municipality,
        website_url=website,
        inventory_url=website,
        discovery_source_url="https://www.openstreetmap.org/node/1",
        adapter_key=None,
        status="discovered",
    )


def test_canonical_domain_normalizes_common_variants() -> None:
    assert canonical_domain("https://www.Example.ca/inventory") == "example.ca"


def test_discovery_deduplicates_domains_and_keeps_richer_location() -> None:
    records = deduplicate_dealers([
        dealer("first", "https://example.ca", "Ontario"),
        dealer("second", "https://www.example.ca/cars", "Ottawa"),
    ])
    assert len(records) == 1
    assert records[0].municipality == "Ottawa"


def test_platform_fingerprints_cover_common_dealer_vendors() -> None:
    assert identify_platform('<script src="https://cdn.d2cmedia.ca/app.js"></script>') == "d2cmedia"
    assert identify_platform('<div class="vehicle-card" data-vin="1"></div>') == "html-inventory"
