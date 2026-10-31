from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from worldcup.config import ROOT
from worldcup.road_flow import RoadFlowError, RoadSample, fetch_flow, normalize_flow
from worldcup_road_producer import main

SAMPLE = RoadSample("agdal-approach", 33.9905, -6.856)
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
FIXTURE = ROOT / "data" / "road_flow_fixture.json"


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"][SAMPLE.sample_id]


def test_road_snapshot_normalizes_units_geometry_and_missing_provider_time():
    event = normalize_flow(payload(), SAMPLE, source_mode="simulated", retrieved_at=NOW)
    assert event.city == "Rabat"
    assert event.source == "road_flow"
    assert event.source_mode == "simulated"
    assert event.retrieved_at == "2026-10-31T12:00:00Z"
    assert event.provider_timestamp is None
    assert event.geometry[0] == [-6.856, 33.9905]
    assert event.speed_kmh == 35
    assert normalize_flow(payload(), SAMPLE, source_mode="simulated", retrieved_at=NOW).event_id == event.event_id
    assert normalize_flow(payload(), SAMPLE, source_mode="live", retrieved_at=NOW).event_id != event.event_id


@pytest.mark.parametrize("field,value", [
    ("currentSpeed", -1), ("currentSpeed", True), ("freeFlowSpeed", 0),
    ("currentTravelTime", float("nan")), ("freeFlowTravelTime", 0),
    ("confidence", 1.1), ("confidence", None), ("roadClosure", "false"),
    ("coordinates", {"coordinate": []}),
    ("coordinates", {"coordinate": [{"latitude": 91, "longitude": 0}, {"latitude": 0, "longitude": 0}]}),
])
def test_invalid_provider_values_are_rejected(field, value):
    item = deepcopy(payload())
    item["flowSegmentData"][field] = value
    with pytest.raises(RoadFlowError):
        normalize_flow(item, SAMPLE)


def test_request_uses_kmh_and_does_not_leak_key_on_http_failure(monkeypatch):
    def fail(request, timeout):
        query = parse_qs(urlparse(request.full_url).query)
        assert query["unit"] == ["kmph"]
        assert query["point"] == ["33.9905,-6.856"]
        assert timeout == 15
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr("worldcup.road_flow.urlopen", fail)
    with pytest.raises(RoadFlowError, match="HTTP 403") as caught:
        fetch_flow(SAMPLE, "fixture-key-never-log")
    assert "fixture-key-never-log" not in str(caught.value)
    assert "https://" not in str(caught.value)


def test_provider_fetch_parses_successful_response(monkeypatch):
    monkeypatch.setattr("worldcup.road_flow.urlopen", lambda request, timeout: io.BytesIO(json.dumps(payload()).encode()))
    assert fetch_flow(SAMPLE, "test-only-key") == payload()


def test_fixture_producer_is_explicitly_simulated_and_uses_separate_topic(capsys):
    assert main(["--fixture", str(FIXTURE)]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(records) == 3
    assert all(r["topic"] == "road-flow" and r["value"]["source_mode"] == "simulated" for r in records)
    assert all(r["key"] == r["value"]["segment_id"] for r in records)
    assert all("fan_id" not in r["value"] for r in records)


def test_live_mode_requires_local_key_and_bad_fixture_fails_cleanly(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    assert main([]) == 2
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    fixture = tmp_path / "wrong.json"
    fixture.write_text("[]")
    assert main(["--fixture", str(fixture)]) == 2
    assert "Invalid" in capsys.readouterr().err
