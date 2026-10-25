from pathlib import Path

from ontario_auto_index.adapters import _image_urls, _zop_config, extract_json_ld


def test_zop_configuration_is_read_from_page() -> None:
    html = Path("tests/fixtures/zop_inventory.html").read_text(encoding="utf-8")
    config = _zop_config(html)
    assert config["collection"] == "collection-id"
    assert config["host"] == "search.example.test"


def test_json_ld_extraction_ignores_non_json_scripts() -> None:
    html = Path("tests/fixtures/zop_inventory.html").read_text(encoding="utf-8")
    assert extract_json_ld(html)[0]["@type"] == "WebPage"


def test_image_extraction_normalizes_gallery_urls() -> None:
    item = {"images": "/one.jpg; /two.jpg|https://cdn.test/three.jpg"}
    assert _image_urls(item, "https://dealer.test/inventory/") == (
        "https://dealer.test/one.jpg",
        "https://dealer.test/two.jpg",
        "https://cdn.test/three.jpg",
    )
