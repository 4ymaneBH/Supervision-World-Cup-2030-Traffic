"""Environment based settings shared by the producer, stream and dashboard."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379/0"
    mapbox_access_token: str = ""
    h3_resolution: int = 8
    window_duration: str = "1 minute"
    window_slide: str = "10 seconds"
    watermark_delay: str = "2 minutes"
    redis_ttl_seconds: int = 900
    spark_checkpoint_root: str = "checkpoints/worldcup"
    stream_id: str = "worldcup-demo-v1"
    alert_high: float = 0.85
    alert_low: float = 0.65
    reference_path: Path = ROOT / "data" / "demo_reference.json"

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            mapbox_access_token=os.getenv("MAPBOX_ACCESS_TOKEN", ""),
            h3_resolution=int(os.getenv("H3_RESOLUTION", "8")),
            window_duration=os.getenv("WINDOW_DURATION", "1 minute"),
            window_slide=os.getenv("WINDOW_SLIDE", "10 seconds"),
            watermark_delay=os.getenv("WATERMARK_DELAY", "2 minutes"),
            redis_ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", "900")),
            spark_checkpoint_root=os.getenv("SPARK_CHECKPOINT_ROOT", "checkpoints/worldcup"),
            stream_id=os.getenv("STREAM_ID", "worldcup-demo-v1"),
            alert_high=float(os.getenv("ALERT_HIGH", "0.85")),
            alert_low=float(os.getenv("ALERT_LOW", "0.65")),
            reference_path=Path(os.getenv("REFERENCE_PATH", str(ROOT / "data" / "demo_reference.json"))),
        )
        if not 0 <= settings.h3_resolution <= 15:
            raise ValueError("H3_RESOLUTION must be between 0 and 15")
        if settings.redis_ttl_seconds <= 0:
            raise ValueError("REDIS_TTL_SECONDS must be positive")
        if not 0 <= settings.alert_low < settings.alert_high:
            raise ValueError("Require 0 <= ALERT_LOW < ALERT_HIGH")
        return settings
