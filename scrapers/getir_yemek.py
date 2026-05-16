import re
import json
import logging
from typing import List, Dict, Optional
from scrapers.base_scraper import BaseScraper
from models.restaurant import Restaurant, MenuCategory, MenuItem
from config import GETIR_HEADERS

logger = logging.getLogger(__name__)

FOOD_API = "https://food-client-api-gateway.getirapi.com"
WEB_BASE = "https://getir.com"


class GetirYemekScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "getir_yemek"

    def _get_headers(self) -> Dict[str, str]:
        return GETIR_HEADERS.copy()

    # ------------------------------------------------------------------
    # Restaurant list — direct REST API (no authorization required)
    # ------------------------------------------------------------------

    def fetch_restaurants(self, lat: float, lng: float, city: str = "") -> List[Restaurant]:
        # API expects "lon" instead of "lng"
        params = {"lat": lat, "lon": lng}
        response = self._request("GET", f"{FOOD_API}/restaurants", params=params)
        if not response:
            logger.error("Failed to fetch restaurant list")
            return []

        data = response.json()
        items = data.get("data", {}).get("items", [])
        total = data.get("data", {}).get("totalCount", len(items))
        logger.info(f"Received {len(items)} out of {total} restaurants")

        restaurants = []
        for raw in items:
            r = self._parse_restaurant(raw)
            if r:
                restaurants.append(r)
        return restaurants

    def _parse_restaurant(self, raw: dict) -> Optional[Restaurant]:
        try:
            # Delivery time from deliveryOptions[0]
            d_min, d_max = None, None
            delivery_fee = None
            for opt in raw.get("deliveryOptions", []):
                dur = opt.get("estimatedDeliveryDuration", {}).get("value", "")
                if "-" in str(dur):
                    parts = str(dur).split("-")
                    d_min = self._safe_int(parts[0])
                    d_max = self._safe_int(parts[1])
                fee_raw = opt.get("deliveryFee", {})
                if isinstance(fee_raw, dict) and fee_raw.get("value"):
                    delivery_fee = self._parse_price_str(fee_raw["value"])
                elif isinstance(fee_raw, str):
                    delivery_fee = self._parse_price_str(fee_raw)
                if d_min is not None:
                    break

            # Fallback to top level if not found in deliveryOptions
            if delivery_fee is None:
                delivery_fee = self._parse_price_str(raw.get("deliveryFee", ""))

            # Discounts from tags
            discounts = []
            for tag in raw.get("tags", []):
                text = tag.get("text") or tag.get("label")
                if text:
                    discounts.append({"type": "tag", "description": text})

            return Restaurant(
                id=str(raw.get("id", "")),
                name=raw.get("name", ""),
                slug=raw.get("slug", ""),
                cuisine_types=[c.get("name", "") for c in raw.get("cuisines", [])],
                rating=self._safe_float(raw.get("ratingPoint")),
                rating_count=self._parse_rating_count(raw.get("ratingCount")),
                min_order_amount=self._parse_price_str(
                    raw.get("minBasketSize", {}).get("value", "") if isinstance(raw.get("minBasketSize"), dict) else ""
                ),
                delivery_fee=delivery_fee,
                delivery_time_min=d_min,
                delivery_time_max=d_max,
                is_open=raw.get("isOpen", True),
                discounts=discounts,
            )
        except Exception as e:
            logger.debug(f"Error parsing restaurant: {e}")
            return None

    # ------------------------------------------------------------------
    # Restaurant menu — parsed from HTML page
    # ------------------------------------------------------------------

    def fetch_menu(self, restaurant: Restaurant) -> Restaurant:
        if not restaurant.slug:
            logger.warning(f"No slug for {restaurant.name}, menu skipped")
            return restaurant

        url = f"{WEB_BASE}/yemek/restoran/{restaurant.slug}/"
        response = self._request("GET", url, headers={"Accept": "text/html,*/*"})
        if not response:
            logger.warning(f"Restaurant page unavailable: {restaurant.name}")
            return restaurant

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            response.text, re.DOTALL
        )
        if not match:
            logger.warning(f"__NEXT_DATA__ not found for {restaurant.name}")
            return restaurant

        try:
            page_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return restaurant

        state = page_data.get("props", {}).get("pageProps", {}).get("initialState", {})
        menu_data = state.get("restaurantDetail", {}).get("menu", {})
        product_categories = menu_data.get("productCategories", [])

        if not product_categories:
            logger.warning(f"Menu is empty for {restaurant.name}")
            return restaurant

        restaurant.menu_categories = self._parse_menu_categories(product_categories)
        logger.debug(f"Menu for {restaurant.name}: {len(restaurant.menu_categories)} categories")
        return restaurant

    def _parse_menu_categories(self, raw_cats: list) -> List[MenuCategory]:
        categories = []
        for raw_cat in raw_cats:
            items = []
            for raw_item in raw_cat.get("products", []):
                price = self._safe_float(raw_item.get("price"))
                # priceText as fallback
                if price is None:
                    price = self._parse_price_str(raw_item.get("priceText", ""))

                items.append(MenuItem(
                    id=str(raw_item.get("id", "")),
                    name=raw_item.get("name", ""),
                    description=raw_item.get("description") or None,
                    price=price or 0.0,
                    original_price=None,
                    discount_percentage=None,
                    image_url=raw_item.get("imageURL") or raw_item.get("fullScreenImageURL"),
                    is_available=bool(raw_item.get("isAvailable", True)),
                ))

            categories.append(MenuCategory(
                id=str(raw_cat.get("id", "")),
                name=raw_cat.get("name", ""),
                items=items,
            ))
        return categories

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_price_str(s: str) -> Optional[float]:
        """Parses Turkish price: '₺45,99' → 45.99, '₺1.234,56' → 1234.56"""
        if not s:
            return None
        # Remove currency symbol and spaces
        cleaned = s.replace("₺", "").strip()
        # Remove thousand separator (dot), replace decimal comma with dot
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_rating_count(s) -> Optional[int]:
        """Parses rating count string: '(500+)' → 500, '1234' → 1234"""
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