"""Deterministic synthetic crowd and hotel data generation."""

from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import Any, Iterator

from .contracts import CrowdEvent, HotelSnapshot, utc_text


def crowd_events(
    reference: dict[str, Any], *, count: int, seed: int, run_id: str, timestamp: datetime | None = None
) -> Iterator[CrowdEvent]:
    if count < 0:
        raise ValueError("count must be nonnegative")
    rng = random.Random(seed)
    cities = reference["cities"]
    for index in range(count):
        event_time = utc_text(timestamp or datetime.now(timezone.utc))
        city = cities[rng.randrange(len(cities))]
        source = "stadium_access" if rng.random() < 0.55 else "transit_validation"
        center_lat, center_lon = city["center"]
        # Synthetic points cluster around the reference venue; no real fan data is used.
        lat = max(-90, min(90, center_lat + rng.gauss(0, 0.004)))
        lon = max(-180, min(180, center_lon + rng.gauss(0, 0.004)))
        yield CrowdEvent.from_mapping(
            {
                "event_id": f"{run_id}-{index:012d}",
                "schema_version": 1,
                "source": source,
                "fan_id": f"SYN-{rng.randrange(max(count // 3, 1)):08d}",
                "city": city["name"],
                "venue": city["venue"],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "timestamp": event_time,
                "action": "gate_checkin" if source == "stadium_access" else "transit_validation",
            }
        )


def hotel_snapshots(
    reference: dict[str, Any], *, seed: int, run_id: str, timestamp: datetime | None = None
) -> Iterator[HotelSnapshot]:
    rng = random.Random(seed)
    event_time = utc_text(timestamp or datetime.now(timezone.utc))
    for city in reference["cities"]:
        total = city["hotel_rooms_total"]
        occupied = round(total * rng.uniform(0.60, 0.95))
        yield HotelSnapshot.from_mapping(
            {
                "snapshot_id": f"{run_id}-hotel-{city['name'].lower()}",
                "schema_version": 1,
                "source_id": "synthetic-demo",
                "city": city["name"],
                "area_id": "citywide",
                "timestamp": event_time,
                "rooms_available": total - occupied,
                "rooms_occupied": occupied,
            }
        )
