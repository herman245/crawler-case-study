# Sigma-Aldrich Product Search Crawler

## Overview

Build a product search crawler for [sigmaaldrich.com](https://www.sigmaaldrich.com) that searches for chemical/lab products and returns structured results **including pricing information**.

You will implement **two versions** of the crawler, each with a different approach to handling product variants (package sizes).

## Context

We build product search integrations for e-procurement platforms. A very common pattern across e-commerce sites is that product catalogs expose APIs behind the scenes, but pricing is loaded separately — it doesn't come back with the initial search results.

Your task is to **reverse-engineer** the Sigma-Aldrich website to discover how it loads search results and pricing, then implement two crawler versions that handle this differently.

## The Task

### Version 1: Fast / Lazy Loading — `crawler_fast.py`

Implement the `SigmaAldrichCrawlerFast` class with two methods:

- `search()` — returns products **immediately**, without prices or variants
- `fetch_prices()` — enriches those products with pricing and variant data

This simulates a UI where search results appear instantly, then prices load in asynchronously.

### Version 2: Expanded — `crawler_expanded.py`

Implement the `SigmaAldrichCrawlerExpanded` class with one method:

- `search()` — returns **one ProductItem per purchasable variant**, each with its own SKU (material number) and price already set

A single catalog product with 5 package sizes becomes 5 separate `ProductItem` objects.

### Shared Requirements

1. **Search for products** given a search term and a country code (e.g., `"US"`, `"DE"`)
2. **Fetch pricing** — prices are **not** included in search results and must be fetched separately
3. **Return structured data** matching the models in `models.py`
4. **Construct product URLs** from the API response data
5. Fetch prices **in parallel** where possible
6. **Exclude** products/variants that have no pricing available or are not available to be bought because of order availability

### Example

For `("acetone", "US")`:

**Version 1 (Fast)** returns items like:

```
[179124] Acetone
  Price:    75.6 USD
  Variants: 179124-500ML (500 mL), 179124-1L (1 L), 179124-2.5L (2.5 L), ...
```

**Version 2 (Expanded)** returns separate items like:

```
[179124-500ML] Acetone - 500 mL    → 75.6 USD
[179124-1L]    Acetone - 1 L       → 110 USD
[179124-2.5L]  Acetone - 2.5 L     → 170 USD
...
```

*(Actual values may differ.)*

## Deliverables

1. *Completed `crawler_fast.py*`* and `crawler_expanded.py`
2. **Brief notes** (in a separate `NOTES.md`) covering:
  - Your general approach to reverse-engineering the search
  - Explanation of the decision you made for the crawlers
  - Edge cases you noticed or handled
  - **Logged-in user scenario:** Imagine a customer has negotiated custom prices with the supplier. When they log in to the shop, they see different prices (and possibly different products) than the public catalog. We would give you a URL containing a session ID that opens the shop already logged in as that customer. How would you adapt your crawler to return the customer-specific products and prices instead of the public ones? Describe how you would need to change your implementation and how much farther you might need to reverse-engineer the search of the shop to have the crawler return those customer-specific products.

## Evaluation Criteria

- **Does it work?** — Both versions produce correct results for both test cases
- **Code quality** — Clean, readable, well-structured code
- **Efficiency** — Parallel price fetching, not unnecessarily sequential
- **Error handling** — Graceful handling of missing data, failed requests
- **Communication** — Clear notes about your approach and decisions

