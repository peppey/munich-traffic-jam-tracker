# Munich Traffic Jam Tracker

This first version derives repeatable Munich bus corridor candidates from a
GTFS feed without `shapes.txt`. It keeps only configured Munich bus routes,
filters their stop sequences to the known Munich stops, and groups equal
ordered stop sequences into service patterns.

`direction_id` is used when the feed provides it. The currently configured
local feed does not contain that column, so the generated direction is a
stable `from_stop -> to_stop` label and the `pattern_id` includes the ordered
stop sequence.

## Run

Create the uv environment and install the package with development tools:

```bash
uv sync --dev
```

Run the test suite with:

```bash
uv run pytest
```

Generate the first corridor candidates with the local source data:

```bash
uv run munich-traffic-jam-tracker derive-patterns \
  --gtfs-dir '/Users/piabaronetzky/Downloads/latest 2' \
  --munich-stops ../mvv-delay-tracker/data/static/munich_stops.csv \
  --munich-lines ../mvv-delay-tracker/data/static/munich_lines.csv \
  --munich-boundary ../mvv-delay-tracker/data/static/munich.geojson
```

Results are written to `data/derived/`:

- `bus_patterns.csv`: one row per route, direction, and stop sequence
- `bus_pattern_stops.csv`: ordered stops for each pattern
- `bus_corridors.geojson`: line candidates joining consecutive stops
- `plots/top_bus_patterns.png`: most frequent patterns by line
- `plots/bus_corridor_map.png`: a map of the most common corridor candidates

The straight line between consecutive stops is only a provisional corridor.
The next stage should map-match it to a routable road network (for example
OSRM or Valhalla), then use that geometry to request HERE Traffic Flow data.
