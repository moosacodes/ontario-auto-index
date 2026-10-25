import asyncio
from pathlib import Path

import httpx

from ontario_auto_index.adapters import DealerCityAdapter, _image_urls, _zop_config, extract_json_ld


def test_zop_configuration_is_read_from_page() -> None:
    html = Path("tests/fixtures/zop_inventory.html").read_text(encoding="utf-8")
    config = _zop_config(html)
    assert config["collection"] == "collection-id"
    assert config["host"] == "search.example.test"
    assert config["image_domain"] == ""


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


def test_dealercity_adapter_uses_public_inventory_fields_and_detail_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/listing"):
            return httpx.Response(200, json={
                "vehicles": [{
                    "vehicleId": 123, "serialNo": "1HGCM82633A004352", "year": 2022,
                    "make": {"slug": "honda", "name": "Honda"},
                    "model": {"slug": "civic", "name": "Civic"}, "trim": "EX",
                    "salePrice": 25000, "odometer": 12345,
                    "multimedia": {"picturesWithCompleteUrl": ["https://img.test/car.jpg"]},
                    "bodyStyle": {"name": "Sedan"}, "exteriorColor": {"colorDescription": "Blue"},
                    "fuel": {"name": "Gasoline"}, "transmission": "Automatic",
                    "driveTrain": "Front Wheel Drive", "primaryOrganizationUnit": {"city": "Ottawa"},
                }],
                "pagination": {"numberOfPages": 1},
            })
        return httpx.Response(200, text='<title>Example Motors</title><div data-listing-api-url="/en/used-inventory/api/listing"></div>')

    async def run() -> list:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await DealerCityAdapter(client).listings("https://dealer.test/en/used-inventory")
        finally:
            await client.aclose()

    records = asyncio.run(run())
    assert records[0].original.price == "25000"
    assert records[0].original.mileage == "12345"
    assert records[0].image_urls == ("https://img.test/car.jpg",)
    assert records[0].listing_url.endswith("/2022-honda-civic-id123")


def test_image_extraction_uses_platform_asset_host_for_relative_paths() -> None:
    item = {"image_urls": "/upload/collection/vehicle.jpg"}
    assert _image_urls(item, "https://assets.example.test") == (
        "https://assets.example.test/upload/collection/vehicle.jpg",
    )
