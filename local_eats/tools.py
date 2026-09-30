"""Tools the model can call, plus the code that actually runs them.

The model never touches the database or APIs directly. It asks for a tool by
name, we validate the input and run it, and we send back a JSON result.
"""

from __future__ import annotations

import json
from typing import Any

from .memory import ALLOWED_KEYS, PreferenceStore
from .providers import RestaurantProvider

TAG_VALUES = [
    "vegetarian_friendly", "vegan_options", "gluten_free_options", "kid_friendly",
    "outdoor_seating", "quick_bite", "takeout", "date_night", "reservations",
    "full_bar", "large_groups", "spicy",
]

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_restaurants",
        "description": (
            "Search local restaurants. Use filters that match what the user asked for. "
            "Returns a short list ranked by rating. Call it again with looser filters "
            "if nothing comes back."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text keywords, e.g. 'noodles' or 'patio brunch'."},
                "cuisine": {"type": "string", "description": "Cuisine, e.g. 'Mexican', 'Japanese'."},
                "max_price": {"type": "integer", "minimum": 1, "maximum": 4,
                              "description": "1 = $, 2 = $$, 3 = $$$, 4 = $$$$."},
                "min_rating": {"type": "number", "minimum": 0, "maximum": 5},
                "open_now": {"type": "boolean", "description": "Only places open right now."},
                "tags": {"type": "array", "items": {"type": "string", "enum": TAG_VALUES}},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
        },
    },
    {
        "name": "get_restaurant_details",
        "description": "Get full details for one restaurant (hours, address, summary) by its id.",
        "input_schema": {
            "type": "object",
            "properties": {"restaurant_id": {"type": "string"}},
            "required": ["restaurant_id"],
        },
    },
    {
        "name": "get_user_preferences",
        "description": "Read saved preferences for this user (dietary needs, budget, dislikes...). Call this first.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_user_preference",
        "description": (
            "Save a lasting preference ONLY when the user states it clearly, "
            "e.g. 'I'm vegetarian' or 'keep it cheap'. Don't save one-off requests."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": sorted(ALLOWED_KEYS)},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
]


class ToolRunner:
    def __init__(self, provider: RestaurantProvider, prefs: PreferenceStore):
        self.provider = provider
        self.prefs = prefs

    def run(self, name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
        """Run a tool. Returns (json_result, is_error).

        Errors are returned to the model instead of crashing the loop,
        so it can fix its input and try again.
        """
        try:
            if name == "search_restaurants":
                result: Any = self.provider.search(**tool_input)
            elif name == "get_restaurant_details":
                result = self.provider.details(tool_input["restaurant_id"])
                if result is None:
                    return json.dumps({"error": "No restaurant with that id."}), True
            elif name == "get_user_preferences":
                result = self.prefs.get_all()
            elif name == "save_user_preference":
                self.prefs.save(tool_input["key"], tool_input["value"])
                result = {"saved": True}
            else:
                return json.dumps({"error": f"Unknown tool '{name}'."}), True
            return json.dumps(result), False
        except Exception as exc:  # report back to the model, don't crash
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}), True
