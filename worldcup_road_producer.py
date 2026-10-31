"""Poll three Rabat road samples into stdout or Kafka. Fixture mode is explicitly simulated."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

from worldcup.config import ROOT, Settings
from worldcup.road_flow import ROAD_TOPIC, RoadFlowError, RoadSample, fetch_flow, normalize_flow
from worldcup_event_producer import KafkaSink, StdoutSink


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sink", choices=("stdout", "kafka"), default="stdout")
    parser.add_argument("--points", type=Path, default=ROOT / "data" / "rabat_road_points.json")
    parser.add_argument("--fixture", type=Path, help="Synthetic provider-shaped data; never marked live")
    parser.add_argument("--polls", type=int, default=1, help="Number of polling rounds; zero runs until Ctrl+C")
    parser.add_argument("--interval", type=float, default=120, help="Seconds between rounds")
    args = parser.parse_args(argv)
    if args.polls < 0 or not math.isfinite(args.interval) or args.interval < 10:
        parser.error("polls must be nonnegative; interval must be finite and at least 10 seconds")
    api_key = os.getenv("TOMTOM_API_KEY", "").strip()
    if not args.fixture and not api_key:
        print("Set TOMTOM_API_KEY locally, or use --fixture data/road_flow_fixture.json for a simulated check.", file=sys.stderr)
        return 2
    try:
        definitions = json.loads(args.points.read_text(encoding="utf-8"))["samples"]
        if not isinstance(definitions, list) or not definitions:
            raise RoadFlowError("samples must be a nonempty list")
        samples = [RoadSample(**item) for item in definitions]
        if len({sample.sample_id for sample in samples}) != len(samples):
            raise RoadFlowError("sample IDs must be unique")
        fixture = json.loads(args.fixture.read_text(encoding="utf-8")) if args.fixture else None
        if fixture is not None and (not isinstance(fixture, dict) or fixture.get("source_mode") != "simulated"):
            raise RoadFlowError("fixture must declare source_mode=simulated")
        payloads = fixture["responses"] if fixture is not None else None
        if payloads is not None and not isinstance(payloads, dict):
            raise RoadFlowError("fixture responses must be an object")
    except (OSError, ValueError, KeyError, TypeError):
        print("Invalid sample points or fixture configuration.", file=sys.stderr)
        return 2
    sink = KafkaSink(Settings.from_env().kafka_bootstrap_servers) if args.sink == "kafka" else StdoutSink()
    round_number = 0
    try:
        while args.polls == 0 or round_number < args.polls:
            for sample in samples:
                payload = payloads[sample.sample_id] if payloads is not None else fetch_flow(sample, api_key)
                event = normalize_flow(payload, sample, source_mode="simulated" if payloads is not None else "live")
                # A snapshot is keyed by road segment, never counted as a passenger validation.
                sink.send(ROAD_TOPIC, event.to_mapping(), key=event.segment_id)
            round_number += 1
            if args.polls == 0 or round_number < args.polls:
                time.sleep(args.interval)
    except RoadFlowError as error:
        print(f"Road collection failed: {error}", file=sys.stderr)
        return 1
    except KeyError:
        print("Road collection failed: a sample is missing from the fixture.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        sink.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
