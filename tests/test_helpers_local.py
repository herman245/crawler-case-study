from sigma_crawler.helpers import (
    build_product_metadata,
    build_product_url_from_metadata,
    normalize_image_url,
    normalize_product_url,
)

BASE_URL = "https://www.sigmaaldrich.com"


def test_build_product_url_from_metadata_generates_expected_path():
    url = build_product_url_from_metadata(
        brand_key="SIGALD",
        product_key="270725",
        country_code="DE",
    )
    assert url == "/DE/en/product/sigald/270725"


def test_normalize_product_url_converts_relative_to_absolute():
    absolute = normalize_product_url(BASE_URL, "sial/270725", "US")
    assert absolute == "https://www.sigmaaldrich.com/US/en/product/sial/270725"


def test_normalize_image_url_keeps_absolute_and_builds_relative():
    from_relative = normalize_image_url(BASE_URL, "/deepweb/assets/img.png")
    from_absolute = normalize_image_url(BASE_URL, "https://cdn.example.com/a.png")

    assert from_relative == "https://www.sigmaaldrich.com/deepweb/assets/img.png"
    assert from_absolute == "https://cdn.example.com/a.png"


def test_build_product_metadata_has_expected_defaults():
    product = {
        "materialIds": ["A", "B"],
        "brandKey": "SIGALD",
        "catalogId": "sial",
    }

    metadata = build_product_metadata(product, product_key="270725")

    assert metadata["material_ids"] == ["A", "B"]
    assert metadata["brand_key"] == "SIGALD"
    assert metadata["catalog_type"] == "sial"
    assert metadata["product_key"] == "270725"
    assert metadata["erp_type"] == []
