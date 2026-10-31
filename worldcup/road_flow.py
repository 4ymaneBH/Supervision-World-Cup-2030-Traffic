"""Small TomTom road-flow adapter. Road snapshots are separate from passenger events."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import utc_text

ROAD_TOPIC = "road-flow"


class RoadFlowError(ValueError):
    """Safe, public error message that must never include the credential-bearing URL."""


@dataclass(frozen=True)
class RoadSample:
    sample_id: str
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id.strip():
            raise RoadFlowError("sample_id is required")
        for value, limit in ((self.lat, 90), (self.lon, 180)):
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or abs(value) > limit:
                raise RoadFlowError("sample coordinates must be finite WGS84 numbers")


@dataclass(frozen=True)
class RoadFlowObservation:
    event_id: str
    schema_version: int
    source: str
    provider: str
    source_mode: str
    city: str
    sample_id: str
    segment_id: str
    retrieved_at: str
    provider_timestamp: str | None
    speed_kmh: float
    free_flow_speed_kmh: float
    travel_time_seconds: float
    free_flow_travel_time_seconds: float
    confidence: float
    road_closed: bool
    geometry: list[list[float]]

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise RoadFlowError(f"{field} must be a finite number")
    if value < 0 or (positive and value == 0):
        raise RoadFlowError(f"{field} is outside its permitted range")
    return float(value)


def normalize_flow(payload: dict, sample: RoadSample, *, source_mode: str = "live", retrieved_at: datetime | None = None) -> RoadFlowObservation:
    if source_mode not in {"live", "simulated"}:
        raise RoadFlowError("unsupported source_mode")
    flow = payload.get("flowSegmentData") if isinstance(payload, dict) else None
    if not isinstance(flow, dict):
        raise RoadFlowError("missing flowSegmentData")
    speed = _number(flow.get("currentSpeed"), "currentSpeed")
    free_speed = _number(flow.get("freeFlowSpeed"), "freeFlowSpeed", positive=True)
    travel = _number(flow.get("currentTravelTime"), "currentTravelTime")
    free_travel = _number(flow.get("freeFlowTravelTime"), "freeFlowTravelTime", positive=True)
    confidence = _number(flow.get("confidence"), "confidence")
    if confidence > 1:
        raise RoadFlowError("confidence must be between zero and one")
    closed = flow.get("roadClosure")
    if not isinstance(closed, bool):
        raise RoadFlowError("roadClosure must be a boolean")
    coordinates = flow.get("coordinates")
    points = coordinates.get("coordinate") if isinstance(coordinates, dict) else coordinates
    if not isinstance(points, list) or len(points) < 2:
        raise RoadFlowError("at least two segment coordinates are required")
    geometry = []
    for point in points:
        if not isinstance(point, dict):
            raise RoadFlowError("invalid segment coordinate")
        location = RoadSample("segment-point", point.get("latitude"), point.get("longitude"))
        geometry.append([float(location.lon), float(location.lat)])
    retrieved = utc_text(retrieved_at or datetime.now(timezone.utc))
    # No observation timestamp is supplied by this endpoint. Keep that absence explicit.
    encoded_geometry = json.dumps(geometry, separators=(",", ":")).encode()
    segment_id = "tomtom:" + hashlib.sha256(encoded_geometry).hexdigest()[:24]
    identity = json.dumps([source_mode, sample.sample_id, retrieved, speed, free_speed, travel, free_travel, confidence, closed, geometry], separators=(",", ":"), allow_nan=False).encode()
    event_id = hashlib.sha256(identity).hexdigest()
    return RoadFlowObservation(event_id, 1, "road_flow", "tomtom", source_mode, "Rabat", sample.sample_id, segment_id, retrieved, None, speed, free_speed, travel, free_travel, confidence, closed, geometry)


def fetch_flow(sample: RoadSample, api_key: str, *, timeout: float = 15) -> dict:
    if not api_key.strip():
        raise RoadFlowError("Set TOMTOM_API_KEY in the local environment")
    query = urlencode({"key": api_key.strip(), "point": f"{sample.lat},{sample.lon}", "unit": "kmph"})
    request = Request("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/14/json?" + query, headers={"Accept": "application/json", "User-Agent": "RabatFlow-BuildDay/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise RoadFlowError("TomTom response is unexpectedly large")
            return json.loads(raw)
    except HTTPError as error:
        raise RoadFlowError(f"TomTom returned HTTP {error.code}; check access and quota") from None
    except (URLError, TimeoutError, OSError):
        raise RoadFlowError("TomTom network request failed; check connectivity") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RoadFlowError("TomTom returned invalid JSON") from None
