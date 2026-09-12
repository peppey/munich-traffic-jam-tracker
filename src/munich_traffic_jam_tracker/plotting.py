"""Plots for derived bus corridor candidates."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.cm import ScalarMappable
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


def plot_traffic_delay_by_line(traffic_by_line: pd.DataFrame, output_path: Path) -> None:
    """Plot estimated road-traffic delay by bus line."""
    top = traffic_by_line.nlargest(25, "traffic_delay_seconds").sort_values("traffic_delay_seconds")
    figure, axis = plt.subplots(figsize=(10, 9), layout="constrained")
    axis.barh(top["route_short_name"].astype(str), top["traffic_delay_seconds"], color="#d95f02")
    axis.set(
        title="Geschaetzte verkehrsbedingte Verzoegerung je Buslinie",
        xlabel="Sekunden pro gematchtem HERE-Strassensegment",
        ylabel="Buslinie",
    )
    axis.grid(axis="x", alpha=0.25)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def plot_traffic_delay_map(
    traffic_by_pattern: pd.DataFrame,
    pattern_stops: pd.DataFrame,
    output_path: Path,
) -> None:
    """Plot GTFS corridors coloured by their estimated traffic delay."""
    selected = traffic_by_pattern.nlargest(35, "traffic_delay_seconds")
    selected_ids = set(selected["pattern_id"])
    stops = pattern_stops.loc[pattern_stops["pattern_id"].isin(selected_ids)].copy()
    delay_min = float(selected["traffic_delay_seconds"].min()) if not selected.empty else 0.0
    delay_max = float(selected["traffic_delay_seconds"].max()) if not selected.empty else 1.0
    normalizer = colors.Normalize(vmin=delay_min, vmax=max(delay_max, delay_min + 1))
    colormap = plt.get_cmap("YlOrRd")
    figure, axis = plt.subplots(figsize=(10, 10), layout="constrained")
    for pattern_id, group in stops.sort_values("stop_sequence").groupby("pattern_id"):
        delay = float(selected.loc[selected["pattern_id"] == pattern_id, "traffic_delay_seconds"].iloc[0])
        axis.plot(
            group["stop_lon"],
            group["stop_lat"],
            linewidth=1.8,
            alpha=0.75,
            color=colormap(normalizer(delay)),
        )
    axis.set(
        title="Geschaetzte HERE-Verzoegerung auf Buskorridoren",
        xlabel="Laengengrad",
        ylabel="Breitengrad",
    )
    axis.set_aspect("equal", adjustable="box")
    figure.colorbar(ScalarMappable(norm=normalizer, cmap=colormap), ax=axis, label="Sekunden")
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
