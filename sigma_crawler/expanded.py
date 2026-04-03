from .fast import SigmaAldrichCrawlerFast
from .models import ProductItem, ProductVariant


class SigmaAldrichCrawlerExpanded:
    """
    Expanded product search crawler for sigmaaldrich.com.

    Each purchasable variant (package size) is returned as its own
    ProductItem with its own SKU, price, and currency. A single catalog
    product with 5 package sizes becomes 5 separate ProductItems.
    """


    def __init__(self, cookies_path: str | None = None):
        self.fast = SigmaAldrichCrawlerFast(
            cookies_path=cookies_path,
        )
        self.logger = self.fast.logger.getChild("expanded")


    async def __aenter__(self):
        return self


    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


    async def search(self, search_term: str, country_code: str) -> list[ProductItem]:
        """
        Search the Sigma-Aldrich catalog and return one ProductItem per
        purchasable variant. Each item has its own vendor_product_number
        (material number), price, and currency already set.
        """
        self.logger.info(
            "Starting expanded search term=%r country=%s",
            search_term,
            country_code,
        )
        products = await self.fast.search(search_term, country_code)

        priced_products = await self.fast.fetch_prices(products, country_code)

        expanded_items: list[ProductItem] = []
        for product in priced_products:
            variants = self._priced_variants(product)

            if not variants and product.price is not None and product.currency:
                expanded_items.append(
                    ProductItem(
                        name=product.name,
                        url=product.url,
                        image_url=product.image_url,
                        description=product.description,
                        price=product.price,
                        currency=product.currency,
                        vendor_product_number=product.vendor_product_number,
                        manufacturer_name=product.manufacturer_name,
                        _metadata=dict(product._metadata),
                    )
                )
                continue

            for variant in variants:
                metadata = dict(product._metadata)
                metadata["source_product_number"] = product.vendor_product_number
                metadata["variant_material_number"] = variant.material_number
                metadata["variant_package_size"] = variant.package_size

                expanded_items.append(
                    ProductItem(
                        name=self._build_variant_name(product.name, variant.package_size),
                        url=product.url,
                        image_url=product.image_url,
                        description=product.description,
                        price=variant.price,
                        currency=variant.currency,
                        vendor_product_number=variant.material_number
                        or product.vendor_product_number,
                        manufacturer_name=product.manufacturer_name,
                        variants=[variant],
                        _metadata=metadata,
                    )
                )

        self.logger.info(
            "Expanded search finished term=%r country=%s items=%d",
            search_term,
            country_code,
            len(expanded_items),
        )
        return expanded_items


    async def close(self):
        """Close the underlying fast crawler client."""
        await self.fast.close()

    def _priced_variants(self, product: ProductItem) -> list[ProductVariant]:
        """Return only variants that already have price and currency."""
        return [
            variant
            for variant in product.variants
            if isinstance(variant, ProductVariant)
            and variant.price is not None
            and variant.currency
        ]


    def _build_variant_name(self, name: str, package_size: str | None) -> str:
        """Append package size to the display name when useful."""
        if not package_size:
            return name
        if package_size in name:
            return name
        return f"{name} ({package_size})"
