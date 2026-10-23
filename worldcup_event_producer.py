"""Publish synthetic stadium, transit and hotel events to Kafka or stdout."""

from __future__ import annotations

import argparse
import json
import sys
import time
from uuid import uuid4

from worldcup.config import Settings
from worldcup.contracts import HOTEL_TOPIC, TOPICS
from worldcup.producer import crowd_events, hotel_snapshots
from worldcup.reference import load_reference


class KafkaSink:
    def __init__(self, bootstrap_servers: str):
        from confluent_kafka import Producer

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "enable.idempotence": True,
                "acks": "all",
                "compression.type": "lz4",
                "linger.ms": 20,
            }
        )
        self.failed = 0

    def _delivered(self, error, _message) -> None:
        if error is not None:
            self.failed += 1
            print(f"Kafka delivery failed: {error}", file=sys.stderr)

    def send(self, topic: str, item: dict) -> None:
        payload = json.dumps(item, separators=(",", ":")).encode("utf-8")
        while True:
            try:
                self._producer.produce(topic, value=payload, on_delivery=self._delivered)
                break
            except BufferError:
                self._producer.poll(0.1)
        self._producer.poll(0)

    def close(self) -> None:
        remaining = self._producer.flush(30)
        if remaining or self.failed:
            raise RuntimeError(f"Kafka delivery incomplete: {remaining} pending, {self.failed} failed")


class StdoutSink:
    def send(self, topic: str, item: dict) -> None:
        print(json.dumps({"topic": topic, "value": item}, ensure_ascii=False))

    def close(self) -> None:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sink", choices=("kafka", "stdout"), default="kafka")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--rate", type=float, default=1000, help="Target crowd events per second")
    parser.add_argument("--seed", type=int, default=2030)
    parser.add_argument("--run-id", default=None, help="Stable ID for a reproducible run")
    parser.add_argument("--without-hotels", action="store_true")
    args = parser.parse_args(argv)
    if args.count < 0 or args.rate <= 0:
        parser.error("count must be nonnegative and rate must be positive")

    settings = Settings.from_env()
    reference = load_reference(settings.reference_path)
    run_id = args.run_id or uuid4().hex
    sink = KafkaSink(settings.kafka_bootstrap_servers) if args.sink == "kafka" else StdoutSink()
    start = time.monotonic()
    sent = 0
    try:
        if not args.without_hotels:
            for snapshot in hotel_snapshots(reference, seed=args.seed, run_id=run_id):
                sink.send(HOTEL_TOPIC, snapshot.to_mapping())
        for event in crowd_events(reference, count=args.count, seed=args.seed, run_id=run_id):
            target = sent / args.rate
            delay = target - (time.monotonic() - start)
            if delay > 0:
                time.sleep(delay)
            sink.send(TOPICS[event.source], event.to_mapping())
            sent += 1
    finally:
        sink.close()
    elapsed = max(time.monotonic() - start, 1e-9)
    print(json.dumps({"run_id": run_id, "sent": sent, "elapsed_s": elapsed, "observed_rate": sent / elapsed}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
