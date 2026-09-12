from datetime import datetime, timezone

import pandas as pd
import pytest

from munich_traffic_jam_tracker import traffic


def here_result(*, speed=30, free_flow=60, jam_factor=4):
    return {
        "location": {
            "shape": {
                "links": [
                    {
                        "points": [
                            {"lat": 48.1000, "lng": 11.5000},
                            {"lat": 48.1000, "lng": 11.5100},
                        ]
                    }
                ]
            }
        },
        "currentFlow": {
            "speed": speed,
            "freeFlow": free_flow,
            "jamFactor": jam_factor,
        },
    }


def test_fetch_flow_uses_here_v7_bbox_and_returns_results(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            captured["raised"] = True

        def json(self):
            return {"results": [{"id": "road-1"}]}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(traffic.requests, "get", fake_get)

    results = traffic.fetch_flow("secret", 11.5, 48.0, 11.6, 48.2)

    assert results == [{"id": "road-1"}]
    assert captured["url"] == traffic.HERE_FLOW_URL
    assert captured["kwargs"]["params"] == {
        "apiKey": "secret",
        "in": "bbox:11.5,48.0,11.6,48.2",
        "locationReferencing": "shape",
    }
    assert captured["kwargs"]["timeout"] == 30
    assert captured["raised"] is True


def test_parse_flow_results_calculates_delay_and_skips_invalid_records():
    flow = traffic.parse_flow_results(
        [
            here_result(speed=30, free_flow=60),
            {"location": {"shape": {"points": [{"lat": 48.1, "lng": 11.5}]}}, "currentFlow": {}},
        ]
    )

    assert len(flow) == 1
    assert flow.iloc[0]["length_km"] == pytest.approx(0.744, abs=0.01)
    assert flow.iloc[0]["delay_seconds"] == pytest.approx(flow.iloc[0]["length_km"] / 60 * 3600)
    assert flow.iloc[0]["jam_factor"] == 4


def test_match_flow_to_patterns_keeps_direction_and_rejects_distant_flow():
    flow = pd.DataFrame(
        [
            {
                "latitude": 48.1,
                "longitude": 11.505,
                "length_km": 1.0,
                "speed_kph": 30.0,
                "free_flow_kph": 60.0,
                "jam_factor": 4.0,
                "delay_seconds": 60.0,
            },
            {
                "latitude": 49.0,
                "longitude": 12.0,
                "length_km": 1.0,
                "speed_kph": 30.0,
                "free_flow_kph": 60.0,
                "jam_factor": 4.0,
                "delay_seconds": 60.0,
            },
        ]
    )
    pattern_stops = pd.DataFrame(
        {
            "pattern_id": ["p1", "p1"],
            "route_short_name": ["58", "58"],
            "direction_label": ["Start -> Ende", "Start -> Ende"],
            "stop_sequence": [0, 1],
            "stop_lat": [48.1, 48.1],
            "stop_lon": [11.5, 11.51],
        }
    )

    matches = traffic.match_flow_to_patterns(flow, pattern_stops, max_distance_km=0.1)

    assert len(matches) == 1
    assert matches.iloc[0]["direction_label"] == "Start -> Ende"


def test_summarize_traffic_returns_line_direction_rows():
    matches = pd.DataFrame(
        [
            {"pattern_id": "p1", "route_short_name": "58", "direction_label": "A -> B", "length_km": 1.0, "delay_seconds": 20.0, "jam_factor": 2.0},
            {"pattern_id": "p1", "route_short_name": "58", "direction_label": "A -> B", "length_km": 3.0, "delay_seconds": 40.0, "jam_factor": 4.0},
            {"pattern_id": "p2", "route_short_name": "58", "direction_label": "B -> A", "length_km": 1.0, "delay_seconds": 80.0, "jam_factor": 8.0},
        ]
    )
    patterns = pd.DataFrame(
        {
            "pattern_id": ["p1", "p2"],
            "route_short_name": ["58", "58"],
            "direction_label": ["A -> B", "B -> A"],
        }
    )

    pattern_summary, line_summary = traffic.summarize_traffic(matches, patterns)

    assert len(line_summary) == 2
    assert set(line_summary["direction_label"]) == {"A -> B", "B -> A"}
    forward = line_summary.loc[line_summary["direction_label"] == "A -> B", "traffic_delay_seconds"].iat[0]
    assert forward == pytest.approx(35.0)


def test_append_snapshot_replaces_same_timestamp_and_history_averages(tmp_path):
    history_path = tmp_path / "traffic_history.parquet"
    snapshot = pd.DataFrame(
        {
            "pattern_id": ["p1"],
            "route_short_name": ["58"],
            "direction_label": ["A -> B"],
            "traffic_delay_seconds": [20.0],
            "traffic_jam_factor": [2.0],
            "matched_flow_segments": [1],
        }
    )
    first = datetime(2026, 9, 12, 10, tzinfo=timezone.utc)
    second = datetime(2026, 9, 12, 11, tzinfo=timezone.utc)

    traffic.append_traffic_snapshot(history_path, snapshot, first)
    traffic.append_traffic_snapshot(history_path, snapshot.assign(traffic_delay_seconds=99.0), first)
    history = traffic.append_traffic_snapshot(history_path, snapshot.assign(traffic_delay_seconds=40.0), second)
    pattern_mean, line_mean = traffic.summarize_traffic_history(history)

    assert len(history) == 2
    assert history["observed_at"].dt.tz is not None
    assert pattern_mean.iloc[0]["traffic_delay_seconds"] == pytest.approx(69.5)
    assert line_mean.iloc[0]["observation_count"] == 2
