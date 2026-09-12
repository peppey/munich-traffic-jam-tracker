import pandas as pd

from munich_traffic_jam_tracker.patterns import derive_patterns
from munich_traffic_jam_tracker.traffic import match_flow_to_patterns, parse_flow_results


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
            "stop_sequence": [0, 1],
            "stop_lat": [48.1, 48.2],
            "stop_lon": [11.5, 11.6],
        }
    )

    matches = match_flow_to_patterns(flow, pattern_stops)

    assert len(flow) == 1
    assert len(matches) == 1
    assert matches.iloc[0]["delay_seconds"] > 0