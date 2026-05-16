import re
import json
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

RESTAURANT_KEYS = {"name", "id", "rating", "restaurantId", "slug", "isOpen", "deliveryFee"}

# Endpoints that match restaurant-list responses but are NOT restaurant lists
_GEOCODER_SKIP = {"cities", "geocode", "autocomplete", "address", "location", "form"}


def analyze_and_configure(captured_calls: list, source: str = "getir_yemek") -> bool:
    """
    Из перехваченных API-вызовов найти эндпоинт ресторанов и обновить config.py.
    Возвращает True если конфигурация успешно обновлена.
    """
    # Yemeksepeti: страница требует выбора адреса, поэтому вендор-API не вызывается
    # во время автодискавери. Вместо этого извлекаем заголовки из любого tr.fd-api.com
    # запроса и прописываем известный эндпоинт.
    if source == "yemeksepeti":
        return _configure_yemeksepeti_from_headers(captured_calls)

    restaurant_call = _find_restaurant_call(captured_calls)
    if not restaurant_call:
        logger.warning("Не удалось автоматически найти эндпоинт ресторанов.")
        _print_all_urls(captured_calls)
        return False

    url = restaurant_call["url"]
    headers = restaurant_call["request_headers"]

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path

    menu_path = _guess_menu_path(path)
    _update_config_file(base_url, path, menu_path, headers, source)

    print(f"\n[OK] Найден эндпоинт ресторанов: {base_url}{path}")
    print(f"[OK] config.py обновлён автоматически.")
    return True


def _configure_yemeksepeti_from_headers(captured_calls: list) -> bool:
    """
    Yemeksepeti использует известные эндпоинты Delivery Hero (tr.fd-api.com).
    Достаточно извлечь заголовки из любого перехваченного tr.fd-api.com запроса.
    """
    FD_API_BASE = "https://tr.fd-api.com"
    VENDORS_PATH = "/api/v5/vendors"
    MENU_PATH = "/api/v5/vendors/{restaurant_id}/menus"

    fd_headers = {}
    for call in captured_calls:
        if "tr.fd-api.com" in call.get("url", ""):
            fd_headers = call.get("request_headers", {})
            break

    if not fd_headers:
        logger.warning("Не найдено ни одного запроса к tr.fd-api.com в перехваченных вызовах.")
        _print_all_urls(captured_calls)
        return False

    # Гарантируем обязательные Delivery Hero заголовки
    fd_headers.setdefault("x-global-entity-id", "YS_TR")
    fd_headers.setdefault("x-caller-country", "tr")
    fd_headers.setdefault("x-caller-platform", "b2c")

    _update_config_file(FD_API_BASE, VENDORS_PATH, MENU_PATH, fd_headers, "yemeksepeti")
    print(f"\n[OK] Yemeksepeti: заголовки извлечены из tr.fd-api.com")
    print(f"[OK] Эндпоинт: {FD_API_BASE}{VENDORS_PATH}")
    print(f"[OK] config.py обновлён автоматически.")
    return True


def configure_from_url(api_url: str, captured_calls: list, source: str = "getir_yemek") -> bool:
    """Ручной override: пользователь указал --api-url напрямую."""
    parsed = urlparse(api_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path
    menu_path = _guess_menu_path(path)

    headers = {}
    for call in captured_calls:
        if parsed.netloc in call.get("url", ""):
            headers = call.get("request_headers", {})
            break

    _update_config_file(base_url, path, menu_path, headers, source)
    print(f"[OK] config.py обновлён с указанным URL: {api_url}")
    return True


def _find_restaurant_call(captured_calls: list) -> dict:
    """Ищет вызов, в ответе которого есть список ресторанов."""
    sorted_calls = sorted(
        captured_calls,
        key=lambda c: len(json.dumps(c.get("response_body", ""))),
        reverse=True,
    )
    for call in sorted_calls:
        # Пропускаем геокодеры и адресные сервисы
        url_lower = call.get("url", "").lower()
        if any(skip in url_lower for skip in _GEOCODER_SKIP):
            continue
        body = call.get("response_body")
        if body and _find_restaurant_list(body):
            return call
    return None


def _find_restaurant_list(data) -> list:
    """Рекурсивно ищет JSON-массив, похожий на список ресторанов."""
    if isinstance(data, list) and len(data) > 5:
        sample = data[0] if data else {}
        if isinstance(sample, dict):
            keys = set(sample.keys())
            if keys & RESTAURANT_KEYS:
                return data
    if isinstance(data, dict):
        for v in data.values():
            result = _find_restaurant_list(v)
            if result:
                return result
    return []


def _guess_menu_path(restaurant_path: str) -> str:
    path = restaurant_path.rstrip("/")
    return f"{path}/{{restaurant_id}}/menu"


def _update_config_file(base_url: str, restaurants_path: str,
                         menu_path: str, headers: dict, source: str):
    """Обновляет config.py для указанного источника (getir_yemek или yemeksepeti)."""
    if source == "yemeksepeti":
        prefix = "YEMEKSEPETI"
    else:
        prefix = "GETIR"

    config_path = "config.py"
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    skip_headers = {":authority", ":method", ":path", ":scheme",
                    "cookie", "sec-fetch-dest", "sec-fetch-mode",
                    "sec-fetch-site", "sec-ch-ua", "sec-ch-ua-mobile",
                    "sec-ch-ua-platform"}
    clean_headers = {
        k: v for k, v in headers.items()
        if k.lower() not in skip_headers
    }

    headers_lines = "\n".join(
        f'    "{k}": "{v}",' for k, v in clean_headers.items()
    )

    new_base = f'{prefix}_API_BASE = "{base_url}"'
    new_endpoints = (
        f'{prefix}_ENDPOINTS = {{\n'
        f'    "restaurants": "{restaurants_path}",\n'
        f'    "restaurant_menu": "{menu_path}",\n'
        f'}}'
    )
    new_headers = (
        f'{prefix}_HEADERS = {{\n'
        + headers_lines + '\n'
        '}'
    )

    # Regex: match from PREFIX_VAR = "..." to end of that string
    content = re.sub(
        rf'{prefix}_API_BASE\s*=\s*"[^"]*"',
        new_base,
        content,
    )
    # For dicts, match from opening { to the first } that starts a line (closing brace)
    content = re.sub(
        rf'{prefix}_ENDPOINTS\s*=\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)?\}}',
        new_endpoints,
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        rf'{prefix}_HEADERS\s*=\s*\{{.*?\n\}}',
        new_headers,
        content,
        flags=re.DOTALL,
    )

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)


def _print_all_urls(captured_calls: list):
    print("\n[!] Автоматическая конфигурация не удалась.")
    print("Все перехваченные API-вызовы:")
    for i, call in enumerate(captured_calls):
        print(f"  {i+1}. {call.get('method', 'GET')} {call.get('url', '')}")
    print("\nНайдите URL со списком ресторанов и запустите:")
    print("  python main.py --discover --api-url <найденный URL> --cities istanbul")
