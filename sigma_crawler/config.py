import os

LANG = "en"
PRICE_CONCURRENCY = int(os.getenv("PRICE_CONCURRENCY", "10"))

BASE_URL = "https://www.sigmaaldrich.com"
PRICING_URL = f"{BASE_URL}/api?operation=PricingAndAvailability"

BROWSER_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}
