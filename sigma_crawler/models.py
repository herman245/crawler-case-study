from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ProductVariant:
    """A purchasable variant of a product (e.g., a specific package size)."""

    price: Decimal
    currency: str
    package_size: str | None = None
    material_number: str | None = None


@dataclass
class ProductItem:
    """
    Structured product data returned by the crawler.

    The _metadata field can be used to carry over intermediate data between
    crawler phases (e.g., identifiers needed for a follow-up pricing request).
    It is not part of the final output.
    """

    name: str
    url: str | None = None
    image_url: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    vendor_product_number: str | None = None
    manufacturer_name: str | None = None
    variants: list[ProductVariant] = field(default_factory=list)
    _metadata: dict = field(default_factory=dict, repr=False)
