# ESA-star Monitoring

This folder contains the lightweight ESA-star monitor used for Geo-K public-funding scouting.

It does not scrape the rendered ESA-star page. ESA-star serves the visible page as a JavaScript app shell, while the tender data is available through public API endpoints used by that frontend.

## Run

```sh
python3 scripts/esastar_monitor.py
```

An app automation named `Geo-K ESA-star Funding Monitor` is active with id `geo-k-esa-star-funding-monitor`. It runs this monitor on weekdays and summarizes urgent or newly relevant items.

Outputs are written to:

```text
funding-scout/monitoring/esa-star/latest/
```

The monitor saves:

- `all-tenders.json` - raw ESA-star tender list snapshot.
- `matched-tenders.json` - Geo-K-relevant matched records.
- `geok-opportunity-monitor.md` - readable status report.
- `geok-opportunity-monitor.csv` - spreadsheet-ready table.

## Urgency Bands

- Red: issued and due in 7 days or less.
- Orange: issued and due in 14 days or less.
- Amber: issued and due in 30 days or less.
- Green: issued and due later than 30 days.
- Blue: intended or no formal closing date yet.
- Gray: closed, in evaluation, awarded, completed, cancelled, or archived.

## Why This Exists

Manual scouting missed open Earth Action calls because the visible ESA EO pages expose broad opportunity descriptions and quarters, while ESA-star details are rendered from API data after the JavaScript app loads. A proper tracker must query ESA-star API records directly and diff them over time.
