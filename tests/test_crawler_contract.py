from decimal import Decimal
import os
import pytest
import pytest_asyncio

from sigma_crawler.expanded import SigmaAldrichCrawlerExpanded
from sigma_crawler.fast import SigmaAldrichCrawlerFast
from sigma_crawler.models import ProductItem, ProductVariant


CASE_MATRIX: list[tuple[str, str]] = [
    ("acetone", "US"),
    ("sodium chloride", "DE"),
]

RUN_LIVE = os.getenv("SIGMA_RUN_LIVE_TESTS") == "1"

@pytest_asyncio.fixture
async def fast_client():
    async with SigmaAldrichCrawlerFast() as crawler:
        yield crawler


@pytest_asyncio.fixture
async def expanded_client():
    async with SigmaAldrichCrawlerExpanded() as crawler:
        yield crawler


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_fast_search_returns_unpriced_products(fast_client):
    for query, region in CASE_MATRIX:
        draft_items = await fast_client.search(query, region)

        assert draft_items, f"Expected non-empty search result for {query}/{region}"
        assert all(isinstance(item, ProductItem) for item in draft_items)

        for item in draft_items:
            assert item.name
            assert item.vendor_product_number
            assert item.url
            assert item.price is None
            assert item.variants == []


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_fast_pricing_enrichment_produces_valid_variants(fast_client):
    for query, region in CASE_MATRIX:
        draft_items = await fast_client.search(query, region)
        priced_items = await fast_client.fetch_prices(draft_items, region)

        assert priced_items, f"Expected priced items for {query}/{region}"

        for item in priced_items:
            assert isinstance(item.price, Decimal)
            assert item.price > 0
            assert item.currency
            assert item.variants
            assert item.price == item.variants[0].price
            assert item.currency == item.variants[0].currency

            for variant in item.variants:
                assert isinstance(variant, ProductVariant)
                assert isinstance(variant.price, Decimal)
                assert variant.price > 0
                assert variant.currency


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_expanded_items_are_ready_to_purchase(expanded_client):
    for query, region in CASE_MATRIX:
        flattened = await expanded_client.search(query, region)

        assert flattened, f"Expected expanded output for {query}/{region}"
        assert all(isinstance(item, ProductItem) for item in flattened)

        for item in flattened:
            assert item.vendor_product_number
            assert item.name
            assert item.url
            assert isinstance(item.price, Decimal)
            assert item.price > 0
            assert item.currency
            assert len(item.variants) == 1

            only_variant = item.variants[0]
            assert item.price == only_variant.price
            assert item.currency == only_variant.currency
            if only_variant.package_size:
                assert only_variant.package_size in item.name


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_expanded_count_matches_fast_variant_count(fast_client, expanded_client):
    for query, region in CASE_MATRIX:
        draft_items = await fast_client.search(query, region)
        priced_items = await fast_client.fetch_prices(draft_items, region)
        flattened = await expanded_client.search(query, region)

        variant_total = sum(len(item.variants) for item in priced_items)
        assert len(flattened) == variant_total


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_fast_search_urls_are_absolute(fast_client):
    for query, region in CASE_MATRIX:
        results = await fast_client.search(query, region)
        assert results

        for item in results:
            assert item.url.startswith("https://www.sigmaaldrich.com/")
            assert f"/{region}/en/" in item.url


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_fast_priced_items_are_subset_of_search_items(fast_client):
    for query, region in CASE_MATRIX:
        drafts = await fast_client.search(query, region)
        priced = await fast_client.fetch_prices(drafts, region)

        draft_ids = {item.vendor_product_number for item in drafts}
        priced_ids = {item.vendor_product_number for item in priced}

        assert priced_ids
        assert priced_ids.issubset(draft_ids)


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Set SIGMA_RUN_LIVE_TESTS=1 to run live tests")
@pytest.mark.asyncio
async def test_expanded_vendor_number_matches_single_variant(expanded_client):
    for query, region in CASE_MATRIX:
        rows = await expanded_client.search(query, region)
        assert rows

        for row in rows:
            assert len(row.variants) == 1
            variant = row.variants[0]

            if variant.material_number:
                assert row.vendor_product_number == variant.material_number

            assert row.price == variant.price
            assert row.currency == variant.currency
