import asyncio
import json
import logging
from decimal import Decimal, InvalidOperation
from html import unescape
from pathlib import Path
from urllib.parse import quote

import httpx

from .helpers import (
    PRICING_QUERY,
    build_default_headers,
    build_product_metadata,
    build_product_url_from_metadata,
    dedupe_key,
    extract_material_pricing,
    extract_next_data_from_html,
    find_value_for_key,
    first_image_url,
    first_non_empty,
    normalize_image_url,
    normalize_product_url,
)
from .models import ProductItem, ProductVariant
from . import config


class SigmaAldrichCrawlerFast:
    """
    Fast product search crawler for sigmaaldrich.com.

    Returns search results immediately, then lazily loads pricing/variants
    in a second step. This allows displaying products to the user before
    prices are available.
    """

    BASE_URL = config.BASE_URL
    GRAPHQL_URL = config.PRICING_URL
    SEARCH_TYPES = ("product", "keyword", "cas_number")

    def __init__(self, cookies_path: str | None = None):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            http2=False,
            headers=build_default_headers(),
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.last_response_url: str | None = None
        if cookies_path:
            self.load_cookies_from_file(cookies_path)
            self.logger.info("Loaded cookies from %s", cookies_path)


    async def __aenter__(self):
        return self


    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


    async def search(self, search_term: str, country_code: str) -> list[ProductItem]:
        """
        Search the Sigma-Aldrich catalog and return products immediately.
        Returned products do NOT have prices or variants yet — call
        fetch_prices() to enrich them.
        """
        last_http_error: httpx.HTTPError | None = None
        self.last_response_url = None
        self.logger.info(
            "Starting search term=%r country=%s search_types=%s",
            search_term,
            country_code,
            ",".join(self.SEARCH_TYPES),
        )

        for search_type in self.SEARCH_TYPES:
            url = self._build_search_url(search_term, country_code, search_type)
            self.logger.debug("Trying search_type=%s url=%s", search_type, url)
            await self._prime_session(country_code, url)
            try:
                response = await self.client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                self.logger.warning(
                    "Search request failed search_type=%s term=%r country=%s error=%s",
                    search_type,
                    search_term,
                    country_code,
                    exc,
                )
                last_http_error = exc
                continue

            self.last_response_url = str(response.url)
            self.logger.debug(
                "Search response received search_type=%s status=%s final_url=%s",
                search_type,
                response.status_code,
                response.url,
            )

            payload = extract_next_data_from_html(response.text)
            items = self._extract_products(payload, country_code)
            if items:
                self.logger.info(
                    "Search succeeded term=%r country=%s search_type=%s products=%d",
                    search_term,
                    country_code,
                    search_type,
                    len(items),
                )
                return items

        if last_http_error is not None:
            raise RuntimeError(
                "Sigma-Aldrich dropped or blocked the direct HTTP request. "
                "This is usually an anti-bot / TLS fingerprint / edge protection issue, "
                "not a parsing bug. Use saved page HTML or raw __NEXT_DATA__ instead."
            ) from last_http_error

        return []


    def parse_html(self, html_text: str, country_code: str) -> list[ProductItem]:
        """Parse search results from saved HTML."""
        payload = extract_next_data_from_html(html_text)
        return self._extract_products(payload, country_code)


    def parse_next_data_json(self, next_data_json: str, country_code: str) -> list[ProductItem]:
        """Parse search results from a raw `__NEXT_DATA__` JSON string."""
        payload = json.loads(unescape(next_data_json))
        return self._extract_products(payload, country_code)


    def parse_html_file(self, path: str, country_code: str) -> list[ProductItem]:
        """Parse search results from a saved HTML file."""
        return self.parse_html(Path(path).read_text(encoding="utf-8"), country_code)


    def parse_next_data_file(self, path: str, country_code: str) -> list[ProductItem]:
        """Parse search results from a saved `__NEXT_DATA__` JSON file."""
        return self.parse_next_data_json(Path(path).read_text(encoding="utf-8"), country_code)


    async def fetch_prices(
        self, items: list[ProductItem], country_code: str
    ) -> list[ProductItem]:
        """
        Fetch pricing for the given products. Populates each item's variants
        list and sets its price/currency from the first available variant.
        Products without available pricing are excluded from the result.
        """
        priced_items: list[ProductItem] = []
        self.logger.info(
            "Fetching prices country=%s products=%d",
            country_code,
            len(items),
        )

        pricing_results = await asyncio.gather(
            *(self._fetch_pricing_for_product(item, country_code) for item in items),
            return_exceptions=True,
        )

        for item, pricing_result in zip(items, pricing_results, strict=False):
            if isinstance(pricing_result, Exception):
                self.logger.warning(
                    "Pricing failed for product=%s country=%s error=%s",
                    item.vendor_product_number,
                    country_code,
                    pricing_result,
                )
                continue

            pricing = pricing_result
            if not pricing:
                self.logger.debug(
                    "No pricing found product=%s country=%s",
                    item.vendor_product_number,
                    country_code,
                )
                continue

            item.variants = pricing
            item.price = pricing[0].price
            item.currency = pricing[0].currency
            priced_items.append(item)
            self.logger.debug(
                "Pricing attached product=%s variants=%d first_price=%s %s",
                item.vendor_product_number,
                len(pricing),
                item.price,
                item.currency,
            )

        self.logger.info(
            "Pricing finished country=%s priced_products=%d",
            country_code,
            len(priced_items),
        )
        return priced_items


    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()


    def load_cookies_from_file(self, path: str) -> None:
        """Load browser-exported cookies from a dict or list JSON file."""
        cookie_path = Path(path)
        if not cookie_path.exists():
            raise FileNotFoundError(f"Cookie file not found: {path}")

        with cookie_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        if isinstance(raw, dict):
            self.load_cookies(raw)
            return

        if isinstance(raw, list):
            cookies: dict[str, str] = {}
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("value")
                if name and value is not None:
                    cookies[str(name)] = str(value)
            self.load_cookies(cookies)
            return

        raise ValueError("Unsupported cookies format. Use a dict or a list of browser cookies.")


    def load_cookies(self, cookies: dict[str, str]) -> None:
        """Attach cookies to the Sigma-Aldrich domain."""
        for name, value in cookies.items():
            self.client.cookies.set(name, value, domain=".sigmaaldrich.com", path="/")
        self.logger.debug("Attached %d cookies to client", len(cookies))


    def _build_search_url(
        self, search_term: str, country_code: str, search_type: str = "product"
    ) -> str:
        encoded_term = quote(search_term)
        return (
            f"{self.BASE_URL}/{country_code}/en/search/{encoded_term}"
            f"?focus=products&page=1&perpage=30&sort=relevance"
            f"&term={encoded_term}&type={search_type}"
        )


    def _extract_products(self, payload: dict, country_code: str) -> list[ProductItem]:
        products = self._extract_products_from_new_search(payload)
        if not products:
            products = self._extract_products_from_apollo_state(payload)

        seen: set[tuple[str | None, str | None, str | None]] = set()
        items: list[ProductItem] = []

        for product in products:
            item = self._product_from_json(product, country_code)
            if item is None:
                continue

            if dedupe_key(item) in seen:
                continue
            seen.add(dedupe_key(item))
            items.append(item)

        return items


    def _extract_products_from_new_search(self, payload: dict) -> list[dict]:
        result = find_value_for_key(payload, "getNewProductSearchResults")
        if isinstance(result, dict):
            products = result.get("products")
            if isinstance(products, list):
                return [p for p in products if isinstance(p, dict)]
        return []


    def _extract_products_from_apollo_state(self, payload: dict) -> list[dict]:
        apollo_state = find_value_for_key(payload, "apolloState")
        if not isinstance(apollo_state, dict):
            return []

        containers: list[dict] = [apollo_state]
        root_query = apollo_state.get("ROOT_QUERY")
        if isinstance(root_query, dict):
            containers.insert(0, root_query)

        for container in containers:
            for key, value in container.items():
                if not isinstance(value, dict):
                    continue

                if key.startswith("getNewProductSearchResults"):
                    products = value.get("products")
                    if isinstance(products, list):
                        return [p for p in products if isinstance(p, dict)]

                if key.startswith("getProductSearchResults"):
                    products = value.get("items")
                    if isinstance(products, list):
                        return [p for p in products if isinstance(p, dict)]

        return []


    def _product_from_json(self, product: dict, country_code: str) -> ProductItem | None:
        name = first_non_empty(
            product.get("name"),
            product.get("title"),
            product.get("productName"),
            product.get("productTitle"),
        )
        vendor_product_number = first_non_empty(
            product.get("productNumber"),
            product.get("materialNumber"),
            product.get("material_number"),
            product.get("sku"),
            product.get("id"),
        )
        product_key = first_non_empty(
            product.get("productKey"),
            vendor_product_number,
        )
        url = normalize_product_url(
            self.BASE_URL,
            first_non_empty(
                product.get("url"),
                product.get("productUrl"),
                product.get("pdpUrl"),
                product.get("seoUrl"),
                product.get("href"),
                build_product_url_from_metadata(
                    product.get("brandKey"),
                    product_key,
                    country_code,
                ),
            ),
            country_code,
        )
        image_url = normalize_image_url(
            self.BASE_URL,
            first_non_empty(
                product.get("imageUrl"),
                product.get("thumbnailUrl"),
                product.get("image"),
                product.get("imgUrl"),
                first_image_url(product.get("images")),
            )
        )
        description = first_non_empty(
            product.get("description"),
            product.get("shortDescription"),
            product.get("subtitle"),
            product.get("nameSuffix"),
            product.get("productNameSuffix"),
        )
        manufacturer_name = first_non_empty(
            product.get("brand"),
            product.get("brandName"),
            product.get("manufacturer"),
            product.get("manufacturerName"),
        )

        if not any([name, vendor_product_number, url]):
            return None

        return ProductItem(
            name=name or vendor_product_number or "Unknown product",
            url=url,
            image_url=image_url,
            description=description,
            vendor_product_number=vendor_product_number,
            manufacturer_name=manufacturer_name,
            _metadata=build_product_metadata(product, product_key),
        )

    async def _prime_session(self, country_code: str, search_url: str) -> None:
        """Warm up the session so subsequent search/pricing calls inherit site context."""
        self.logger.debug("Priming session country=%s search_url=%s", country_code, search_url)
        self.client.headers["referer"] = f"{self.BASE_URL}/{country_code}/en"
        self._set_country_context(country_code)

        try:
            await self.client.get(f"{self.BASE_URL}/{country_code}/en")
        except httpx.HTTPError as exc:
            self.logger.debug("Session prime step 1 failed country=%s error=%s", country_code, exc)
            return

        try:
            await self.client.get(
                f"{self.BASE_URL}/{country_code}/en/search",
                headers={
                    "sec-fetch-site": "same-origin",
                    "referer": f"{self.BASE_URL}/{country_code}/en",
                },
            )
        except httpx.HTTPError as exc:
            self.logger.debug("Session prime step 2 failed country=%s error=%s", country_code, exc)
            return

        self.client.headers["referer"] = search_url

    def _set_country_context(self, country_code: str) -> None:
        self.client.cookies.set("country", country_code, domain=".sigmaaldrich.com", path="/")
        self.client.cookies.set("language", "en", domain=".sigmaaldrich.com", path="/")


    async def _fetch_pricing_for_product(
        self, item: ProductItem, country_code: str
    ) -> list[ProductVariant]:
        """Fetch purchasable material variants for a single catalog product."""
        product_number = item.vendor_product_number
        if not product_number:
            return []
        self.logger.debug(
            "Fetching pricing product=%s country=%s",
            product_number,
            country_code,
        )

        self._set_country_context(country_code)

        payload = self._build_pricing_payload(item, product_number)
        headers = dict(self.client.headers)
        headers.update(self._build_pricing_headers(item, country_code))

        response = await self.client.post(self.GRAPHQL_URL, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "Pricing request failed product=%s country=%s status=%s",
                product_number,
                country_code,
                response.status_code,
            )
            raise RuntimeError(
                f"Pricing request failed for {product_number} with status "
                f"{response.status_code}. Response body: {response.text[:1500]}"
            ) from exc

        variants = [
            variant
            for material in extract_material_pricing(response.json())
            if (variant := self._variant_from_material_pricing(material)) is not None
        ]

        self.logger.debug(
            "Pricing response parsed product=%s variants=%d",
            product_number,
            len(variants),
        )
        return variants


    def _build_pricing_payload(self, item: ProductItem, product_number: str) -> dict:
        """Build the GraphQL body for a single product pricing lookup."""
        variables = {
            "productNumber": product_number,
            "brand": item._metadata.get("brand_key"),
            "quantity": 1,
            "catalogType": item._metadata.get("catalog_type"),
            "orgId": None,
            "checkForPb": True,
            "dealerId": "",
            "checkBuyNow": True,
            "productKey": item._metadata.get("product_key"),
            "cachedPriceOnly": False,
        }

        material_ids = item._metadata.get("material_ids") or []
        if material_ids:
            variables["materialIds"] = material_ids

        erp_type = item._metadata.get("erp_type") or []
        if erp_type:
            variables["erp_type"] = erp_type

        return {
            "operationName": "PricingAndAvailability",
            "query": PRICING_QUERY,
            "variables": variables,
        }


    def _build_pricing_headers(self, item: ProductItem, country_code: str) -> dict[str, str]:
        """Build the browser-like headers required by the pricing endpoint."""
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "origin": self.BASE_URL,
            "referer": self.last_response_url
            or f"{self.BASE_URL}/{country_code}/en/search/{quote(item.name)}",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-gql-country": country_code,
            "x-gql-language": "en",
            "x-gql-operation-name": "PricingAndAvailability",
            "x-gql-requesting-website": "SigmaAldrich",
            "x-gql-store": item._metadata.get("catalog_type") or "sial",
            "x-gql-user-erp-type": "ANONYMOUS",
        }

        access_token = self.client.cookies.get("accessToken")
        if access_token:
            headers["x-gql-access-token"] = access_token

        profile_token = self.client.cookies.get("profileToken")
        if profile_token:
            headers["x-gql-profile-token"] = profile_token

        return headers

    def _variant_from_material_pricing(self, material: dict) -> ProductVariant | None:
        """Convert one pricing material entry into a normalized variant."""
        if not isinstance(material, dict):
            return None
        if material.get("isBlockedProduct"):
            return None
        if material.get("hidePriceMessageKey"):
            return None

        price_value = first_non_empty(
            material.get("price"),
            material.get("netPrice"),
            material.get("listPrice"),
        )
        currency = first_non_empty(
            material.get("currency"),
            material.get("listPriceCurrency"),
        )
        if price_value is None or currency is None:
            return None

        try:
            price = Decimal(str(price_value))
        except (InvalidOperation, ValueError) as exc:
            self.logger.debug("Skipping variant with invalid price value=%r error=%s", price_value, exc)
            return None

        return ProductVariant(
            price=price,
            currency=str(currency),
            package_size=first_non_empty(
                material.get("packageSize"),
                material.get("packageType"),
            ),
            material_number=first_non_empty(
                material.get("materialNumber"),
                material.get("vendorSKU"),
            ),
        )
