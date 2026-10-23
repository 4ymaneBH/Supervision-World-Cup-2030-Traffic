from datetime import datetime, timedelta, timezone
import time

import pytest

from worldcup.redis_store import (
    aggregate_key,
    index_key,
    mark_processed_batch,
    recent_aggregates,
    recent_hotels,
    write_aggregate,
    write_hotel,
)


fakeredis = pytest.importorskip("fakeredis")


def test_aggregate_key_is_stable_and_contains_no_venue_name():
    moment = datetime(2030, 6, 15, tzinfo=timezone.utc)
    key = aggregate_key("cell", "Casablanca", "Grand Stade de Benslimane", "stadium_access", "883901", moment)
    assert key == aggregate_key("cell", "Casablanca", "Grand Stade de Benslimane", "stadium_access", "883901", moment)
    assert "Benslimane" not in key


def test_reads_recent_aggregate_and_hotel_with_typed_values():
    client = fakeredis.FakeRedis(decode_responses=True)
    key = "wc:v1:aggregate:test"
    client.hset(key, mapping={"event_count": "20", "capacity": "100", "pressure": "0.2", "city": "Casablanca", "window_end": "2030-06-15T16:30:00Z"})
    client.zadd(index_key("venue"), {key: time.time()})
    client.hset("wc:v1:hotel:test", mapping={"rooms_available": "20", "rooms_occupied": "80", "city": "Casablanca"})
    client.sadd("wc:v1:index:hotel", "wc:v1:hotel:test")
    rows = recent_aggregates(client, "venue")
    assert rows[0]["event_count"] == 20
    assert rows[0]["pressure"] == 0.2
    assert recent_hotels(client)[0]["rooms_occupied"] == 80


def test_aggregate_delta_and_progress_are_idempotent():
    client = fakeredis.FakeRedis(decode_responses=True)
    end = datetime.now(timezone.utc).replace(microsecond=0)
    arguments = dict(
        stream_id="test-stream",
        kind="venue",
        city="Casablanca",
        venue="Grand Stade de Benslimane",
        source="stadium_access",
        h3_cell="",
        window_start=end - timedelta(minutes=1),
        window_end=end,
        capacity=100,
        ttl_seconds=900,
    )
    assert write_aggregate(client, batch_id=1, delta=20, **arguments) == 20
    assert write_aggregate(client, batch_id=1, delta=20, **arguments) == 0
    assert write_aggregate(client, batch_id=2, delta=15, **arguments) == 35
    row = recent_aggregates(client, "venue")[0]
    assert row["event_count"] == 35
    assert row["pressure"] == 0.35
    assert mark_processed_batch(client, stream_id="test-stream", batch_id=1, count=20, ttl_seconds=900) == 20
    assert mark_processed_batch(client, stream_id="test-stream", batch_id=1, count=20, ttl_seconds=900) == 0
    assert mark_processed_batch(client, stream_id="test-stream", batch_id=2, count=15, ttl_seconds=900) == 35


def test_hotel_update_rejects_stale_snapshots():
    client = fakeredis.FakeRedis(decode_responses=True)
    current = datetime.now(timezone.utc).replace(microsecond=0)
    sample = {
        "snapshot_id": "current",
        "source_id": "synthetic-demo",
        "city": "Casablanca",
        "area_id": "citywide",
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "rooms_available": 20,
        "rooms_occupied": 80,
    }
    assert write_hotel(client, sample, 900) == 1
    assert write_hotel(client, sample, 900) == 0
    stale = sample | {"snapshot_id": "older", "timestamp": (current - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")}
    assert write_hotel(client, stale, 900) == 0
    assert recent_hotels(client)[0]["snapshot_id"] == "current"
