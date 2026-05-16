from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MenuItem:
    id: str
    name: str
    description: Optional[str]
    price: float
    original_price: Optional[float]
    discount_percentage: Optional[float]
    image_url: Optional[str]
    is_available: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "original_price": self.original_price,
            "discount_percentage": self.discount_percentage,
            "image_url": self.image_url,
            "is_available": self.is_available,
        }


@dataclass
class MenuCategory:
    id: str
    name: str
    items: List[MenuItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class Restaurant:
    id: str
    name: str
    slug: str
    cuisine_types: List[str]
    rating: Optional[float]
    rating_count: Optional[int]
    min_order_amount: Optional[float]
    delivery_fee: Optional[float]
    delivery_time_min: Optional[int]
    delivery_time_max: Optional[int]
    is_open: bool
    discounts: List[dict]
    menu_categories: List[MenuCategory] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "cuisine_types": self.cuisine_types,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "min_order_amount": self.min_order_amount,
            "delivery_fee": self.delivery_fee,
            "delivery_time_min": self.delivery_time_min,
            "delivery_time_max": self.delivery_time_max,
            "is_open": self.is_open,
            "discounts": self.discounts,
            "menu": {
                "categories": [cat.to_dict() for cat in self.menu_categories]
            },
        }


@dataclass
class ScrapeResult:
    source: str
    city: str
    lat: float
    lng: float
    scraped_at: str
    restaurants: List[Restaurant] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metadata": {
                "source": self.source,
                "scraped_at": self.scraped_at,
                "city": self.city,
                "coordinates": {"lat": self.lat, "lng": self.lng},
            },
            "restaurants": [r.to_dict() for r in self.restaurants],
        }
