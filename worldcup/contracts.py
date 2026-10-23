"""Versioned input contracts. Personal identifiers never enter aggregate state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from typing import Any, Mapping


TOPICS = {
    "stadium_access": "stadium-access",
    "transit_validation": "transit-validations",
}
HOTEL_TOPIC = "hotel-occupancy"
INVALID_TOPIC = "worldcup-invalid"
ACTIONS = {
    "stadium_access": {"gate_checkin"},
    "transit_validation": {"transit_validation"},
}


def parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be an ISO 8601 UTC string ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must be UTC")
    return parsed


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must have timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value.strip()


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


@dataclass(frozen=True)
class CrowdEvent:
    event_id: str
    schema_version: int
    source: str
    city: str
    venue: str | None
    lat: float
    lon: float
    timestamp: str
    action: str
    fan_id: str | None = None

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> "CrowdEvent":
        event_id = _nonempty(item.get("event_id"), "event_id")
        version = item.get("schema_version")
        if type(version) is not int or version != 1:
            raise ValueError("unsupported schema_version")
        source = _nonempty(item.get("source"), "source")
        if source not in TOPICS:
            raise ValueError("unknown source")
        city = _nonempty(item.get("city"), "city")
        venue_value = item.get("venue")
        venue = _nonempty(venue_value, "venue") if venue_value is not None else None
        if source == "stadium_access" and venue is None:
            raise ValueError("stadium event needs venue")
        lat_value, lon_value = item.get("lat"), item.get("lon")
        if any(isinstance(value, bool) or not isinstance(value, (float, int)) for value in (lat_value, lon_value)):
            raise ValueError("lat and lon must be numbers")
        lat, lon = float(lat_value), float(lon_value)
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("lat or lon outside WGS84 bounds")
        timestamp = _nonempty(item.get("timestamp"), "timestamp")
        parse_utc(timestamp)
        action = _nonempty(item.get("action"), "action")
        if action not in ACTIONS[source]:
            raise ValueError("action does not match source")
        fan_value = item.get("fan_id")
        fan_id = _nonempty(fan_value, "fan_id") if fan_value is not None else None
        return cls(event_id, version, source, city, venue, lat, lon, timestamp, action, fan_id)

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HotelSnapshot:
    snapshot_id: str
    schema_version: int
    source_id: str
    city: str
    area_id: str
    timestamp: str
    rooms_available: int
    rooms_occupied: int

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> "HotelSnapshot":
        version = item.get("schema_version")
        if type(version) is not int or version != 1:
            raise ValueError("unsupported schema_version")
        timestamp = _nonempty(item.get("timestamp"), "timestamp")
        parse_utc(timestamp)
        available = _nonnegative_int(item.get("rooms_available"), "rooms_available")
        occupied = _nonnegative_int(item.get("rooms_occupied"), "rooms_occupied")
        if available + occupied == 0:
            raise ValueError("hotel capacity must be positive")
        return cls(
            _nonempty(item.get("snapshot_id"), "snapshot_id"),
            version,
            _nonempty(item.get("source_id"), "source_id"),
            _nonempty(item.get("city"), "city"),
            _nonempty(item.get("area_id"), "area_id"),
            timestamp,
            available,
            occupied,
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)
