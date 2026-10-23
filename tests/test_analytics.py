from datetime import datetime, timezone

from worldcup.analytics import forecast_next_counts, hotel_view, next_alert, recommend_shuttle
from worldcup.reference import load_reference


def test_forecast_uses_distinct_windows_and_clamps_negative():
    rows = [
        {"window_end": "2030-06-15T16:00:00Z", "event_count": 10},
        {"window_end": "2030-06-15T16:00:10Z", "event_count": 20},
        {"window_end": "2030-06-15T16:00:10Z", "event_count": 18},
        {"window_end": "2030-06-15T16:00:20Z", "event_count": 30},
    ]
    assert forecast_next_counts(rows) == 40
    assert forecast_next_counts(rows[:1]) is None
    assert forecast_next_counts([
        {"window_end": "2030-06-15T16:00:00Z", "event_count": 8},
        {"window_end": "2030-06-15T16:00:10Z", "event_count": 1},
    ]) == 0


def test_alert_hysteresis_and_recommendation():
    city = load_reference()["cities"][0]
    assert next_alert(False, 0.90, 0.85, 0.65)
    assert next_alert(True, 0.70, 0.85, 0.65)
    assert not next_alert(True, 0.60, 0.85, 0.65)
    assert next_alert(False, None, 0.85, 0.65) is False
    recommendation = recommend_shuttle(city, 0.90, 0.85)
    assert recommendation["route"] == "Navette A"
    assert recommendation["status"] == "simulation_only"
    assert recommend_shuttle(city, 0.50, 0.85) is None


def test_old_hotel_snapshot_is_marked_stale():
    result = hotel_view(
        [{"rooms_available": 20, "rooms_occupied": 80, "timestamp": "2030-06-15T16:00:00Z"}],
        now=datetime(2030, 6, 15, 16, 10, tzinfo=timezone.utc),
    )
    assert result[0]["occupancy"] == 0.8
    assert result[0]["stale"] is True
