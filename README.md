# Munich Traffic Jam Tracker


## Run

Create the uv environment and install the package with development tools:

```bash
uv sync --dev
```

Run the test suite with:

```bash
uv run pytest
```

Generate corridor candidates from the CSV files in `data/static/`:

```bash
uv run munich-traffic-jam-tracker derive-patterns
```

Results are written to `data/derived/`:

- `bus_patterns.csv`: one row per route, direction, and stop sequence
- `bus_pattern_stops.csv`: ordered stops for each pattern
- `bus_corridors.geojson`: line candidates joining consecutive stops
- `bus_pattern_traffic.csv`: HERE-Verkehrsschätzung je GTFS-Muster
- `bus_line_traffic.csv`: HERE-Verkehrsschätzung je Buslinie und Richtung
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
