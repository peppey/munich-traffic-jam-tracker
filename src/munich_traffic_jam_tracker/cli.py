"""Command line entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .patterns import (
    derive_patterns,
    load_bus_trips,
    load_munich_bus_routes,
    load_munich_bus_stop_times,
    load_munich_stops,
    write_corridor_geojson,
)
from .plotting import plot_corridor_map, plot_top_patterns
from .plotting import plot_traffic_delay_by_line, plot_traffic_delay_map
from .traffic import (
    append_traffic_snapshot,
    fetch_flow,
    match_flow_to_patterns,
    parse_flow_results,
    summarize_traffic,
    summarize_traffic_history,
)


def derive_command(arguments: argparse.Namespace) -> None:
    static_dir = Path("data/static")
    output_dir = Path(arguments.output_dir)
    plots_dir = output_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(exist_ok=True)

    routes = load_munich_bus_routes(static_dir / "routes.csv", static_dir / "munich_lines.csv")
    stops = load_munich_stops(static_dir / "munich_stops.csv")
    trips = load_bus_trips(static_dir / "trips.csv", set(routes["route_id"]))
    stop_times = load_munich_bus_stop_times(
        static_dir / "stop_times.csv", set(trips["trip_id"]), set(stops["stop_id"])
    )
    patterns, pattern_stops = derive_patterns(routes, trips, stop_times, stops)
    patterns.drop(columns="stop_ids").to_csv(output_dir / "bus_patterns.csv", index=False)
    pattern_stops.to_csv(output_dir / "bus_pattern_stops.csv", index=False)
    write_corridor_geojson(patterns, pattern_stops, output_dir / "bus_corridors.geojson")
    plot_top_patterns(patterns, plots_dir / "top_bus_patterns.png")
    plot_corridor_map(patterns, pattern_stops, plots_dir / "bus_corridor_map.png")
    api_key = arguments.here_api_key or os.environ.get("HERE_API_KEY")
    if api_key:
        west = float(stops["stop_lon"].min())
        east = float(stops["stop_lon"].max())
        south = float(stops["stop_lat"].min())
        north = float(stops["stop_lat"].max())
        results = fetch_flow(api_key, west, south, east, north)
        flow = parse_flow_results(results)
        matches = match_flow_to_patterns(flow, pattern_stops)
        current_by_pattern, _ = summarize_traffic(matches, patterns)
        history_path = output_dir / "traffic_history.parquet"
        if current_by_pattern.empty:
            print("HERE returned no flow segments matching the bus corridors; history unchanged")
        else:
            history = append_traffic_snapshot(history_path, current_by_pattern)
            traffic_by_pattern, traffic_by_line = summarize_traffic_history(history)
            traffic_by_pattern.to_csv(output_dir / "bus_pattern_traffic.csv", index=False)
            traffic_by_line.to_csv(output_dir / "bus_line_traffic.csv", index=False)
            plot_traffic_delay_by_line(traffic_by_line, plots_dir / "bus_line_traffic_delay.png")
            plot_traffic_delay_map(traffic_by_pattern, pattern_stops, plots_dir / "bus_traffic_delay_map.png")
            print(f"Matched {len(matches)} HERE flow segments and wrote traffic estimates")
    print(f"Wrote {len(patterns)} patterns and {len(pattern_stops)} pattern stops to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive Munich bus traffic corridors from GTFS.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    derive = subparsers.add_parser("derive-patterns")
    derive.add_argument("--output-dir", default="data/derived")
    derive.add_argument("--here-api-key", help="HERE API key; defaults to HERE_API_KEY")
    derive.set_defaults(handler=derive_command)
    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
