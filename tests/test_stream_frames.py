import json
import os
import sys
from datetime import datetime, timezone

import pytest

from worldcup.producer import crowd_events, hotel_snapshots
from worldcup.reference import load_reference


pyspark = pytest.importorskip("pyspark")


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    os.environ["PYSPARK_PYTHON"] = sys.executable
    session = (
        SparkSession.builder.master("local[1]")
        .appName("WorldCupContractTests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


def raw_frame(spark, topic_and_items):
    from pyspark.sql import functions as F

    frames = [
        spark.range(1).select(
            F.lit(topic).alias("topic"),
            F.lit(0).alias("partition"),
            F.lit(index).cast("long").alias("offset"),
            F.lit(json.dumps(item).encode("utf-8")).alias("value"),
        )
        for index, (topic, item) in enumerate(topic_and_items)
    ]
    result = frames[0]
    for frame in frames[1:]:
        result = result.unionByName(frame)
    return result


def test_crowd_validation_h3_and_privacy(spark):
    from spark_worldcup_traffic import crowd_frames
    from worldcup.spatial import latlon_to_h3

    reference = load_reference()
    event = next(crowd_events(reference, count=1, seed=1, run_id="test", timestamp=datetime(2030, 6, 15, tzinfo=timezone.utc)))
    valid, invalid = crowd_frames(
        raw_frame(
            spark,
            [
                ("stadium-access", event.to_mapping() | {"source": "stadium_access", "action": "gate_checkin"}),
                ("stadium-access", event.to_mapping() | {"event_id": "bad", "source": "stadium_access", "action": "gate_checkin", "lat": 91}),
            ],
        ),
        reference,
        8,
    )
    good_rows = valid.select("event_id", "city", "event_time").collect()
    bad_rows = invalid.collect()
    assert len(good_rows) == 1
    assert latlon_to_h3(event.lat, event.lon, 8).startswith("8")
    assert "fan_id" not in valid.columns
    assert len(bad_rows) == 1 and bad_rows[0].invalid_reason == "coordinates"
    assert "fan_id" not in invalid.columns


def test_hotel_validation(spark):
    from spark_worldcup_traffic import hotel_frames

    reference = load_reference()
    hotel = next(hotel_snapshots(reference, seed=2, run_id="test", timestamp=datetime(2030, 6, 15, tzinfo=timezone.utc)))
    valid, invalid = hotel_frames(
        raw_frame(spark, [("hotel-occupancy", hotel.to_mapping()), ("hotel-occupancy", hotel.to_mapping() | {"snapshot_id": "bad", "rooms_available": -1})]),
        reference,
    )
    assert valid.count() == 1
    assert [row.invalid_reason for row in invalid.collect()] == ["rooms"]
