import asyncio
import logging

from sigma_crawler.expanded import SigmaAldrichCrawlerExpanded
from sigma_crawler.fast import SigmaAldrichCrawlerFast


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def run_fast():
    print("\n" + "=" * 70)
    print("  VERSION 1: FAST (search first, then lazy-load pricing)")
    print("=" * 70)

    crawler = SigmaAldrichCrawlerFast()

    try:
        for search_term, country_code in [("acetone", "US"), ("sodium chloride", "DE")]:
            print(f"\n--- Searching: '{search_term}' (country: {country_code}) ---\n")

            items = await crawler.search(search_term, country_code)
            print(f"  {len(items)} products found (no prices yet)")

            items = await crawler.fetch_prices(items, country_code)
            print(f"  {len(items)} products after pricing\n")

            for i, item in enumerate(items[:3], 1):
                print(f"  {i}. [{item.vendor_product_number}] {item.name}")
                print(f"     Price: {item.price} {item.currency}")
                if item.variants:
                    print(f"     Variants ({len(item.variants)}):")
                    for v in item.variants[:4]:
                        print(f"       - {v.material_number} | {v.package_size}: {v.price} {v.currency}")
                    if len(item.variants) > 4:
                        print(f"       ... and {len(item.variants) - 4} more")
                print()
    except Exception:
        logging.exception("run_fast failed")
    finally:
        await crawler.close()


async def run_expanded():
    print("\n" + "=" * 70)
    print("  VERSION 2: EXPANDED (each variant is its own product)")
    print("=" * 70)

    crawler = SigmaAldrichCrawlerExpanded()

    try:
        for search_term, country_code in [("acetone", "US"), ("sodium chloride", "DE")]:
            print(f"\n--- Searching: '{search_term}' (country: {country_code}) ---\n")

            items = await crawler.search(search_term, country_code)
            print(f"  {len(items)} individual items returned\n")

            for i, item in enumerate(items[:8], 1):
                print(f"  {i}. [{item.vendor_product_number}] {item.name}")
                print(f"     Price: {item.price} {item.currency}")
                print()

            if len(items) > 8:
                print(f"  ... and {len(items) - 8} more\n")
    except Exception:
        logging.exception("run_expanded failed")
    finally:
        await crawler.close()


async def main():
    await run_fast()
    await run_expanded()


if __name__ == "__main__":
    asyncio.run(main())
