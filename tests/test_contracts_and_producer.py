from datetime import datetime, timezone
import json

import pytest

from worldcup.contracts import CrowdEvent, HotelSnapshot
from worldcup.producer import crowd_events, hotel_snapshots
from worldcup.reference import load_reference


NOW = datetime(2030, 6, 15, 16, 30, tzinfo=timezone.utc)


def test_reproducible_events_and_topic_contracts():
    reference = load_reference()
    first = list(crowd_events(reference, count=30, seed=42, run_id="test", timestamp=NOW))
    second = list(crowd_events(reference, count=30, seed=42, run_id="test", timestamp=NOW))
    assert first == second
    assert len({event.event_id for event in first}) == 30
    assert {event.source for event in first} == {"stadium_access", "transit_validation"}
    assert all(event.timestamp == "2030-06-15T16:30:00Z" for event in first)


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"lat": 91},
        {"lon": float("nan")},
        {"timestamp": "2030-06-15T16:30:00"},
        {"action": "transit_validation"},
        {"event_id": ""},
    ],
)
def test_invalid_crowd_event_is_rejected(change):
    event = next(crowd_events(load_reference(), count=1, seed=1, run_id="test", timestamp=NOW))
    item = event.to_mapping() | {"source": "stadium_access", "action": "gate_checkin"} | change
    with pytest.raises(ValueError):
        CrowdEvent.from_mapping(item)


def test_hotel_capacity_contract():
    snapshot = next(hotel_snapshots(load_reference(), seed=7, run_id="test", timestamp=NOW))
    assert snapshot.rooms_available + snapshot.rooms_occupied == 12000
    with pytest.raises(ValueError):
        HotelSnapshot.from_mapping(snapshot.to_mapping() | {"rooms_available": -1})


def test_longer_producer_run_refreshes_hotel_snapshots(capsys):
    from worldcup_event_producer import main

    assert main(["--sink", "stdout", "--count", "3", "--rate", "100", "--hotel-interval", "0.001", "--run-id", "refresh"]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    hotel_records = [record for record in records if record["topic"] == "hotel-occupancy"]
    crowd_records = [record for record in records if record["topic"] != "hotel-occupancy"]
    assert len(crowd_records) == 3
    assert len(hotel_records) >= 4
    assert len({record["value"]["snapshot_id"] for record in hotel_records}) == len(hotel_records)
