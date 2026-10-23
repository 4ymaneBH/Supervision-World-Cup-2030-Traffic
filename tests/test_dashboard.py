from datetime import datetime, timedelta, timezone

import fakeredis

from app_worldcup_control import build_view
from worldcup.config import Settings
from worldcup.redis_store import write_aggregate, write_hotel
from worldcup.reference import load_reference
from worldcup.spatial import latlon_to_h3


def test_redis_to_dashboard_alert_route_and_stale_state():
    client = fakeredis.FakeRedis(decode_responses=True)
    reference = load_reference()
    city = reference["cities"][0]
    end = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = end - timedelta(minutes=1)
    shared = dict(
        stream_id="dashboard-test",
        batch_id=1,
        city=city["name"],
        venue=city["venue"],
        source="stadium_access",
        window_start=window_start,
        window_end=end,
        ttl_seconds=900,
    )
    write_aggregate(client, kind="venue", h3_cell="", delta=1700, capacity=1800, **shared)
    write_aggregate(
        client, kind="cell", h3_cell=latlon_to_h3(*city["center"], 8),
        delta=1700, capacity=None, **shared,
    )
    write_hotel(
        client,
        {
            "snapshot_id": "hotel-1",
            "source_id": "synthetic-demo",
            "city": city["name"],
            "area_id": "citywide",
            "timestamp": end.isoformat().replace("+00:00", "Z"),
            "rooms_available": 200,
            "rooms_occupied": 800,
        },
        900,
    )

    view = build_view(client, reference, city["name"], {}, Settings())
    assert len(view["geojson"]["features"]) == 1
    assert len(view["alerts"]) == 1
    assert len(view["recommendations"]) == 1
    assert view["recommendations"][0]["status"] == "simulation_only"
    assert view["hotels"][0]["occupancy"] == 0.8
    assert view["hotels"][0]["stale"] is False

    empty_city = build_view(client, reference, reference["cities"][1]["name"], view["alert_state"], Settings())
    assert empty_city["alerts"] == []
    assert empty_city["geojson"]["features"] == []


def test_hysteresis_keeps_route_and_missing_data_clears_alert(monkeypatch):
    reference = load_reference()
    city = reference["cities"][0]
    identity = f"{city['name']}:{city['venue']}:stadium_access"
    venue = {
        "city": city["name"], "venue": city["venue"], "source": "stadium_access",
        "event_count": 1300, "capacity": 1800, "pressure": 1300 / 1800,
        "window_end": "2030-06-15T16:00:00Z", "updated_at": "2030-06-15T16:00:01Z",
    }

    def aggregates(_client, kind):
        return [venue] if kind == "venue" else []

    monkeypatch.setattr("app_worldcup_control.recent_aggregates", aggregates)
    monkeypatch.setattr("app_worldcup_control.recent_hotels", lambda _client: [])
    view = build_view(None, reference, city["name"], {identity: True}, Settings())
    assert len(view["alerts"]) == 1
    assert len(view["recommendations"]) == 1

    monkeypatch.setattr("app_worldcup_control.recent_aggregates", lambda _client, _kind: [])
    missing = build_view(None, reference, city["name"], view["alert_state"], Settings())
    assert identity not in missing["alert_state"]
