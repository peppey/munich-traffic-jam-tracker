"""Command line entry point."""

from __future__ import annotations

import argparse
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


def derive_command(arguments: argparse.Namespace) -> None:
    gtfs_dir = Path(arguments.gtfs_dir)
    output_dir = Path(arguments.output_dir)
    plots_dir = output_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(exist_ok=True)

    routes = load_munich_bus_routes(gtfs_dir / "routes.txt", Path(arguments.munich_lines))
    stops = load_munich_stops(Path(arguments.munich_stops))
    trips = load_bus_trips(gtfs_dir / "trips.txt", set(routes["route_id"]))
    stop_times = load_munich_bus_stop_times(
        gtfs_dir / "stop_times.txt", set(trips["trip_id"]), set(stops["stop_id"])
    )
    patterns, pattern_stops = derive_patterns(routes, trips, stop_times, stops)
    patterns.drop(columns="stop_ids").to_csv(output_dir / "bus_patterns.csv", index=False)
    pattern_stops.to_csv(output_dir / "bus_pattern_stops.csv", index=False)
    write_corridor_geojson(patterns, pattern_stops, output_dir / "bus_corridors.geojson")
    plot_top_patterns(patterns, plots_dir / "top_bus_patterns.png")
    plot_corridor_map(patterns, pattern_stops, plots_dir / "bus_corridor_map.png")
    print(f"Wrote {len(patterns)} patterns and {len(pattern_stops)} pattern stops to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive Munich bus traffic corridors from GTFS.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    derive = subparsers.add_parser("derive-patterns")
    derive.add_argument("--gtfs-dir", required=True)
    derive.add_argument("--munich-stops", required=True)
    derive.add_argument("--munich-lines", required=True)
    derive.add_argument("--munich-boundary", required=True, help="Recorded input boundary for reproducibility.")
    derive.add_argument("--output-dir", default="data/derived")
    derive.set_defaults(handler=derive_command)
    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
