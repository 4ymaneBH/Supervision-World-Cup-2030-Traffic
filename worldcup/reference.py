"""Load synthetic reference capacity and route data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings


def load_reference(path: Path | None = None) -> dict[str, Any]:
    reference_path = path or Settings.from_env().reference_path
    data = json.loads(reference_path.read_text(encoding="utf-8"))
    cities = data.get("cities")
    if not isinstance(cities, list) or not cities:
        raise ValueError("Reference data needs a nonempty cities list")
    names = [city["name"] for city in cities]
    if len(names) != len(set(names)):
        raise ValueError("City names must be unique")
    for city in cities:
        if len(city["center"]) != 2:
            raise ValueError(f"Invalid center for {city['name']}")
        for key in ("stadium_capacity_per_minute", "transit_capacity_per_minute", "hotel_rooms_total"):
            if int(city[key]) <= 0:
                raise ValueError(f"{key} must be positive for {city['name']}")
    return data


def cities_by_name(reference: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {city["name"]: city for city in reference["cities"]}


def capacity_for(reference: dict[str, Any], city: str, source: str) -> int | None:
    location = cities_by_name(reference).get(city)
    if not location:
        return None
    key = {
        "stadium_access": "stadium_capacity_per_minute",
        "transit_validation": "transit_capacity_per_minute",
    }.get(source)
    return int(location[key]) if key else None
