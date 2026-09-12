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
- `bus_pattern_traffic.csv`: HERE-Verkehrsschätzung je GTFS-Muster
- `bus_line_traffic.csv`: HERE-Verkehrsschätzung je Buslinie
- `plots/top_bus_patterns.png`: most frequent patterns by line
- `plots/bus_corridor_map.png`: a map of the most common corridor candidates
- `plots/bus_line_traffic_delay.png`: Linien-Ranking nach geschätzter Verzögerung
- `plots/bus_traffic_delay_map.png`: Korridore eingefärbt nach geschätzter Verzögerung

Die HERE-Werte beschreiben den aktuellen Straßenverkehr und sind deshalb eine
verkehrsbedingte Verzögerungsschätzung für Buskorridore, keine tatsächliche
Verspätung einzelner Busse. Die Zuordnung basiert derzeit auf geraden Linien
zwischen Haltestellen. Für bessere Ergebnisse sollte der nächste Schritt die
Korridore auf ein routingfähiges Straßennetz (z. B. OSRM oder Valhalla)
map-matchen.
