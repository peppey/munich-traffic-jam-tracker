"""Plots for derived bus corridor candidates."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_top_patterns(patterns: pd.DataFrame, output_path: Path) -> None:
    """Plot the most frequent service pattern for each bus line."""
    top = patterns.sort_values("trip_count", ascending=False).drop_duplicates("route_short_name")
    top = top.nlargest(25, "trip_count").sort_values("trip_count")
    figure, axis = plt.subplots(figsize=(10, 9), layout="constrained")
    axis.barh(top["route_short_name"], top["trip_count"], color="#00796b")
    axis.set(title="Haeufigste Muenchner Busfahrmuster", xlabel="Fahrten im GTFS-Feed", ylabel="Buslinie")
    axis.grid(axis="x", alpha=0.25)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def plot_corridor_map(patterns: pd.DataFrame, pattern_stops: pd.DataFrame, output_path: Path) -> None:
    """Plot provisional stop-to-stop corridors for common patterns."""
    selected_ids = set(patterns.nlargest(35, "trip_count")["pattern_id"])
    stops = pattern_stops.loc[pattern_stops["pattern_id"].isin(selected_ids)].copy()
    figure, axis = plt.subplots(figsize=(10, 10), layout="constrained")
    for pattern_id, group in stops.sort_values("stop_sequence").groupby("pattern_id"):
        line = group["route_short_name"].iat[0]
        axis.plot(group["stop_lon"], group["stop_lat"], linewidth=1.1, alpha=0.55, label=line)
    axis.set(title="Vorlaeufige Buskorridore aus Haltestellenfolgen", xlabel="Laengengrad", ylabel="Breitengrad")
    axis.set_aspect("equal", adjustable="box")
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
