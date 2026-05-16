import argparse
import json
import logging
import sys
from config import CITIES
from scrapers.getir_yemek import GetirYemekScraper
from scrapers.yemeksepeti import YemeksepetScraper
from utils.file_handler import FileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

SCRAPERS = {
    "getir_yemek": GetirYemekScraper,
    "yemeksepeti": YemeksepetScraper,
    # "trendyol_yemek": TrendyolScraper,
}


def run(sources: list, cities: list, incremental: bool):
    file_handler = FileHandler()

    for source_name in sources:
        scraper_cls = SCRAPERS.get(source_name)
        if not scraper_cls:
            logger.error(f"Unknown source: {source_name}")
            continue

        scraper = scraper_cls()
        logger.info(f"=== Starting {source_name} ===")

        for city in cities:
            coords = CITIES.get(city.lower())
            if not coords:
                logger.error(f"Unknown city: {city}. Available: {list(CITIES.keys())}")
                continue

            result = scraper.scrape_city(
                city=city,
                lat=coords["lat"],
                lng=coords["lng"],
                incremental=incremental,
            )

            if result and result.restaurants:
                logger.info(f"Saved {len(result.restaurants)} restaurants to output/{city}/{source_name}/")
            else:
                logger.warning(f"No data for {source_name}/{city}")


# Cookie acceptance button texts (Turkish + English)
_COOKIE_ACCEPT_TEXTS = ["kabul et", "tümünü kabul et", "accept", "accept all", "tamam", "anladım", "onay"]


def _dismiss_cookie_modal(page):
    """Attempts to automatically close the cookie consent modal."""
    try:
        # Try by button text
        for text in _COOKIE_ACCEPT_TEXTS:
            btn = page.get_by_role("button", name=text, exact=False)
            if btn.count() > 0:
                btn.first.click()
                print("  [cookie] Modal dismissed automatically")
                page.wait_for_timeout(1000)
                return

        # Fallback: search by CSS selectors
        for selector in [
            "[data-testid='cookie-accept']",
            "[class*='cookie'] button",
            "[class*='Cookie'] button",
            "[class*='consent'] button",
            "button[class*='accept']",
        ]:
            if page.locator(selector).count() > 0:
                page.locator(selector).first.click()
                print("  [cookie] Modal dismissed (CSS)")
                page.wait_for_timeout(1000)
                return
    except Exception:
        pass  # No modal — this is normal


def _fill_yemeksepeti_location(page, city: str):
    """
    Yemeksepeti requires selecting an address before showing restaurants.
    Finds the address search field, enters the city name and selects the first suggestion.
    """
    # Common Turkish city names for autocomplete
    city_tr = {
        "istanbul": "İstanbul",
        "ankara": "Ankara",
        "izmir": "İzmir",
        "bursa": "Bursa",
        "antalya": "Antalya",
    }.get(city.lower(), city.capitalize())

    try:
        # Try multiple possible address input selectors
        input_selectors = [
            "input[placeholder*='adres']",
            "input[placeholder*='Adres']",
            "input[placeholder*='konum']",
            "input[placeholder*='Nereye']",
            "input[data-testid*='address']",
            "input[data-testid*='location']",
            "input[type='search']",
            "input[type='text']",
        ]
        inp = None
        for sel in input_selectors:
            loc = page.locator(sel).first
            if loc.count() > 0:
                try:
                    loc.wait_for(state="visible", timeout=3000)
                    inp = loc
                    print(f"  [address] Input field found: {sel}")
                    break
                except Exception:
                    pass

        if inp is None:
            print("  [address] Address input not found — waiting for page to load")
            return

        inp.click()
        page.wait_for_timeout(500)
        inp.fill(city_tr)
        page.wait_for_timeout(2000)

        # Select the first suggestion
        suggestion_selectors = [
            "[data-testid*='suggestion']:first-child",
            "[class*='suggestion']:first-child",
            "[class*='autocomplete'] li:first-child",
            "[role='option']:first-child",
            "[class*='Suggestion']:first-child",
            "ul li:first-child",
        ]
        clicked = False
        for sel in suggestion_selectors:
            try:
                sugg = page.locator(sel).first
                if sugg.count() > 0:
                    sugg.wait_for(state="visible", timeout=2000)
                    sugg.click()
                    print(f"  [address] First suggestion selected ({sel})")
                    clicked = True
                    break
            except Exception:
                pass

        if not clicked:
            # Fallback: press Enter
            inp.press("Enter")
            print("  [address] Enter pressed as fallback")

        page.wait_for_timeout(3000)

    except Exception as e:
        print(f"  [address] Error filling address: {e}")


def run_discovery(city: str, manual_api_url: str = None, source: str = "getir_yemek"):
    """
    Opens a browser, captures API requests, automatically detects endpoints
    and updates the config. After successful discovery, immediately runs the scraper.
    """
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        print("Playwright is not installed. Run the following commands:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return

    from utils import auto_configure

    coords = CITIES.get(city.lower())
    if not coords:
        print(f"Unknown city: {city}. Available: {list(CITIES.keys())}")
        return

    FileHandler()  # ensure output/ folder exists
    captured = []

    # Domains to skip (analytics, ads, static content)
    SKIP_DOMAINS = {
        "google-analytics.com", "googletagmanager.com", "facebook.com",
        "amplitude.com", "segment.com", "sentry.io", "datadog-browser",
        "hotjar.com", "mixpanel.com", "intercom.io", "cloudfront.net",
        "cdn.", "fonts.googleapis.com", "firebase", "appsflyer.com",
    }

    print(f"\nOpening browser for city: {city}...")
    print("The page will load automatically (~25 seconds).\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        def on_response(response):
            url = response.url
            if any(skip in url for skip in SKIP_DOMAINS):
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            if response.status == 200:
                try:
                    body = response.json()
                    entry = {
                        "url": url,
                        "method": response.request.method,
                        "request_headers": dict(response.request.headers),
                        "status": response.status,
                        "response_body": body,
                    }
                    captured.append(entry)
                    print(f"  [captured] {response.request.method} {url}")
                except Exception:
                    pass

        page.on("response", on_response)

        # Build city-specific URLs
        if source == "yemeksepeti":
            city_urls = [
                f"https://www.yemeksepeti.com/{city.lower()}/",
                f"https://www.yemeksepeti.com/{city.lower()}",
                f"https://www.yemeksepeti.com/",
            ]
        else:
            city_urls = [
                f"https://getir.com/yemek/restoranlar/{city.lower()}/",
                f"https://getir.com/yemek/restoranlar/",
                f"https://www.getir.com/yemek/restoranlar/{city.lower()}/",
            ]

        connected = False
        for site_url in city_urls:
            try:
                print(f"  Trying {site_url} ...")
                page.goto(site_url, timeout=20000)

                page.wait_for_timeout(3000)
                _dismiss_cookie_modal(page)

                if source == "yemeksepeti":
                    _fill_yemeksepeti_location(page, city)
                    page.wait_for_timeout(8000)
                else:
                    page.wait_for_timeout(15000)

                connected = True
                print(f"  Loaded successfully: {site_url}\n")
                break
            except PlaywrightError as e:
                if "ERR_CONNECTION_REFUSED" in str(e) or "ERR_NAME_NOT_RESOLVED" in str(e):
                    print(f"  Unreachable: {site_url}")
                elif "Timeout" in str(e):
                    connected = True
                    print(f"  Loaded with timeout: {site_url}\n")
                    break
                else:
                    print(f"  Error ({site_url}): {e}")

        try:
            browser.close()
        except Exception:
            pass

    site_label = "Yemeksepeti" if source == "yemeksepeti" else "GetirYemek"
    if not connected:
        print(f"\n[!] None of the {site_label} addresses are reachable.")
        print("    Possible solutions:")
        print("    1. Use a Turkish VPN/proxy")
        print("    2. Check your internet connection")
        print("\n    Alternative: Open the site manually in Chrome,")
        print("    press F12 → Network → XHR, find restaurant request,")
        print("    copy the URL and run:")
        print(f"      python main.py --discover --sources {source} --api-url <URL> --cities {city}")
        return

    print(f"\nTotal captured API calls: {len(captured)}")

    # Save for debugging
    debug_path = f"output/discovery_debug_{source}.json"
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(captured, f, ensure_ascii=False, indent=2)

    # Auto configure
    if manual_api_url:
        success = auto_configure.configure_from_url(manual_api_url, captured, source=source)
    else:
        success = auto_configure.analyze_and_configure(captured, source=source)

    if success:
        print(f"\nStarting scraper for {city}...\n")
        import importlib
        import config as cfg
        importlib.reload(cfg)
        run(sources=[source], cities=[city], incremental=False)
    else:
        print(f"\nDebug file saved: {debug_path}")
        print("You can run manually with:")
        print(f"  python main.py --discover --sources {source} --api-url <URL> --cities {city}")


def main():
    parser = argparse.ArgumentParser(
        description="Scraper for Turkish food delivery services (Getir Yemek, Yemeksepeti, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First run — discover APIs and scrape:
  python main.py --discover --cities istanbul

  # Scrape multiple cities (after initial setup):
  python main.py --cities istanbul ankara izmir

  # Force full re-scrape:
  python main.py --cities istanbul --no-incremental

  # Manual API URL (if auto-discovery fails):
  python main.py --discover --api-url https://food-client-api-gateway.getirapi.com/restaurants --cities istanbul
        """,
    )
    parser.add_argument(
        "--sources", nargs="+", default=["getir_yemek"],
        choices=list(SCRAPERS.keys()),
        help="Sources to scrape (default: getir_yemek)",
    )
    parser.add_argument(
        "--cities", nargs="+", default=list(CITIES.keys()),
        help=f"Cities to scrape. Available: {list(CITIES.keys())}",
    )
    parser.add_argument(
        "--no-incremental", action="store_true",
        help="Disable incremental mode — re-scrape everything from scratch",
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="Open browser, discover API endpoints and run scraper automatically",
    )
    parser.add_argument(
        "--api-url", dest="api_url", default=None,
        help="Manually specify restaurant API endpoint URL",
    )

    args = parser.parse_args()

    if args.discover:
        city = args.cities[0] if args.cities else "istanbul"
        src = args.sources[0] if args.sources else "getir_yemek"
        run_discovery(city=city, manual_api_url=args.api_url, source=src)
    else:
        run(
            sources=args.sources,
            cities=args.cities,
            incremental=not args.no_incremental,
        )


if __name__ == "__main__":
    main()