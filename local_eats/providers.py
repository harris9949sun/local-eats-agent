"""Restaurant data providers.

The agent only talks to the `RestaurantProvider` interface, so the data source
can be swapped without touching the agent:

- `SampleDataProvider`: offline, uses data/sample_restaurants.json (fictional places)
- `GooglePlacesProvider`: live data from the Google Places API (New)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import requests

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_restaurants.json"


class RestaurantProvider(Protocol):
    def search(
        self,
        query: str | None = None,
        cuisine: str | None = None,
        max_price: int | None = None,
        min_rating: float | None = None,
        open_now: bool = False,
        tags: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...

    def details(self, restaurant_id: str) -> dict[str, Any] | None: ...


def is_open(hours: dict[str, str], now: datetime) -> bool:
    """Check a simple 'HH:MM-HH:MM' schedule. '24:00' means midnight."""
    spec = hours.get(DAYS[now.weekday()], "closed")
    if spec == "closed":
        return False
    start, end = spec.split("-")
    current = now.strftime("%H:%M")
    return start <= current < end


class SampleDataProvider:
    """Offline provider backed by a JSON file. Good for demos and tests."""

    def __init__(self, path: Path = DEFAULT_DATA_PATH, clock=datetime.now):
        self.restaurants = json.loads(Path(path).read_text())
        self.clock = clock  # injectable so tests can control "now"

    def search(self, query=None, cuisine=None, max_price=None, min_rating=None,
               open_now=False, tags=None, limit=5):
        now = self.clock()
        results = []
        for r in self.restaurants:
            if cuisine and cuisine.lower() not in r["cuisine"].lower():
                continue
            if max_price and r["price_level"] > max_price:
                continue
            if min_rating and r["rating"] < min_rating:
                continue
            if tags and not all(t in r["tags"] for t in tags):
                continue
            if open_now and not is_open(r["hours"], now):
                continue
            if query:
                text = " ".join([r["name"], r["cuisine"], r["neighborhood"], r["summary"], *r["tags"]]).lower()
                if not any(word in text for word in query.lower().split()):
                    continue
            results.append(r)

        # Rank by rating, then by how many people rated it.
        results.sort(key=lambda r: (r["rating"], r["review_count"]), reverse=True)
        return [self._summary(r, now) for r in results[:limit]]

    def details(self, restaurant_id):
        for r in self.restaurants:
            if r["id"] == restaurant_id:
                return {**r, "open_now": is_open(r["hours"], self.clock())}
        return None

    @staticmethod
    def _summary(r, now):
        return {
            "id": r["id"],
            "name": r["name"],
            "cuisine": r["cuisine"],
            "price_level": r["price_level"],
            "rating": r["rating"],
            "review_count": r["review_count"],
            "neighborhood": r["neighborhood"],
            "tags": r["tags"],
            "open_now": is_open(r["hours"], now),
        }


class GooglePlacesProvider:
    """Live provider using the Google Places API (New).

    Docs: https://developers.google.com/maps/documentation/places/web-service/text-search
    Check the docs for current field names and pricing before relying on this in production.
    """

    SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
    PRICE_LEVELS = {
        1: "PRICE_LEVEL_INEXPENSIVE",
        2: "PRICE_LEVEL_MODERATE",
        3: "PRICE_LEVEL_EXPENSIVE",
        4: "PRICE_LEVEL_VERY_EXPENSIVE",
    }
    PRICE_TO_INT = {v: k for k, v in PRICE_LEVELS.items()}
    SEARCH_FIELDS = ",".join([
        "places.id", "places.displayName", "places.formattedAddress", "places.rating",
        "places.userRatingCount", "places.priceLevel", "places.primaryTypeDisplayName",
        "places.currentOpeningHours.openNow",
    ])
    DETAIL_FIELDS = ",".join([
        "id", "displayName", "formattedAddress", "rating", "userRatingCount", "priceLevel",
        "regularOpeningHours.weekdayDescriptions", "websiteUri", "nationalPhoneNumber",
        "editorialSummary", "servesVegetarianFood", "outdoorSeating", "goodForChildren",
    ])

    def __init__(self, api_key: str, location: str, timeout: float = 10.0):
        self.api_key = api_key
        self.location = location
        self.timeout = timeout

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

    def search(self, query=None, cuisine=None, max_price=None, min_rating=None,
               open_now=False, tags=None, limit=5):
        words = [cuisine or "", query or "", " ".join(t.replace("_", " ") for t in tags or [])]
        text = " ".join(w for w in words if w).strip() or "restaurants"
        body: dict[str, Any] = {"textQuery": f"{text} restaurants in {self.location}"}
        if open_now:
            body["openNow"] = True
        if min_rating:
            body["minRating"] = min_rating
        if max_price:
            body["priceLevels"] = [self.PRICE_LEVELS[p] for p in range(1, max_price + 1)]

        resp = requests.post(self.SEARCH_URL, json=body,
                             headers=self._headers(self.SEARCH_FIELDS), timeout=self.timeout)
        resp.raise_for_status()
        places = resp.json().get("places", [])[:limit]
        return [self._summary(p) for p in places]

    def details(self, restaurant_id):
        resp = requests.get(self.DETAILS_URL.format(place_id=restaurant_id),
                            headers=self._headers(self.DETAIL_FIELDS), timeout=self.timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        p = resp.json()
        return {
            **self._summary(p),
            "hours": p.get("regularOpeningHours", {}).get("weekdayDescriptions", []),
            "website": p.get("websiteUri"),
            "phone": p.get("nationalPhoneNumber"),
            "summary": p.get("editorialSummary", {}).get("text"),
            "serves_vegetarian": p.get("servesVegetarianFood"),
            "outdoor_seating": p.get("outdoorSeating"),
            "good_for_children": p.get("goodForChildren"),
        }

    def _summary(self, p):
        return {
            "id": p.get("id"),
            "name": p.get("displayName", {}).get("text"),
            "cuisine": p.get("primaryTypeDisplayName", {}).get("text"),
            "price_level": self.PRICE_TO_INT.get(p.get("priceLevel")),
            "rating": p.get("rating"),
            "review_count": p.get("userRatingCount"),
            "address": p.get("formattedAddress"),
            "open_now": p.get("currentOpeningHours", {}).get("openNow"),
        }
