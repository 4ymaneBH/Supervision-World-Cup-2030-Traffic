"""Create the four demo topics on a single-broker Kafka cluster."""

from __future__ import annotations

import argparse

from worldcup.config import Settings
from worldcup.contracts import HOTEL_TOPIC, INVALID_TOPIC, TOPICS


def main() -> None:
    from confluent_kafka.admin import AdminClient, NewTopic

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partitions", type=int, default=6)
    args = parser.parse_args()
    if args.partitions < 1:
        parser.error("partitions must be positive")
    admin = AdminClient({"bootstrap.servers": Settings.from_env().kafka_bootstrap_servers})
    existing = set(admin.list_topics(timeout=10).topics)
    names = [*TOPICS.values(), HOTEL_TOPIC, INVALID_TOPIC]
    missing = [NewTopic(name, num_partitions=args.partitions, replication_factor=1) for name in names if name not in existing]
    futures = admin.create_topics(missing) if missing else {}
    for name, result in futures.items():
        result.result(timeout=30)
        print(f"created {name}")
    for name in names:
        if name in existing:
            print(f"exists {name}")


if __name__ == "__main__":
    main()
