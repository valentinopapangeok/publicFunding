# Geo-K ESA-star Funding Monitor

Public, sanitized monitor for active ESA-star funding opportunities relevant to Geo-K themes: Earth Observation, satellite image processing, wildfire, water, hydrology, drones/UAVs, autonomous systems, edge/on-board AI, SAR/SWIR/thermal, validation, veracity and provenance.

The monitor queries ESA-star public API data directly, filters active opportunities, assigns deadline urgency, and publishes a static GitHub Pages report.

## Published Report

After GitHub Pages is enabled with source set to **GitHub Actions**, the workflow publishes the site from:

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
