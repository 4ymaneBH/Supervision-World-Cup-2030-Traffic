"""Kafka -> Spark Structured Streaming -> H3 aggregates and Redis."""

from __future__ import annotations

import argparse
from pathlib import Path
import time

from worldcup.config import Settings
from worldcup.contracts import HOTEL_TOPIC, INVALID_TOPIC, TOPICS
from worldcup.reference import capacity_for, load_reference
from worldcup.redis_store import index_key, mark_processed_batch, write_aggregate, write_hotel
from worldcup.spatial import latlon_to_h3


def crowd_frames(raw, reference: dict, h3_resolution: int):
    """Return validated crowd events and reason-coded invalid records."""
    from pyspark.sql import functions as F, types as T

    schema = T.StructType(
        [
            T.StructField("event_id", T.StringType()),
            T.StructField("schema_version", T.IntegerType()),
            T.StructField("source", T.StringType()),
            T.StructField("city", T.StringType()),
            T.StructField("venue", T.StringType()),
            T.StructField("lat", T.DoubleType()),
            T.StructField("lon", T.DoubleType()),
            T.StructField("timestamp", T.StringType()),
            T.StructField("action", T.StringType()),
            T.StructField("fan_id", T.StringType()),
        ]
    )
    frame = (
        raw.filter(F.col("topic").isin(*TOPICS.values()))
        .withColumn("event", F.from_json(F.col("value").cast("string"), schema))
        .withColumn("event_time", F.to_timestamp(F.col("event.timestamp"), "yyyy-MM-dd'T'HH:mm:ssX"))
    )
    e = lambda field: F.col(f"event.{field}")
    reason = (
        F.when(F.col("event").isNull(), "invalid_json")
        .when(e("schema_version").isNull() | (e("schema_version") != 1), "schema_version")
        .when(e("event_id").isNull() | (F.length(F.trim(e("event_id"))) == 0), "event_id")
        .when(e("city").isNull() | ~e("city").isin(*[city["name"] for city in reference["cities"]]), "city")
        .when(e("source").isNull() | ~e("source").isin(*TOPICS.keys()), "source")
        .when(
            ((F.col("topic") == TOPICS["stadium_access"]) & (e("source") != "stadium_access"))
            | ((F.col("topic") == TOPICS["transit_validation"]) & (e("source") != "transit_validation")),
            "topic_source_mismatch",
        )
        .when(
            ((e("source") == "stadium_access") & (e("action") != "gate_checkin"))
            | ((e("source") == "transit_validation") & (e("action") != "transit_validation"))
            | e("action").isNull(),
            "action",
        )
        .when(
            (e("source") == "stadium_access")
            & (e("venue").isNull() | (F.length(F.trim(e("venue"))) == 0)),
            "venue",
        )
        .when(
            e("lat").isNull() | e("lon").isNull() | F.isnan(e("lat")) | F.isnan(e("lon"))
            | (e("lat") < -90) | (e("lat") > 90) | (e("lon") < -180) | (e("lon") > 180),
            "coordinates",
        )
        .when(
            e("timestamp").isNull()
            | ~e("timestamp").rlike(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            | F.col("event_time").isNull(),
            "timestamp",
        )
    )
    frame = frame.withColumn("invalid_reason", reason)
    invalid = frame.filter(F.col("invalid_reason").isNotNull()).select(
        "topic", "partition", "offset", "invalid_reason", e("event_id").alias("event_id")
    )

    h3_udf = F.udf(lambda lat, lon: latlon_to_h3(lat, lon, h3_resolution), T.StringType())
    valid = frame.filter(F.col("invalid_reason").isNull()).select(
        e("event_id").alias("event_id"),
        e("city").alias("city"),
        e("venue").alias("venue"),
        e("source").alias("source"),
        e("lat").alias("lat"),
        e("lon").alias("lon"),
        "event_time",
    ).withColumn("h3_cell", h3_udf("lat", "lon")).drop("lat", "lon")
    return valid, invalid


def hotel_frames(raw, reference: dict):
    from pyspark.sql import functions as F, types as T

    schema = T.StructType(
        [
            T.StructField("snapshot_id", T.StringType()),
            T.StructField("schema_version", T.IntegerType()),
            T.StructField("source_id", T.StringType()),
            T.StructField("city", T.StringType()),
            T.StructField("area_id", T.StringType()),
            T.StructField("timestamp", T.StringType()),
            T.StructField("rooms_available", T.IntegerType()),
            T.StructField("rooms_occupied", T.IntegerType()),
        ]
    )
    frame = raw.filter(F.col("topic") == HOTEL_TOPIC).withColumn(
        "event", F.from_json(F.col("value").cast("string"), schema)
    )
    e = lambda field: F.col(f"event.{field}")
    required = ["snapshot_id", "source_id", "city", "area_id", "timestamp"]
    missing = F.lit(False)
    for field in required:
        missing = missing | e(field).isNull() | (F.length(F.trim(e(field))) == 0)
    reason = (
        F.when(F.col("event").isNull(), "invalid_json")
        .when(e("schema_version").isNull() | (e("schema_version") != 1), "schema_version")
        .when(missing, "required_field")
        .when(~e("city").isin(*[city["name"] for city in reference["cities"]]), "city")
        .when(
            ~e("timestamp").rlike(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            | F.to_timestamp(e("timestamp"), "yyyy-MM-dd'T'HH:mm:ssX").isNull(),
            "timestamp",
        )
        .when(
            e("rooms_available").isNull() | e("rooms_occupied").isNull()
            | (e("rooms_available") < 0) | (e("rooms_occupied") < 0)
            | ((e("rooms_available") + e("rooms_occupied")) <= 0),
            "rooms",
        )
    )
    frame = frame.withColumn("invalid_reason", reason)
    invalid = frame.filter(F.col("invalid_reason").isNotNull()).select(
        "topic", "partition", "offset", "invalid_reason", e("snapshot_id").alias("event_id")
    )
    valid = frame.filter(F.col("invalid_reason").isNull()).select(
        *[e(field).alias(field) for field in ("snapshot_id", "source_id", "city", "area_id", "timestamp", "rooms_available", "rooms_occupied")]
    )
    return valid, invalid


def save_crowd_batch(batch, batch_id: int, settings: Settings, reference: dict) -> None:
    """Aggregate a static micro-batch, then apply each delta once in Redis."""
    from pyspark.sql import functions as F

    batch.persist()
    try:
        event_count = batch.count()
        if event_count == 0:
            return
        window = F.window("event_time", settings.window_duration, settings.window_slide).alias("window")
        cells = (
            batch.groupBy("city", "venue", "source", "h3_cell", window)
            .count()
            .withColumnRenamed("count", "event_count")
            .withColumn("kind", F.lit("cell"))
        )
        venues = (
            batch.groupBy("city", "venue", "source", window)
            .count()
            .withColumnRenamed("count", "event_count")
            .withColumn("h3_cell", F.lit(""))
            .withColumn("kind", F.lit("venue"))
        )
        rows = cells.select("city", "venue", "source", "h3_cell", "window", "event_count", "kind").unionByName(
            venues.select("city", "venue", "source", "h3_cell", "window", "event_count", "kind")
        )

        def write_partition(partition) -> None:
            import redis

            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            for row in partition:
                venue = row.venue or ""
                known_venue = next((city["venue"] for city in reference["cities"] if city["name"] == row.city), None)
                capacity = capacity_for(reference, row.city, row.source) if row.kind == "venue" and venue == known_venue else None
                write_aggregate(
                    client,
                    stream_id=settings.stream_id,
                    batch_id=batch_id,
                    kind=row.kind,
                    city=row.city,
                    venue=venue,
                    source=row.source,
                    h3_cell=row.h3_cell,
                    window_start=row.window.start,
                    window_end=row.window.end,
                    delta=int(row.event_count),
                    capacity=capacity,
                    ttl_seconds=settings.redis_ttl_seconds,
                )
            client.close()

        rows.foreachPartition(write_partition)
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        cutoff = time.time() - settings.redis_ttl_seconds
        for kind in ("cell", "venue"):
            client.zremrangebyscore(index_key(kind), "-inf", cutoff)
        mark_processed_batch(
            client,
            stream_id=settings.stream_id,
            batch_id=batch_id,
            count=event_count,
            ttl_seconds=settings.redis_ttl_seconds,
        )
        client.close()
    finally:
        batch.unpersist()


def save_hotel_batch(batch, _batch_id: int, settings: Settings) -> None:
    def write_partition(partition) -> None:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        for row in partition:
            write_hotel(client, row.asDict(recursive=True), settings.redis_ttl_seconds)
        client.close()

    batch.foreachPartition(write_partition)


def main() -> None:
    from pyspark.sql import SparkSession, functions as F

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--available-now", action="store_true", help="Process currently available Kafka offsets and exit")
    args = parser.parse_args()
    settings = Settings.from_env()
    reference = load_reference(settings.reference_path)
    spark = SparkSession.builder.appName("WorldCupTraffic").config("spark.sql.session.timeZone", "UTC").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", ",".join([*TOPICS.values(), HOTEL_TOPIC]))
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "true")
        .load()
    )
    crowd, crowd_invalid = crowd_frames(raw, reference, settings.h3_resolution)
    hotels, hotel_invalid = hotel_frames(raw, reference)
    deduplicated = crowd.withWatermark("event_time", settings.watermark_delay).dropDuplicatesWithinWatermark(["event_id"])
    invalid = crowd_invalid.unionByName(hotel_invalid)
    checkpoint_root = Path(settings.spark_checkpoint_root).resolve()
    trigger = {"availableNow": True} if args.available_now else {"processingTime": "10 seconds"}
    queries = []
    try:
        queries.append(
            deduplicated.writeStream.outputMode("append")
            .foreachBatch(lambda batch, batch_id: save_crowd_batch(batch, batch_id, settings, reference))
            .option("checkpointLocation", str(checkpoint_root / "crowd"))
            .trigger(**trigger)
            .start()
        )
        queries.append(
            hotels.writeStream.outputMode("append")
            .foreachBatch(lambda batch, batch_id: save_hotel_batch(batch, batch_id, settings))
            .option("checkpointLocation", str(checkpoint_root / "hotels"))
            .trigger(**trigger)
            .start()
        )
        dead_letter = invalid.select(
            F.col("topic").cast("string").alias("key"),
            F.to_json(F.struct("topic", "partition", "offset", "invalid_reason", "event_id")).alias("value"),
        )
        queries.append(
            dead_letter.writeStream.format("kafka").outputMode("append")
            .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
            .option("topic", INVALID_TOPIC)
            .option("checkpointLocation", str(checkpoint_root / "invalid"))
            .trigger(**trigger)
            .start()
        )
        if args.available_now:
            for query in queries:
                query.awaitTermination()
        else:
            spark.streams.awaitAnyTermination()
    finally:
        for query in queries:
            if query.isActive:
                query.stop()
        spark.stop()


if __name__ == "__main__":
    main()
