# Notes

## General Reverse-Engineering Approach

I started from the public search results page instead of guessing an internal API immediately.
The search HTML contains a `__NEXT_DATA__` script block with the full Next.js page payload, and that payload includes product search results inside Apollo state.
That made search extraction more stable than scraping rendered DOM elements.

For pricing, I used the browser Network panel and inspected the requests triggered after the search results loaded.
The key finding was that pricing is not part of the search payload and is fetched separately through:

- `POST /api?operation=PricingAndAvailability`

That GraphQL endpoint then fans out internally to Sigma-Aldrich's pricing backend.

Another important part of the reverse-engineering process was reproducing browser-like request context.
Plain raw HTTP requests were not always enough because the site is sensitive to anti-bot / edge validation.
To make requests work more reliably outside the browser, I aligned them with the browser request shape by forwarding:

- country and language cookies
- GraphQL-specific headers such as `x-gql-country`, `x-gql-language`, and `x-gql-operation-name`
- access/profile token headers when present in cookies
- product-specific variables such as `brand`, `catalogType`, `productKey`, and `materialIds`

So the anti-bot handling was mainly done by matching the same session context and browser-like headers the website itself uses.

## Crawler Design Decisions

### `crawler_fast.py`

`SigmaAldrichCrawlerFast` is split into two phases:

- `search()` returns grouped catalog products quickly from `__NEXT_DATA__`
- `fetch_prices()` enriches those products with variant pricing later

This matches the "fast/lazy loading" behavior described in the task and keeps the initial search step independent from pricing.
Each `ProductItem` returned by `search()` keeps intermediate identifiers in `_metadata` so the pricing step can reuse them without reparsing the original response.

### `crawler_expanded.py`

`SigmaAldrichCrawlerExpanded` is built on top of the already working fast crawler instead of duplicating the reverse-engineered request logic.
It:

- performs the same search
- fetches pricing
- expands each purchasable variant into its own `ProductItem`

This keeps the network/request logic shared while exposing a different final data shape.
In other words, both crawler versions use the same underlying HTTP flow, but they present the result differently depending on the use case:

- `fast` is product-oriented
- `expanded` is SKU / variant-oriented

## Edge Cases Noticed / Handled

- Search results are available even when pricing is not, so search and pricing had to be separated.
- The same product can expose many `materialIds`, including duplicate-like identifiers, so deduplication is important.
- GraphQL validation is strict: declaring variables that are not actually used in the query results in a `400` error.
- Pricing requests can fail even with a correct GraphQL body if the country context is missing.
- Some products or variants may not be purchasable, so variants with blocked purchase flags or hidden price messages are excluded.
- Search result payload structure is not fully uniform, so the implementation checks both the newer `getNewProductSearchResults` shape and Apollo state fallbacks.
- The implementation is robust to missing pricing data and returns an empty result for that product instead of crashing.

## Logged-In User / Customer-Specific Pricing Scenario

If I were given a URL that opens the shop already logged in as a customer with negotiated prices, I would adapt the crawler by preserving that authenticated browser session and replaying requests within that context.

In practice, I would do the following:

- open the provided logged-in URL once to establish the authenticated session
- persist all relevant cookies from that session, especially access/profile/session tokens
- reuse those cookies for both search and pricing requests
- keep the GraphQL headers aligned with the authenticated session values, especially:
  - `x-gql-access-token`
  - `x-gql-profile-token`
  - `x-gql-country`
  - `x-gql-language`
  - any customer/account/dealer-specific headers if the site sends them

The pricing portion would likely need little additional reverse-engineering because the public and logged-in flows appear to use the same endpoint family, but with different session context.
The bigger unknown is search: a logged-in account may see additional products, fewer products, or different catalog partitions.
So I would verify whether the logged-in search page still exposes the same `__NEXT_DATA__` / Apollo structure or whether it switches to a different query or adds account-specific variables.

If the logged-in search response differs, I would reverse-engineer:

- which search GraphQL or page-data request is used after login
- whether dealer/account identifiers are injected into the search request
- whether account-specific product visibility is decided during search or only later during pricing

My expectation is:

- pricing adaptation: low to medium extra work
- logged-in search adaptation: medium extra work, depending on whether the page payload shape changes

## Additional Notes

- Price fetching is implemented in parallel to avoid unnecessary sequential pricing requests.
- Product URLs are reconstructed from the response data when direct URL fields are missing by combining country, brand metadata, and product key.
- One remaining polish improvement would be normalizing descriptions further because some source values still contain HTML entities or inline markup.
