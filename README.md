# Geo-K ESA-star Funding Monitor

Public, sanitized monitor for active funding opportunities relevant to Geo-K. The implemented monitor currently covers ESA-star; the broader monitoring roadmap covers EU Funding & Tenders, LIFE/CINEA, ECMWF Copernicus procurement, and FAO/UNGM.

The monitor queries ESA-star public API data directly, filters active opportunities, assigns deadline urgency, and publishes a static GitHub Pages report.

Geo-K themes are separated from source portals:

- Source registry: `monitoring/funding-sources.json`
- Geo-K profile: `monitoring/geok-profile.md`
- Implementation roadmap: `monitoring/roadmap.md`
- ESA-star keyword profile: `monitoring/esa-star/geok-keywords.json`

Current Geo-K themes include Earth Observation, satellite image processing, wildfire, water/hydrology, agriculture, drones/UAVs, autonomous systems, edge/on-board AI, SAR/SWIR/thermal, validation/veracity/provenance, archaeology/cultural heritage, and critical infrastructure monitoring.

## Published Report

After GitHub Pages is enabled with source set to the **gh-pages branch**, the workflow publishes the site from:

```text
site/esa-star-monitor/
```

## Run Locally

```sh
python3 scripts/esastar_monitor.py 300
python3 scripts/build_esastar_pages_site.py
```

Generated local outputs:

```text
funding-scout/monitoring/esa-star/latest/
site/esa-star-monitor/index.html
site/esa-star-monitor/data.json
```

## Urgency

- RED: due in 7 days or less.
- ORANGE: due in 14 days or less.
- AMBER: due in 30 days or less.
- GREEN: due later than 30 days.
- BLUE: intended or no formal closing date yet.

Closed, passed-deadline, evaluation, awarded, completed, archived and cancelled records are excluded.

## Public Repo Scope

This public repository intentionally tracks only the monitor, workflow, keyword configuration, and generated static page. Proposal drafts, internal notes, downloaded tender documents, and presentation material are excluded by `.gitignore`.
