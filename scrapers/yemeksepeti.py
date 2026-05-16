import re
import json
import logging
from typing import List, Dict, Optional
from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant, MenuCategory, MenuItem
from config import YEMEKSEPETI_HEADERS, YEMEKSEPETI_API_BASE

logger = logging.getLogger(__name__)

WEB_BASE = "https://www.yemeksepeti.com"


class YemeksepetScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "yemeksepeti"

    def _get_headers(self) -> Dict[str, str]:
        return YEMEKSEPETI_HEADERS.copy()

    # ------------------------------------------------------------------
    # Список ресторанов — REST API Delivery Hero
    # ------------------------------------------------------------------

    def fetch_restaurants(self, lat: float, lng: float, city: str = "") -> List[Restaurant]:
        # Попытка 1: Delivery Hero REST API (tr.fd-api.com/api/v5/vendors)
        from config import YEMEKSEPETI_ENDPOINTS
        api_path = YEMEKSEPETI_ENDPOINTS.get("restaurants", "")
        if api_path:
            # Delivery Hero использует latitude/longitude (не lat/lon)
            params = {"latitude": lat, "longitude": lng, "limit": 200}
            url = f"{YEMEKSEPETI_API_BASE}{api_path}"
            response = self._request("GET", url, params=params)
            if response:
                data = response.json()
                # Delivery Hero v5: { "data": { "items": [...] } } или { "vendors": [...] }
                items = (
                    data.get("data", {}).get("items")
                    or data.get("vendors")
                    or data.get("restaurants")
                    or []
                )
                if isinstance(items, dict):
                    items = items.get("items") or []
                total = (
                    data.get("data", {}).get("total_count")
                    or data.get("total_count")
                    or len(items)
                )
                logger.info(f"Получено {len(items)} из {total} ресторанов (yemeksepeti, API)")
                result = [r for raw in items if (r := self._parse_restaurant(raw, city))]
                if result:
                    return result
                logger.warning("API вернул пустой список — переходим к HTML-скрапингу")

        # Попытка 2: HTML-скрапинг страницы города (fallback)
        return self._fetch_restaurants_html(city, lat, lng)

    def _fetch_restaurants_html(self, city: str, lat: float, lng: float) -> List[Restaurant]:
        """Скрапит список ресторанов из __NEXT_DATA__ страницы города."""
        city_slug = city.lower()
        urls_to_try = [
            f"{WEB_BASE}/{city_slug}/",
            f"{WEB_BASE}/{city_slug}",
            f"{WEB_BASE}/",
        ]
        for url in urls_to_try:
            response = self._request("GET", url, headers={"Accept": "text/html,*/*"})
            if not response:
                continue

            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                response.text, re.DOTALL
            )
            if not match:
                logger.debug(f"__NEXT_DATA__ не найден на {url}")
                continue

            try:
                page_data = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

            page_props = page_data.get("props", {}).get("pageProps", {})
            # Пробуем известные пути
            raw_list = (
                page_props.get("restaurants")
                or page_props.get("initialState", {}).get("restaurants", {}).get("items")
                or page_props.get("restaurantList")
                or self._deep_find_key(page_props, "restaurants")
            )
            if not raw_list:
                logger.debug(f"Список ресторанов не найден в __NEXT_DATA__ на {url}")
                continue

            if isinstance(raw_list, dict):
                raw_list = raw_list.get("items") or raw_list.get("data") or []

            logger.info(f"Получено {len(raw_list)} ресторанов (yemeksepeti, HTML, {url})")
            result = [r for raw in raw_list if (r := self._parse_restaurant(raw, city))]
            if result:
                return result

        logger.error("Не удалось получить список ресторанов Yemeksepeti (API и HTML)")
        return []

    def _parse_restaurant(self, raw: dict, city: str = "") -> Optional[Restaurant]:
        try:
            # Slug: предпочитаем slug, fallback — url_path (без ведущего слеша)
            slug = raw.get("slug") or raw.get("url_path", "").lstrip("/")

            # Время доставки
            dt = raw.get("delivery_time") or {}
            d_min = self._safe_int(dt.get("minimum") or dt.get("min"))
            d_max = self._safe_int(dt.get("maximum") or dt.get("max"))

            # Стоимость доставки
            fee_obj = raw.get("delivery_fee") or {}
            if isinstance(fee_obj, dict):
                delivery_fee = self._safe_float(fee_obj.get("amount"))
            else:
                delivery_fee = self._parse_price_str(str(fee_obj))

            # Минимальный заказ
            mov_obj = raw.get("minimum_order_value") or {}
            if isinstance(mov_obj, dict):
                min_order = self._safe_float(mov_obj.get("amount"))
            else:
                min_order = self._parse_price_str(str(mov_obj))

            # Рейтинг
            rating_obj = raw.get("rating") or {}
            if isinstance(rating_obj, dict):
                rating = self._safe_float(rating_obj.get("score") or rating_obj.get("average"))
                rating_count = self._safe_int(rating_obj.get("vote_count") or rating_obj.get("count"))
            else:
                rating = self._safe_float(raw.get("ratingPoint") or raw.get("rating"))
                rating_count = self._parse_rating_count(raw.get("ratingCount"))

            # Кухни
            cuisines_raw = raw.get("cuisines") or raw.get("cuisine_types") or []
            cuisine_types = [
                (c.get("name") or c) if isinstance(c, dict) else str(c)
                for c in cuisines_raw
            ]

            # Скидки / промо-теги
            discounts = []
            for label in (raw.get("labels") or raw.get("tags") or []):
                text = (label.get("text") or label.get("title") or label.get("name")
                        if isinstance(label, dict) else str(label))
                if text:
                    discounts.append({"type": "label", "description": text})

            return Restaurant(
                id=str(raw.get("id", "")),
                name=raw.get("name", ""),
                slug=slug,
                cuisine_types=cuisine_types,
                rating=rating,
                rating_count=rating_count,
                min_order_amount=min_order,
                delivery_fee=delivery_fee,
                delivery_time_min=d_min,
                delivery_time_max=d_max,
                is_open=raw.get("is_open", raw.get("isOpen", True)),
                discounts=discounts,
            )
        except Exception as e:
            logger.debug(f"Ошибка парсинга ресторана Yemeksepeti: {e}")
            return None

    # ------------------------------------------------------------------
    # Меню ресторана — из HTML страницы
    # ------------------------------------------------------------------

    def fetch_menu(self, restaurant: Restaurant) -> Restaurant:
        if not restaurant.slug:
            logger.warning(f"Нет slug для {restaurant.name}, меню пропущено")
            return restaurant

        # Попытка 1: Delivery Hero REST API /api/v5/vendors/{id}/menus
        from config import YEMEKSEPETI_ENDPOINTS
        menu_path_tpl = YEMEKSEPETI_ENDPOINTS.get("restaurant_menu", "")
        if menu_path_tpl and restaurant.id:
            menu_path = menu_path_tpl.replace("{restaurant_id}", restaurant.id)
            api_response = self._request("GET", f"{YEMEKSEPETI_API_BASE}{menu_path}")
            if api_response:
                try:
                    data = api_response.json()
                    raw_cats = (
                        data.get("data", {}).get("menus")
                        or data.get("menus")
                        or data.get("categories")
                        or []
                    )
                    if raw_cats:
                        restaurant.menu_categories = self._parse_menu_categories(raw_cats)
                        logger.debug(f"Меню {restaurant.name}: {len(restaurant.menu_categories)} категорий (API)")
                        return restaurant
                except Exception as e:
                    logger.debug(f"Ошибка парсинга меню через API для {restaurant.name}: {e}")

        # Попытка 2: HTML-скрапинг страницы ресторана
        urls_to_try = [
            f"{WEB_BASE}/{restaurant.slug}/",
        ]
        response = None
        for url in urls_to_try:
            response = self._request("GET", url, headers={"Accept": "text/html,*/*"})
            if response:
                break

        if not response:
            logger.warning(f"Страница ресторана недоступна: {restaurant.name}")
            return restaurant

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            response.text, re.DOTALL
        )
        if not match:
            logger.warning(f"__NEXT_DATA__ не найден для {restaurant.name}")
            return restaurant

        try:
            page_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return restaurant

        categories = self._find_categories(page_data)
        if not categories:
            logger.warning(f"Меню пустое для {restaurant.name}")
            return restaurant

        restaurant.menu_categories = self._parse_menu_categories(categories)
        logger.debug(f"Меню {restaurant.name}: {len(restaurant.menu_categories)} категорий")
        return restaurant

    def _find_categories(self, page_data: dict) -> list:
        """Пробует несколько известных путей в __NEXT_DATA__ Yemeksepeti."""
        page_props = page_data.get("props", {}).get("pageProps", {})
        candidates = [
            # Delivery Hero / Yemeksepeti Next.js
            page_props.get("restaurantData", {}).get("menu", {}).get("categories"),
            page_props.get("initialState", {}).get("restaurant", {}).get("menu", {}).get("categories"),
            page_props.get("initialState", {}).get("restaurantDetail", {}).get("menu", {}).get("categories"),
            page_props.get("restaurant", {}).get("menu", {}).get("categories"),
            page_props.get("menuData", {}).get("categories"),
        ]
        for c in candidates:
            if c:
                return c
        # Глубокий поиск ключа 'categories' в дереве pageProps
        return self._deep_find_key(page_props, "categories")

    @staticmethod
    def _deep_find_key(obj, key: str, depth: int = 6):
        """Ищет первый список по ключу на глубину до depth уровней."""
        if depth == 0 or not isinstance(obj, (dict, list)):
            return None
        if isinstance(obj, dict):
            if key in obj and isinstance(obj[key], list) and obj[key]:
                return obj[key]
            for v in obj.values():
                result = YemeksepetScraper._deep_find_key(v, key, depth - 1)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = YemeksepetScraper._deep_find_key(item, key, depth - 1)
                if result is not None:
                    return result
        return None

    def _parse_menu_categories(self, raw_cats: list) -> List[MenuCategory]:
        categories = []
        for raw_cat in raw_cats:
            items = []
            products = raw_cat.get("products") or raw_cat.get("items") or []
            for raw_item in products:
                price = self._extract_price(raw_item)
                orig_price = self._extract_price(raw_item, key="original_price")

                image_url = (
                    raw_item.get("image_url")
                    or raw_item.get("imageURL")
                    or (raw_item.get("images") or [{}])[0].get("url")
                    if isinstance(raw_item.get("images"), list) else None
                )

                items.append(MenuItem(
                    id=str(raw_item.get("id", "")),
                    name=raw_item.get("name", ""),
                    description=raw_item.get("description") or None,
                    price=price or 0.0,
                    original_price=orig_price,
                    discount_percentage=self._safe_float(raw_item.get("discount_percentage")),
                    image_url=image_url,
                    is_available=bool(raw_item.get("available", raw_item.get("is_available", True))),
                ))

            categories.append(MenuCategory(
                id=str(raw_cat.get("id", "")),
                name=raw_cat.get("name", ""),
                items=items,
            ))
        return categories

    def _extract_price(self, raw_item: dict, key: str = "price") -> Optional[float]:
        """Извлекает цену из {amount: N} или прямого числа / строки."""
        val = raw_item.get(key)
        if val is None:
            return None
        if isinstance(val, dict):
            return self._safe_float(val.get("amount") or val.get("value"))
        if isinstance(val, (int, float)):
            return float(val)
        return self._parse_price_str(str(val))

    # ------------------------------------------------------------------
    # Вспомогательные методы (идентичны GetirYemekScraper)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_price_str(s: str) -> Optional[float]:
        """Парсит турецкую цену: '₺45,99' → 45.99, '₺1.234,56' → 1234.56"""
        if not s:
            return None
        cleaned = s.replace("₺", "").replace("₺", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_rating_count(s) -> Optional[int]:
        if s is None:
            return None
        if isinstance(s, int):
            return s
        digits = re.sub(r"[^\d]", "", str(s))
        return int(digits) if digits else None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None
