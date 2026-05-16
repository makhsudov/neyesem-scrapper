import requests
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict
from models.restaurant import Restaurant, ScrapeResult
from utils.rate_limiter import RateLimiter
from utils.file_handler import FileHandler
from config import MAX_RETRIES

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.file_handler = FileHandler()
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())

    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]: ...

    @abstractmethod
    def fetch_restaurants(self, lat: float, lng: float, city: str = "") -> List[Restaurant]: ...

    @abstractmethod
    def fetch_menu(self, restaurant: Restaurant) -> Restaurant: ...

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        for attempt in range(MAX_RETRIES):
            try:
                self.rate_limiter.wait()
                response = self.session.request(method, url, timeout=30, **kwargs)

                if response.status_code in (429, 503):
                    self.rate_limiter.backoff(attempt + 1)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on {url} (attempt {attempt+1}/{MAX_RETRIES})")
                self.rate_limiter.backoff(attempt + 1)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                logger.error(f"HTTP {status} on {url}")
                if status in (401, 403, 404):
                    return None
                self.rate_limiter.backoff(attempt + 1)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on {url}: {e}")
                self.rate_limiter.backoff(attempt + 1)

        logger.error(f"Exhausted retries for {url}")
        return None

    def scrape_city(self, city: str, lat: float, lng: float,
                    incremental: bool = True) -> Optional[ScrapeResult]:
        scraped_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"[{self.source_name}] Scraping {city} ({lat}, {lng})")

        restaurants = self.fetch_restaurants(lat, lng, city)
        if not restaurants:
            logger.warning(f"No restaurants returned for {city}")
            return None

        already_scraped = set()
        if incremental:
            already_scraped = self.file_handler.get_scraped_restaurant_ids(
                self.source_name, city
            )

        result = ScrapeResult(
            source=self.source_name,
            city=city, lat=lat, lng=lng,
            scraped_at=scraped_at,
        )

        total = len(restaurants)
        for i, restaurant in enumerate(restaurants, 1):
            if incremental and restaurant.id in already_scraped:
                logger.debug(f"Skipping {restaurant.name} (already scraped)")
                continue

            restaurant = self.fetch_menu(restaurant)
            result.restaurants.append(restaurant)
            self.file_handler.save_restaurant(
                self.source_name, city, restaurant.to_dict(), scraped_at
            )
            self.file_handler.mark_restaurant_scraped(
                self.source_name, city, restaurant.id, scraped_at
            )
            logger.info(f"[{self.source_name}] {city}: {i}/{total} — {restaurant.name}")

        logger.info(f"[{self.source_name}] {city}: scraped {len(result.restaurants)} restaurants")
        return result
