"""Pure supervision rules used by the dashboard and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def latest_rows(rows: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    latest: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in keys)
        existing = latest.get(key)
        if existing is None or (row["window_end"], row["updated_at"]) > (
            existing["window_end"], existing["updated_at"]
        ):
            latest[key] = row
    return list(latest.values())


def forecast_next_counts(rows: Iterable[dict[str, Any]]) -> int | None:
    """One-step linear baseline; return None until two distinct windows exist."""
    by_window: dict[str, int] = {}
    for row in rows:
        end = row["window_end"]
        by_window[end] = max(by_window.get(end, 0), int(row["event_count"]))
    values = [by_window[key] for key in sorted(by_window)[-3:]]
    if len(values) < 2:
        return None
    trend = (values[-1] - values[0]) / (len(values) - 1)
    return max(0, round(values[-1] + trend))


def next_alert(previous: bool, pressure: float | None, high: float, low: float) -> bool:
    if pressure is None:
        return False
    return pressure >= (low if previous else high)


def recommend_shuttle(city_reference: dict[str, Any], pressure: float | None, high: float) -> dict[str, Any] | None:
    if pressure is None or pressure < high:
        return None
    routes = [route for route in city_reference.get("shuttles", []) if route["available_seats"] > 0 and route["travel_minutes"] > 0]
    if not routes:
        return None
    route = max(routes, key=lambda item: (item["available_seats"] / item["travel_minutes"], item["available_seats"]))
    return {
        "city": city_reference["name"],
        "route": route["name"],
        "available_seats": route["available_seats"],
        "travel_minutes": route["travel_minutes"],
        "reason": f"Pression {pressure:.0%}; priorité à la capacité disponible par minute de trajet.",
        "status": "simulation_only",
    }


def hotel_view(rows: Iterable[dict[str, Any]], *, now: datetime | None = None, stale_after_seconds: int = 300) -> list[dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    result = []
    for row in rows:
        total = row["rooms_available"] + row["rooms_occupied"]
        age = (current - _instant(row["timestamp"])).total_seconds()
        result.append(
            {
                **row,
                "occupancy": row["rooms_occupied"] / total if total else None,
                "stale": age > stale_after_seconds or age < -60,
                "age_seconds": round(age),
            }
        )
    return result


def cell_geojson(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    import h3

    features = []
    for row in latest_rows(rows, ("city", "venue", "source", "h3_cell")):
        cell = row["h3_cell"]
        if not cell or not h3.is_valid_cell(cell):
            continue
        boundary = h3.cell_to_boundary(cell)
        polygon = [[lon, lat] for lat, lon in boundary]
        polygon.append(polygon[0])
        count = int(row["event_count"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [polygon]},
                "properties": {
                    "city": row["city"],
                    "venue": row["venue"],
                    "source": row["source"],
                    "count": count,
                    "height": min(800, 8 + count * 8),
                    "window_end": row["window_end"],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
