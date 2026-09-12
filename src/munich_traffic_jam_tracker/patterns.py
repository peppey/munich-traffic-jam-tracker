"""GTFS loading and bus service-pattern derivation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


BUS_ROUTE_TYPE = "3"


def load_munich_bus_routes(routes_path: Path, lines_path: Path) -> pd.DataFrame:
    """Return GTFS routes that are configured Munich bus lines."""
    routes = pd.read_csv(routes_path, dtype=str)
    lines = pd.read_csv(lines_path, dtype=str)
    bus_lines = set(
        lines.loc[lines["mode"].str.casefold() == "bus", "line"].dropna().str.strip()
    )
    routes["route_short_name"] = routes["route_short_name"].fillna("").str.strip()
    is_munich_bus = routes["route_short_name"].isin(bus_lines)
    is_gtfs_bus = routes["route_type"].fillna("") == BUS_ROUTE_TYPE
    return routes.loc[is_munich_bus & is_gtfs_bus].copy()


def load_munich_stops(stops_path: Path) -> pd.DataFrame:
    """Load the existing Munich-boundary-filtered stop catalogue."""
    stops = pd.read_csv(stops_path, dtype={"stop_id": str})
    stops["stop_id"] = stops["stop_id"].astype(str)
    inside = stops["inside_munich"].astype(str).str.casefold().eq("true")
    return stops.loc[inside, ["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()


def load_bus_trips(trips_path: Path, route_ids: set[str]) -> pd.DataFrame:
    """Load bus trips and retain `direction_id` if available in a future feed."""
    trips = pd.read_csv(trips_path, dtype=str)
    trips = trips.loc[trips["route_id"].isin(route_ids)].copy()
    if "direction_id" not in trips:
        trips["direction_id"] = pd.NA
    return trips[["trip_id", "route_id", "direction_id"]]


def load_munich_bus_stop_times(
    stop_times_path: Path,
    trip_ids: set[str],
    munich_stop_ids: set[str],
    chunk_size: int = 500_000,
) -> pd.DataFrame:
    """Read the large stop-times file in chunks and keep relevant stop visits."""
    retained_chunks: list[pd.DataFrame] = []
    columns = ["trip_id", "stop_id", "stop_sequence"]
    for chunk in pd.read_csv(stop_times_path, usecols=columns, dtype=str, chunksize=chunk_size):
        selected = chunk.loc[
            chunk["trip_id"].isin(trip_ids) & chunk["stop_id"].isin(munich_stop_ids)
        ].copy()
        if not selected.empty:
            selected["stop_sequence"] = pd.to_numeric(
                selected["stop_sequence"], errors="coerce"
            )
            retained_chunks.append(selected)
    if not retained_chunks:
        return pd.DataFrame(columns=columns)
    return pd.concat(retained_chunks, ignore_index=True)


def _sequence_id(route_id: str, direction_key: str, stop_ids: tuple[str, ...]) -> str:
    payload = "|".join((route_id, direction_key, *stop_ids))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def derive_patterns(
    routes: pd.DataFrame, trips: pd.DataFrame, stop_times: pd.DataFrame, stops: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Group equal ordered Munich stop sequences into directional service patterns."""
    visits = stop_times.merge(trips, on="trip_id", how="inner")
    visits = visits.sort_values(["trip_id", "stop_sequence"])
    trip_sequences = (
        visits.groupby(["trip_id", "route_id", "direction_id"], dropna=False)["stop_id"]
        .agg(tuple)
        .reset_index(name="stop_ids")
    )
    trip_sequences = trip_sequences.loc[trip_sequences["stop_ids"].str.len() >= 2].copy()
    stop_names = stops.set_index("stop_id")["stop_name"].to_dict()
    trip_sequences["direction_source"] = trip_sequences["direction_id"].notna().map(
        {True: "gtfs_direction_id", False: "derived_terminal_stops"}
    )
    trip_sequences["direction_key"] = trip_sequences.apply(
        lambda row: str(row.direction_id)
        if pd.notna(row.direction_id)
        else f"{row.stop_ids[0]}:{row.stop_ids[-1]}",
        axis=1,
    )
    trip_sequences["direction_label"] = trip_sequences["stop_ids"].map(
        lambda sequence: f"{stop_names.get(sequence[0], sequence[0])} -> "
        f"{stop_names.get(sequence[-1], sequence[-1])}"
    )
    trip_sequences["pattern_id"] = trip_sequences.apply(
        lambda row: _sequence_id(row.route_id, row.direction_key, row.stop_ids), axis=1
    )
    patterns = (
        trip_sequences.groupby(
            ["pattern_id", "route_id", "direction_label", "direction_source", "stop_ids"],
            as_index=False,
        )
        .agg(trip_count=("trip_id", "size"))
        .sort_values(["trip_count", "route_id"], ascending=[False, True])
    )
    route_names = routes.set_index("route_id")["route_short_name"]
    patterns.insert(1, "route_short_name", patterns["route_id"].map(route_names))
    patterns["stop_count"] = patterns["stop_ids"].str.len()

    pattern_stops = patterns[
        ["pattern_id", "route_id", "route_short_name", "direction_label", "stop_ids"]
    ].explode("stop_ids", ignore_index=True)
    pattern_stops = pattern_stops.rename(columns={"stop_ids": "stop_id"})
    pattern_stops["stop_sequence"] = pattern_stops.groupby("pattern_id").cumcount()
    pattern_stops = pattern_stops.merge(stops, on="stop_id", how="left")
    return patterns, pattern_stops


def write_corridor_geojson(patterns: pd.DataFrame, pattern_stops: pd.DataFrame, output_path: Path) -> None:
    """Write provisional straight-line segments between consecutive stops."""
    selected_ids = set(patterns.nlargest(100, "trip_count")["pattern_id"])
    stops = pattern_stops.loc[pattern_stops["pattern_id"].isin(selected_ids)].copy()
    stops = stops.sort_values(["pattern_id", "stop_sequence"])
    features: list[dict] = []
    for pattern_id, group in stops.groupby("pattern_id"):
        coordinates = group[["stop_lon", "stop_lat"]].dropna().values.tolist()
        if len(coordinates) < 2:
            continue
        pattern = patterns.loc[patterns["pattern_id"] == pattern_id].iloc[0]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "pattern_id": pattern_id,
                    "line": pattern["route_short_name"],
                    "direction": pattern["direction_label"],
                    "trip_count": int(pattern["trip_count"]),
                },
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
        )
    output_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
