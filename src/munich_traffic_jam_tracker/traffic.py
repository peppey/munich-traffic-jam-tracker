"""Fetch HERE traffic flow and estimate road-delay on bus corridors."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import requests

HERE_FLOW_URL = "https://data.traffic.hereapi.com/v7/flow"
EARTH_RADIUS_KM = 6371.0088


def fetch_flow(api_key: str, west: float, south: float, east: float, north: float) -> list[dict[str, Any]]:
    """Fetch current HERE flow results for a WGS84 bounding box."""
    response = requests.get(
        HERE_FLOW_URL,
        params={
            "apiKey": api_key,
            "in": f"bbox:{west},{south},{east},{north}",
            "locationReferencing": "shape",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("results", [])


def _point(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        latitude = value.get("lat")
        longitude = value.get("lng", value.get("lon"))
        if latitude is not None and longitude is not None:
            return float(latitude), float(longitude)
    if isinstance(value, str):
        latitude, longitude = value.split(",", maxsplit=1)
        return float(latitude), float(longitude)
    return None


def _result_points(result: dict[str, Any]) -> list[tuple[float, float]]:
    shape = result.get("location", {}).get("shape", {})
    raw_points: list[Any] = []
    if isinstance(shape.get("links"), list):
        for link in shape["links"]:
            raw_points.extend(link.get("points", []))
    if not raw_points:
        raw_points = shape.get("points", [])
    return [point for value in raw_points if (point := _point(value)) is not None]


def _distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    first_lat, first_lon = map(math.radians, first)
    second_lat, second_lon = map(math.radians, second)
    delta_lat = second_lat - first_lat
    delta_lon = second_lon - first_lon
    value = math.sin(delta_lat / 2) ** 2 + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(value))


def parse_flow_results(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert HERE results into one record per road-flow geometry."""
    records: list[dict[str, Any]] = []
    for result in results:
        points = _result_points(result)
        current = result.get("currentFlow", {})
        speed = float(current.get("speed", 0) or 0)
        free_flow = float(current.get("freeFlow", 0) or 0)
        if len(points) < 2 or speed <= 0 or free_flow <= 0:
            continue
        length_km = sum(_distance_km(first, second) for first, second in zip(points, points[1:]))
        delay_seconds = max(0.0, length_km / speed * 3600 - length_km / free_flow * 3600)
        midpoint = points[len(points) // 2]
        records.append(
            {
                "latitude": midpoint[0],
                "longitude": midpoint[1],
                "length_km": length_km,
                "speed_kph": speed,
                "free_flow_kph": free_flow,
                "jam_factor": float(current.get("jamFactor", 0) or 0),
                "delay_seconds": delay_seconds,
            }
        )
    return pd.DataFrame(records)


def _point_to_segment_distance_km(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> float:
    mean_lat = math.radians((start[0] + end[0] + point[0]) / 3)
    scale_x = EARTH_RADIUS_KM * math.cos(mean_lat) * math.pi / 180
    scale_y = EARTH_RADIUS_KM * math.pi / 180
    px, py = point[1] * scale_x, point[0] * scale_y
    sx, sy = start[1] * scale_x, start[0] * scale_y
    ex, ey = end[1] * scale_x, end[0] * scale_y
    dx, dy = ex - sx, ey - sy
    denominator = dx * dx + dy * dy
    factor = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / denominator)) if denominator else 0.0
    nearest = (sx + factor * dx, sy + factor * dy)
    return math.hypot(px - nearest[0], py - nearest[1])


def match_flow_to_patterns(
    flow: pd.DataFrame,
    pattern_stops: pd.DataFrame,
    max_distance_km: float = 0.35,
) -> pd.DataFrame:
    """Match nearby HERE road-flow midpoints to provisional GTFS segments."""
    if flow.empty:
        return pd.DataFrame()
    segments: list[dict[str, Any]] = []
    ordered = pattern_stops.sort_values(["pattern_id", "stop_sequence"])
    for pattern_id, group in ordered.groupby("pattern_id"):
        stops = group.dropna(subset=["stop_lat", "stop_lon"])
        rows = list(stops.itertuples())
        for start, end in zip(rows, rows[1:]):
            segments.append(
                {
                    "pattern_id": pattern_id,
                    "route_short_name": start.route_short_name,
                    "direction_label": start.direction_label,
                    "start": (float(start.stop_lat), float(start.stop_lon)),
                    "end": (float(end.stop_lat), float(end.stop_lon)),
                }
            )
    matches: list[dict[str, Any]] = []
    for flow_row in flow.itertuples(index=False):
        point = (flow_row.latitude, flow_row.longitude)
        nearest = min(
            segments,
            key=lambda segment: _point_to_segment_distance_km(point, segment["start"], segment["end"]),
            default=None,
        )
        if nearest is None:
            continue
        distance = _point_to_segment_distance_km(point, nearest["start"], nearest["end"])
        if distance <= max_distance_km:
            matches.append(
                {
                    "pattern_id": nearest["pattern_id"],
                    "route_short_name": nearest["route_short_name"],
                    "direction_label": nearest["direction_label"],
                    "distance_km": distance,
                    "length_km": flow_row.length_km,
                    "speed_kph": flow_row.speed_kph,
                    "free_flow_kph": flow_row.free_flow_kph,
                    "jam_factor": flow_row.jam_factor,
                    "delay_seconds": flow_row.delay_seconds,
                }
            )
    return pd.DataFrame(matches)


def summarize_traffic(matches: pd.DataFrame, patterns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate matched flow into pattern and line-direction delay estimates."""
    if matches.empty:
        empty = pd.DataFrame(columns=["pattern_id", "traffic_delay_seconds", "traffic_jam_factor", "matched_flow_segments"])
        return empty, pd.DataFrame(columns=["route_short_name", "direction_label", "traffic_delay_seconds", "traffic_jam_factor", "matched_flow_segments"])
    weighted = matches.assign(weight=matches["length_km"].clip(lower=0.001))
    rows: list[dict[str, Any]] = []
    for (pattern_id, route_short_name), group in weighted.groupby(["pattern_id", "route_short_name"]):
        total_weight = group["weight"].sum()
        rows.append(
            {
                "pattern_id": pattern_id,
                "route_short_name": route_short_name,
                "traffic_delay_seconds": (group["delay_seconds"] * group["weight"]).sum() / total_weight,
                "traffic_jam_factor": (group["jam_factor"] * group["weight"]).sum() / total_weight,
                "matched_flow_segments": len(group),
            }
        )
    pattern_summary = pd.DataFrame(rows)
    pattern_summary = patterns[["pattern_id", "route_short_name", "direction_label"]].merge(
        pattern_summary, on=["pattern_id", "route_short_name"], how="right"
    )
    route_summary = pattern_summary.groupby(["route_short_name", "direction_label"], as_index=False).agg(
        traffic_delay_seconds=("traffic_delay_seconds", "mean"),
        traffic_jam_factor=("traffic_jam_factor", "mean"),
        matched_flow_segments=("matched_flow_segments", "sum"),
    )
    return pattern_summary, route_summary
