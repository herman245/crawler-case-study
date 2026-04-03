import json
import re
from html import unescape
from urllib.parse import urljoin

from .config import BROWSER_HEADERS
from .models import ProductItem


PRICING_QUERY = """query PricingAndAvailability($productNumber: String!, $brand: String, $quantity: Int!, $catalogType: CatalogType, $checkForPb: Boolean, $orgId: String, $materialIds: [String!], $dealerId: String, $checkBuyNow: Boolean, $productKey: String, $erp_type: [String!], $cachedPriceOnly: Boolean) {
  getPricingForProduct(
    input: {productNumber: $productNumber, brand: $brand, quantity: $quantity, catalogType: $catalogType, checkForPb: $checkForPb, orgId: $orgId, materialIds: $materialIds, dealerId: $dealerId, checkBuyNow: $checkBuyNow, productKey: $productKey, erp_type: $erp_type, cachedPriceOnly: $cachedPriceOnly}
  ) {
    materialPricing {
      currency
      listPriceCurrency
      listPrice
      materialNumber
      netPrice
      packageSize
      packageType
      price
      vendorSKU
      isBlockedProduct
      hidePriceMessageKey
    }
  }
}"""
NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)
BRAND_KEY_TO_URL_SEGMENT = {
    "SIGALD": "sigald",
    "SIAL": "sial",
    "SIGMA": "sigma",
    "MM": "mm",
}


def build_default_headers() -> dict[str, str]:
    return dict(BROWSER_HEADERS)


def extract_next_data_from_html(html_text: str) -> dict:
    match = NEXT_DATA_RE.search(html_text)
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ in HTML")
    return json.loads(unescape(match.group(1)))


def find_value_for_key(value, target_key: str):
    if isinstance(value, dict):
        if target_key in value:
            return value[target_key]
        for nested_value in value.values():
            found = find_value_for_key(nested_value, target_key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_value_for_key(item, target_key)
            if found is not None:
                return found
    return None


def first_non_empty(*values):
    for value in values:
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        elif value is not None:
            return value
    return None


def first_image_url(images) -> str | None:
    if not isinstance(images, list):
        return None
    for image in images:
        if not isinstance(image, dict):
            continue
        url = image.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def normalize_product_url(base_url: str, url: str | None, country_code: str) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if not url.startswith("/"):
        url = f"/{country_code}/en/product/{url}"
    return urljoin(base_url, url)


def normalize_image_url(base_url: str, url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(base_url, url)


def build_product_url_from_metadata(
    brand_key: str | None,
    product_key: str | None,
    country_code: str,
) -> str | None:
    if not brand_key or not product_key:
        return None

    brand_segment = BRAND_KEY_TO_URL_SEGMENT.get(str(brand_key).upper())
    if not brand_segment:
        return None

    normalized_product_key = str(product_key).strip()
    if not normalized_product_key:
        return None

    return f"/{country_code}/en/product/{brand_segment}/{normalized_product_key}"


def build_product_metadata(product: dict, product_key: str | None) -> dict:
    return {
        "material_ids": product.get("materialIds") or [],
        "brand_key": product.get("brandKey"),
        "catalog_type": product.get("catalogId"),
        "product_key": product_key,
        "erp_type": product.get("erp_type") or [],
    }


def dedupe_key(item: ProductItem) -> tuple[str | None, str | None, str | None]:
    return (item.vendor_product_number, item.name, item.url)


def extract_material_pricing(payload: dict) -> list[dict]:
    data_root = payload.get("data")
    if not isinstance(data_root, dict):
        return []

    pricing_root = data_root.get("getPricingForProduct")
    if not isinstance(pricing_root, dict):
        return []

    material_pricing = pricing_root.get("materialPricing")
    if not isinstance(material_pricing, list):
        return []

    return [material for material in material_pricing if isinstance(material, dict)]
