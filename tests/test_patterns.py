import pandas as pd

from munich_traffic_jam_tracker.patterns import derive_patterns
from munich_traffic_jam_tracker.traffic import match_flow_to_patterns, parse_flow_results
from munich_traffic_jam_tracker.traffic import append_traffic_snapshot, summarize_traffic_history


def test_derives_stable_pattern_and_terminal_direction_without_gtfs_direction():
    routes = pd.DataFrame({"route_id": ["route-1"], "route_short_name": ["58"]})
    trips = pd.DataFrame(
        {"trip_id": ["trip-a", "trip-b"], "route_id": ["route-1", "route-1"], "direction_id": [pd.NA, pd.NA]}
    )
    stop_times = pd.DataFrame(
        {"trip_id": ["trip-a", "trip-a", "trip-b", "trip-b"], "stop_id": ["a", "b", "a", "b"], "stop_sequence": [0, 1, 0, 1]}
    )
    stops = pd.DataFrame(
        {"stop_id": ["a", "b"], "stop_name": ["Start", "Ende"], "stop_lat": [48.1, 48.2], "stop_lon": [11.5, 11.6]}
    )

    patterns, pattern_stops = derive_patterns(routes, trips, stop_times, stops)

    assert len(patterns) == 1
    assert patterns.iloc[0]["trip_count"] == 2
    assert patterns.iloc[0]["direction_label"] == "Start -> Ende"
    assert patterns.iloc[0]["direction_source"] == "derived_terminal_stops"
    assert pattern_stops["stop_id"].tolist() == ["a", "b"]


def test_parses_and_matches_here_flow_to_a_pattern():
    results = [
        {
            "location": {"shape": {"links": [{"points": [{"lat": 48.1, "lng": 11.5}, {"lat": 48.2, "lng": 11.6}]}]}},
            "currentFlow": {"speed": 20, "freeFlow": 40, "jamFactor": 5},
        }
    ]
    flow = parse_flow_results(results)
    pattern_stops = pd.DataFrame(
        {
            "pattern_id": ["pattern-1", "pattern-1"],
            "route_short_name": ["58", "58"],
            "direction_label": ["Start -> Ende", "Start -> Ende"],
            "stop_sequence": [0, 1],
            "stop_lat": [48.1, 48.2],
            "stop_lon": [11.5, 11.6],
        }
    )

    matches = match_flow_to_patterns(flow, pattern_stops)

    assert len(flow) == 1
    assert len(matches) == 1
    assert matches.iloc[0]["delay_seconds"] > 0


def test_appends_hourly_snapshot_and_calculates_all_time_mean(tmp_path):
    snapshot = pd.DataFrame(
        {
            "pattern_id": ["pattern-1"],
            "route_short_name": ["58"],
            "direction_label": ["Start -> Ende"],
            "traffic_delay_seconds": [30.0],
            "traffic_jam_factor": [3.0],
            "matched_flow_segments": [2],
        }
    )
    history_path = tmp_path / "traffic_history.parquet"

    append_traffic_snapshot(history_path, snapshot, pd.Timestamp("2026-01-01T10:00:00Z"))
    history = append_traffic_snapshot(
        history_path,
        snapshot.assign(traffic_delay_seconds=50.0),
        pd.Timestamp("2026-01-01T11:00:00Z"),
    )
    pattern_mean, line_mean = summarize_traffic_history(history)

    assert len(history) == 2
    assert pattern_mean.iloc[0]["traffic_delay_seconds"] == 40.0
    assert line_mean.iloc[0]["observation_count"] == 2

