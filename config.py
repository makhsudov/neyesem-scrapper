CITIES = {
    "istanbul": {"lat": 41.0082, "lng": 28.9784},
    "ankara":   {"lat": 39.9334, "lng": 32.8597},
    "izmir":    {"lat": 38.4192, "lng": 27.1287},
    "bursa":    {"lat": 40.1885, "lng": 29.0610},
    "antalya":  {"lat": 36.8969, "lng": 30.7133},
}

# Fill these after running: python main.py --discover --cities istanbul
GETIR_API_BASE = "https://food-client-api-gateway.getirapi.com"
GETIR_ENDPOINTS = {
    "restaurants":     "/restaurants",
    "restaurant_menu": "/restaurants/{restaurant_id}/menu",
}

GETIR_HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":       "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "x-platform":   "web",
    "x-language":   "tr-TR",
    # "Authorization": "Bearer <token>",  # set after discovery
}

# Fill these after running: python main.py --discover --sources yemeksepeti --cities istanbul
YEMEKSEPETI_API_BASE = "https://tr.fd-api.com"
YEMEKSEPETI_ENDPOINTS = {
    "restaurants": "/api/v5/vendors",
    "restaurant_menu": "/api/v5/vendors/{restaurant_id}/menus",
}

YEMEKSEPETI_HEADERS = {
    "perseus-session-id": "1778944775155.177846743344889345.fmzlpn4lfq",
    "referer": "https://www.yemeksepeti.com/",
    "perseus-client-id": "1778944775154.051585413439588621.nh9gwfsc90",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "x-fp-api-key": "volo",
    "x-global-entity-id": "YS_TR",
    "x-caller-country": "tr",
    "x-caller-platform": "b2c",
}

REQUEST_DELAY_MIN = 1.0
REQUEST_DELAY_MAX = 3.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

OUTPUT_DIR = "output"
SCRAPE_STATE_FILE = "output/.scrape_state.json"
