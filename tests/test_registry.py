from pathlib import Path

from ontario_auto_index.registry import Dealer, DealerRegistry, identify_platform


def test_registry_persists_and_exports_dealers(tmp_path: Path) -> None:
    registry = DealerRegistry(tmp_path / "registry.sqlite3")
    dealer = Dealer(
        dealer_id="example",
        name="Example Motors",
        municipality="Toronto",
        website_url="https://example.test",
        inventory_url="https://example.test/inventory",
        discovery_source_url="https://directory.test/example",
        adapter_key=None,
        status="verified",
    )
    registry.upsert(dealer)
    output = tmp_path / "dealers.json"
    registry.export(output)
    imported = DealerRegistry(tmp_path / "other.sqlite3")
    assert imported.import_file(output) == 1
    assert imported.all()[0].name == "Example Motors"


def test_platform_identification_is_evidence_based() -> None:
    assert identify_platform('"TYPESENSE_HOST": "search.example" "zopsoftware"') == "zopsoftware-typesense"
    assert identify_platform("<html></html>") == "unknown"
