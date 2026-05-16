import json
import os
import tempfile
import logging
from datetime import datetime, timezone
from typing import Set
from config import OUTPUT_DIR, SCRAPE_STATE_FILE

logger = logging.getLogger(__name__)


class FileHandler:
    def __init__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    def save_restaurant(self, source: str, city: str, restaurant_dict: dict, scraped_at: str):
        dir_path = os.path.join(OUTPUT_DIR, city, source)
        os.makedirs(dir_path, exist_ok=True)
        slug = restaurant_dict.get("slug") or restaurant_dict["id"]
        data = {"source": source, "scraped_at": scraped_at, **restaurant_dict}
        filepath = os.path.join(dir_path, f"{slug}.json")
        self._atomic_write(filepath, data)

    def _atomic_write(self, filepath: str, data: dict):
        dir_name = os.path.dirname(os.path.abspath(filepath))
        with tempfile.NamedTemporaryFile(
            mode='w', dir=dir_name, delete=False,
            suffix='.tmp', encoding='utf-8'
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, filepath)

    def load_state(self) -> dict:
        if os.path.exists(SCRAPE_STATE_FILE):
            with open(SCRAPE_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_state(self, state: dict):
        self._atomic_write(SCRAPE_STATE_FILE, state)

    def get_scraped_restaurant_ids(self, source: str, city: str,
                                   max_age_hours: int = 24) -> Set[str]:
        state = self.load_state()
        city_state = state.get(source, {}).get(city, {})
        last_scraped = city_state.get("last_scraped")
        if last_scraped:
            age = (datetime.now(timezone.utc) -
                   datetime.fromisoformat(last_scraped)).total_seconds()
            if age > max_age_hours * 3600:
                return set()
        return set(city_state.get("restaurant_ids", []))

    def mark_restaurant_scraped(self, source: str, city: str,
                                 restaurant_id: str, scraped_at: str):
        state = self.load_state()
        state.setdefault(source, {}).setdefault(city, {}).setdefault("restaurant_ids", [])
        ids = state[source][city]["restaurant_ids"]
        if restaurant_id not in ids:
            ids.append(restaurant_id)
        state[source][city]["last_scraped"] = scraped_at
        self.save_state(state)
