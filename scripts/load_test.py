"""Run stepped Kafka production while sampling Spark-completed Redis counts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from uuid import uuid4

from worldcup.config import ROOT, Settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _processed(client, stream_id: str) -> int:
    return int(client.get(f"wc:v1:metrics:processed:{stream_id}") or 0)


def main() -> int:
    import redis
    from confluent_kafka.admin import AdminClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rates", type=int, nargs="+", default=[1000, 10000, 25000, 50000])
    parser.add_argument("--duration", type=int, default=60, help="Seconds per rate; use 900 for a 15-minute sustained stage")
    parser.add_argument("--drain-timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "load-results.json")
    args = parser.parse_args()
    if any(rate <= 0 for rate in args.rates) or args.duration <= 0 or args.drain_timeout < 0:
        parser.error("rates and duration must be positive; drain timeout cannot be negative")

    settings = Settings.from_env()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "started_at": _utc_now(),
        "host": {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count()},
        "configuration": {
            "kafka_bootstrap_servers": settings.kafka_bootstrap_servers,
            "stream_id": settings.stream_id,
            "duration_seconds": args.duration,
            "drain_timeout_seconds": args.drain_timeout,
        },
        "limitations": [
            "Redis counts events after Spark completes a micro-batch; this is not a per-event latency measurement.",
            "Run on a dedicated Kafka/Spark/Redis environment; concurrent traffic invalidates processed deltas.",
            "Dashboard rendering latency and resource utilization are not measured by this runner.",
        ],
        "stages": [],
    }
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=3)
    try:
        client.ping()
        AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers}).list_topics(timeout=10)
    except Exception as exc:
        result["status"] = "preflight_failed"
        result["preflight_error"] = f"{type(exc).__name__}: {exc}"
        result["finished_at"] = _utc_now()
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Preflight failed; wrote {args.output}: {result['preflight_error']}", file=sys.stderr)
        return 2
    result["status"] = "running"
    for rate in args.rates:
        run_id = uuid4().hex
        count = rate * args.duration
        baseline = _processed(client, settings.stream_id)
        stderr_path = args.output.parent / f"producer-{run_id}.stderr.log"
        cmd = [
            sys.executable,
            str(ROOT / "worldcup_event_producer.py"),
            "--sink", "kafka",
            "--without-hotels",
            "--count", str(count),
            "--rate", str(rate),
            "--run-id", run_id,
        ]
        samples = []
        stage_start = time.monotonic()
        with stderr_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=log)
            while process.poll() is None:
                samples.append({"elapsed_s": round(time.monotonic() - stage_start, 2), "processed": _processed(client, settings.stream_id) - baseline})
                time.sleep(2)
            process.wait()
        producer_elapsed = time.monotonic() - stage_start
        processed_at_finish = _processed(client, settings.stream_id) - baseline
        producer_stats = None
        for line in stderr_path.read_text(encoding="utf-8").splitlines()[::-1]:
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and candidate.get("run_id") == run_id:
                producer_stats = candidate
                break
        drain_start = time.monotonic()
        while process.returncode == 0 and _processed(client, settings.stream_id) - baseline < count and time.monotonic() - drain_start < args.drain_timeout:
            time.sleep(2)
        processed_final = _processed(client, settings.stream_id) - baseline
        stage = {
            "run_id": run_id,
            "rate_requested": rate,
            "events_requested": count,
            "producer_exit_code": process.returncode,
            "producer": producer_stats,
            "producer_wall_seconds": round(producer_elapsed, 3),
            "processed_at_producer_finish": processed_at_finish,
            "processed_after_drain": processed_final,
            "drain_seconds": round(time.monotonic() - drain_start, 3),
            "sustained_processed_per_second": round(processed_at_finish / max(producer_elapsed, 1e-9), 2),
            "samples": samples,
            "meets_requested_rate": bool(
                process.returncode == 0
                and producer_stats
                and producer_stats["observed_rate"] >= rate * 0.95
                and processed_at_finish / max(producer_elapsed, 1e-9) >= rate * 0.95
                and processed_final >= count
            ),
        }
        result["stages"].append(stage)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{rate}/s: produced={producer_stats['sent'] if producer_stats else '?'} processed={processed_final} sustained={stage['sustained_processed_per_second']}/s")
        if process.returncode != 0:
            result["status"] = "producer_failed"
            result["finished_at"] = _utc_now()
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Producer failed; see {stderr_path}", file=sys.stderr)
            return 1
    result["status"] = "completed"
    result["finished_at"] = _utc_now()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
