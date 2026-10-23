"""Redis sink and query helpers for aggregate, hotel and freshness state."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import time
from typing import Any


PREFIX = "wc:v1"


AGGREGATE_SCRIPT = """
if not redis.call('SET', KEYS[1], '1', 'NX', 'EX', tonumber(ARGV[1])) then
  return 0
end
local count = redis.call('HINCRBY', KEYS[2], 'event_count', tonumber(ARGV[3]))
local capacity = tonumber(ARGV[12])
local pressure = ''
local quality = 'capacity_unknown'
if capacity and capacity > 0 then
  pressure = tostring(count / capacity)
  quality = 'ok'
end
redis.call('HSET', KEYS[2],
  'city', ARGV[4], 'venue', ARGV[5], 'source', ARGV[6],
  'h3_cell', ARGV[7], 'kind', ARGV[8],
  'window_start', ARGV[9], 'window_end', ARGV[10],
  'updated_at', ARGV[11], 'capacity', ARGV[12],
  'pressure', pressure, 'quality_status', quality)
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[2]))
redis.call('ZADD', KEYS[3], tonumber(ARGV[13]), KEYS[2])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[2]))
return count
"""


HOTEL_SCRIPT = """
local current_epoch = tonumber(redis.call('HGET', KEYS[1], 'event_epoch') or '-1')
local current_id = redis.call('HGET', KEYS[1], 'snapshot_id') or ''
local incoming_epoch = tonumber(ARGV[1])
if current_epoch > incoming_epoch or (current_epoch == incoming_epoch and current_id >= ARGV[2]) then
  return 0
end
redis.call('HSET', KEYS[1],
  'event_epoch', ARGV[1], 'snapshot_id', ARGV[2], 'source_id', ARGV[3],
  'city', ARGV[4], 'area_id', ARGV[5], 'timestamp', ARGV[6],
  'rooms_available', ARGV[7], 'rooms_occupied', ARGV[8], 'updated_at', ARGV[9])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[10]))
redis.call('SADD', KEYS[2], KEYS[1])
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[10]))
return 1
"""


PROGRESS_SCRIPT = """
if not redis.call('SET', KEYS[1], '1', 'NX', 'EX', tonumber(ARGV[1])) then
  return 0
end
return redis.call('INCRBY', KEYS[2], tonumber(ARGV[2]))
"""


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def aggregate_key(kind: str, city: str, venue: str, source: str, h3_cell: str, window_start: datetime) -> str:
    identity = json.dumps([kind, city, venue, source, h3_cell, _iso(window_start)], ensure_ascii=False, separators=(",", ":"))
    return f"{PREFIX}:aggregate:{sha256(identity.encode('utf-8')).hexdigest()}"


def index_key(kind: str) -> str:
    if kind not in {"cell", "venue"}:
        raise ValueError("unknown aggregate kind")
    return f"{PREFIX}:index:{kind}"


def hotel_key(city: str, area_id: str) -> str:
    identity = json.dumps([city, area_id], ensure_ascii=False, separators=(",", ":"))
    return f"{PREFIX}:hotel:{sha256(identity.encode('utf-8')).hexdigest()}"


def write_aggregate(
    client: Any,
    *,
    stream_id: str,
    batch_id: int,
    kind: str,
    city: str,
    venue: str,
    source: str,
    h3_cell: str,
    window_start: datetime,
    window_end: datetime,
    delta: int,
    capacity: int | None,
    ttl_seconds: int,
) -> int:
    if delta <= 0:
        raise ValueError("aggregate delta must be positive")
    key = aggregate_key(kind, city, venue, source, h3_cell, window_start)
    marker = f"{PREFIX}:batch:{stream_id}:{batch_id}:{key.rsplit(':', 1)[1]}"
    return int(
        client.eval(
            AGGREGATE_SCRIPT,
            3,
            marker,
            key,
            index_key(kind),
            max(ttl_seconds * 4, 3600),
            ttl_seconds,
            delta,
            city,
            venue,
            source,
            h3_cell,
            kind,
            _iso(window_start),
            _iso(window_end),
            _iso(datetime.now(timezone.utc)),
            capacity if capacity is not None else "",
            int(_utc(window_end).timestamp()),
        )
    )


def write_hotel(client: Any, item: dict[str, Any], ttl_seconds: int) -> int:
    timestamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
    return int(
        client.eval(
            HOTEL_SCRIPT,
            2,
            hotel_key(item["city"], item["area_id"]),
            f"{PREFIX}:index:hotel",
            int(timestamp.timestamp()),
            item["snapshot_id"],
            item["source_id"],
            item["city"],
            item["area_id"],
            item["timestamp"],
            item["rooms_available"],
            item["rooms_occupied"],
            _iso(datetime.now(timezone.utc)),
            ttl_seconds,
        )
    )


def mark_processed_batch(client: Any, *, stream_id: str, batch_id: int, count: int, ttl_seconds: int) -> int:
    """Increment a durable counter once after a micro-batch is fully written."""
    return int(
        client.eval(
            PROGRESS_SCRIPT,
            2,
            f"{PREFIX}:batch-progress:{stream_id}:{batch_id}",
            f"{PREFIX}:metrics:processed:{stream_id}",
            max(ttl_seconds * 4, 3600),
            count,
        )
    )


def recent_aggregates(client: Any, kind: str, *, max_age_seconds: int = 180) -> list[dict[str, Any]]:
    now = time.time()
    keys = client.zrangebyscore(index_key(kind), now - max_age_seconds, now + 120)
    if not keys:
        return []
    pipeline = client.pipeline()
    for key in keys:
        pipeline.hgetall(key)
    values = pipeline.execute()
    rows = []
    for value in values:
        if not value:
            continue
        value["event_count"] = int(value["event_count"])
        value["capacity"] = int(value["capacity"]) if value.get("capacity") else None
        value["pressure"] = float(value["pressure"]) if value.get("pressure") else None
        rows.append(value)
    return rows


def recent_hotels(client: Any) -> list[dict[str, Any]]:
    keys = client.smembers(f"{PREFIX}:index:hotel")
    if not keys:
        return []
    pipeline = client.pipeline()
    for key in keys:
        pipeline.hgetall(key)
    rows = []
    for value in pipeline.execute():
        if value:
            value["rooms_available"] = int(value["rooms_available"])
            value["rooms_occupied"] = int(value["rooms_occupied"])
            rows.append(value)
    return rows
