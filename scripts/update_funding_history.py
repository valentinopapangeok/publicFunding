#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORY_CSV = ROOT / "monitoring" / "funding-history.csv"
HISTORY_JSON = ROOT / "site" / "esa-star-monitor" / "history.json"
SITE_HISTORY_CSV = ROOT / "site" / "esa-star-monitor" / "history.csv"
SITE_REPORT = ROOT / "site" / "esa-star-monitor" / "funding-history-patterns.md"
REPORT = ROOT / "monitoring" / "funding-history-patterns.md"

SOURCE_CSVS = [
    ("ESA-star", ROOT / "funding-scout" / "monitoring" / "esa-star" / "latest" / "geok-opportunity-monitor.csv"),
    ("ESA Open Calls", ROOT / "funding-scout" / "monitoring" / "esa-open-calls" / "latest" / "geok-esa-open-calls-monitor.csv"),
    ("ESA Business Applications", ROOT / "funding-scout" / "monitoring" / "esa-business" / "latest" / "geok-esa-business-monitor.csv"),
    ("EU Funding & Tenders", ROOT / "funding-scout" / "monitoring" / "eu-funding-tenders" / "latest" / "geok-eu-ft-monitor.csv"),
    ("ECMWF Copernicus", ROOT / "funding-scout" / "monitoring" / "ecmwf-copernicus" / "latest" / "geok-ecmwf-monitor.csv"),
    ("LIFE CINEA", ROOT / "funding-scout" / "monitoring" / "life-cinea" / "latest" / "geok-life-monitor.csv"),
    ("FAO / UNGM", ROOT / "funding-scout" / "monitoring" / "fao-ungm" / "latest" / "geok-fao-ungm-monitor.csv"),
    ("Italian National", ROOT / "funding-scout" / "monitoring" / "italian-national" / "latest" / "geok-italian-national-monitor.csv"),
]

FIELDNAMES = [
    "History Key",
    "Source",
    "Provider",
    "Programme",
    "Call ID",
    "Topic ID",
    "Title",
    "Type",
    "URL",
    "Opened",
    "Deadline",
    "First Seen",
    "Last Seen",
    "Seen Snapshots",
    "Seen Count",
    "Currently Matched",
    "Last Status",
    "Last Urgency",
    "Last Days",
    "Score",
    "Matched Terms",
    "Theme",
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_dt(value: str | None) -> datetime | None:
    value = clean(value)
    if not value:
        return None
    for candidate in (value, value.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def iso_date(value: str | None) -> str:
    parsed = parse_dt(value)
    return parsed.date().isoformat() if parsed else clean(value)


def stable_key(row: dict[str, str]) -> str:
    parts = [
        row.get("Source", ""),
        row.get("Call ID", ""),
        row.get("Topic ID", ""),
        row.get("URL", ""),
        row.get("Title", ""),
    ]
    text = "|".join(clean(part).lower() for part in parts if clean(part))
    return re.sub(r"\s+", " ", text)[:700]


def normalize_row(source_hint: str, row: dict[str, str]) -> dict[str, str]:
    if source_hint == "ESA-star" or "TA" in row:
        normalized = {
            "Source": "ESA-star",
            "Provider": "ESA",
            "Programme": "",
            "Call ID": row.get("TA", ""),
            "Topic ID": row.get("ID", ""),
            "Title": row.get("Title", ""),
            "Type": row.get("Type", ""),
            "URL": row.get("ESA-star", ""),
            "Opened": row.get("Opened", ""),
            "Deadline": row.get("Deadline", ""),
            "Last Status": row.get("Status", ""),
            "Last Urgency": row.get("Urgency", ""),
            "Last Days": row.get("Days", ""),
            "Score": row.get("Score", ""),
            "Matched Terms": row.get("Matched Terms", ""),
            "Theme": row.get("Theme", ""),
        }
    else:
        normalized = {
            "Source": row.get("Source", source_hint),
            "Provider": row.get("Provider", ""),
            "Programme": row.get("Programme", ""),
            "Call ID": row.get("Call ID", ""),
            "Topic ID": row.get("Topic ID", ""),
            "Title": row.get("Title", ""),
            "Type": row.get("Type", ""),
            "URL": row.get("URL", ""),
            "Opened": row.get("Opened", ""),
            "Deadline": row.get("Deadline", ""),
            "Last Status": row.get("Status", ""),
            "Last Urgency": row.get("Urgency", ""),
            "Last Days": row.get("Days", ""),
            "Score": row.get("Score", ""),
            "Matched Terms": row.get("Matched Terms", ""),
            "Theme": row.get("Theme", ""),
        }
    for key, value in list(normalized.items()):
        normalized[key] = clean(value)
    normalized["Opened"] = iso_date(normalized["Opened"])
    normalized["Deadline"] = iso_date(normalized["Deadline"])
    normalized["History Key"] = stable_key(normalized)
    return normalized


def snapshot_date_from_path(path: Path, default: str) -> str:
    for part in path.parts:
        if re.fullmatch(r"20\d{6}-\d{6}", part):
            return f"{part[:4]}-{part[4:6]}-{part[6:8]}"
    return default


def iter_snapshot_rows(include_runs: bool, today: str) -> list[tuple[dict[str, str], str, bool]]:
    snapshots: list[tuple[dict[str, str], str, bool]] = []
    for source, path in SOURCE_CSVS:
        for row in read_csv(path):
            normalized = normalize_row(source, row)
            if normalized["History Key"]:
                snapshots.append((normalized, today, True))
    if not include_runs:
        return snapshots
    for path in sorted((ROOT / "funding-scout" / "monitoring").glob("*/runs/*/*.csv")):
        source = source_from_run_path(path)
        snapshot_date = snapshot_date_from_path(path, today)
        for row in read_csv(path):
            normalized = normalize_row(source, row)
            if normalized["History Key"]:
                snapshots.append((normalized, snapshot_date, False))
    return snapshots


def source_from_run_path(path: Path) -> str:
    parent = path.parent.parent.parent.name
    return {
        "esa-star": "ESA-star",
        "esa-open-calls": "ESA Open Calls",
        "esa-business": "ESA Business Applications",
        "eu-funding-tenders": "EU Funding & Tenders",
        "ecmwf-copernicus": "ECMWF Copernicus",
        "life-cinea": "LIFE CINEA",
        "fao-ungm": "FAO / UNGM",
        "italian-national": "Italian National",
    }.get(parent, parent)


def load_history() -> dict[str, dict[str, str]]:
    history: dict[str, dict[str, str]] = {}
    for row in read_csv(HISTORY_CSV):
        key = row.get("History Key") or stable_key(row)
        if key:
            row["History Key"] = key
            history[key] = {field: row.get(field, "") for field in FIELDNAMES}
    return history


def merge_history(include_runs: bool) -> list[dict[str, str]]:
    today = datetime.now().date().isoformat()
    history = load_history()
    for row in history.values():
        row["Currently Matched"] = "no"

    for row, snapshot_date, is_current in iter_snapshot_rows(include_runs, today):
        key = row["History Key"]
        existing = history.get(key)
        if not existing:
            existing = {field: "" for field in FIELDNAMES}
            existing["History Key"] = key
            existing["First Seen"] = snapshot_date
            existing["Seen Count"] = "0"
            existing["Seen Snapshots"] = ""
            history[key] = existing

        existing["First Seen"] = min(filter(None, [existing.get("First Seen", ""), snapshot_date]))
        existing["Last Seen"] = max(filter(None, [existing.get("Last Seen", ""), snapshot_date]))
        snapshots = [part for part in existing.get("Seen Snapshots", "").split(";") if part]
        if snapshot_date not in snapshots:
            snapshots.append(snapshot_date)
        existing["Seen Snapshots"] = ";".join(sorted(snapshots))
        existing["Seen Count"] = str(len(snapshots))
        if is_current:
            existing["Currently Matched"] = "yes"
        for field in (
            "Source",
            "Provider",
            "Programme",
            "Call ID",
            "Topic ID",
            "Title",
            "Type",
            "URL",
            "Last Status",
            "Last Urgency",
            "Last Days",
            "Score",
            "Matched Terms",
            "Theme",
        ):
            if row.get(field):
                existing[field] = row[field]
        for field in ("Opened", "Deadline"):
            if row.get(field) and not existing.get(field):
                existing[field] = row[field]

    return sorted(history.values(), key=lambda item: (item["Source"], item["Deadline"] or "9999", item["Title"].lower()))


def month_label(counter: Counter[int]) -> str:
    if not counter:
        return ""
    return ", ".join(f"{MONTHS[month - 1]} ({count})" for month, count in counter.most_common(5))


def median(values: list[int]) -> int | None:
    if not values:
        return None
    values = sorted(values)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return round((values[middle - 1] + values[middle]) / 2)


def duration_bucket(days: int) -> str:
    if days <= 45:
        return "<=45d"
    if days <= 90:
        return "46-90d"
    if days <= 180:
        return "91-180d"
    return ">180d"


def write_history(rows: list[dict[str, str]]) -> None:
    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    HISTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    shutil.copyfile(HISTORY_CSV, SITE_HISTORY_CSV)


def write_report(rows: list[dict[str, str]]) -> None:
    by_source: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_source.setdefault(row["Source"], []).append(row)

    lines = [
        "# Funding History Patterns",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "This report uses the accumulated Geo-K monitor history. Opening/deadline statistics are only computed when a source exposes those dates.",
        "",
        "## Source Seasonality",
        "",
        "| Source | Calls | Current | Date pairs | Median open window | Window range | Opening months | Deadline months | First-seen months | Typical pattern |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for source, source_rows in sorted(by_source.items()):
        opening_months: Counter[int] = Counter()
        deadline_months: Counter[int] = Counter()
        first_seen_months: Counter[int] = Counter()
        buckets: Counter[str] = Counter()
        durations: list[int] = []
        current = sum(1 for row in source_rows if row.get("Currently Matched") == "yes")
        for row in source_rows:
            opened = parse_dt(row.get("Opened"))
            deadline = parse_dt(row.get("Deadline"))
            first_seen = parse_dt(row.get("First Seen"))
            if opened:
                opening_months[opened.month] += 1
            if deadline:
                deadline_months[deadline.month] += 1
            if first_seen:
                first_seen_months[first_seen.month] += 1
            if opened and deadline:
                days = (deadline.date() - opened.date()).days
                if days >= 0:
                    durations.append(days)
                    buckets[duration_bucket(days)] += 1
        pattern = "needs more history"
        med = median(durations)
        if med is not None:
            if med <= 45:
                pattern = "short-window"
            elif med <= 90:
                pattern = "medium-window"
            elif med <= 180:
                pattern = "long-window"
            else:
                pattern = "very long or rolling"
        if not deadline_months and any(not row.get("Deadline") for row in source_rows):
            pattern = "rolling/no fixed deadline"
        window_range = f"{min(durations)}-{max(durations)}d" if durations else ""
        lines.append(
            f"| {source} | {len(source_rows)} | {current} | {len(durations)} | "
            f"{'' if med is None else str(med) + 'd'} | {window_range} | {month_label(opening_months)} | "
            f"{month_label(deadline_months)} | {month_label(first_seen_months)} | {pattern} |"
        )

    lines.extend(
        [
            "",
            "## Window Buckets",
            "",
            "| Source | <=45d | 46-90d | 91-180d | >180d |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for source, source_rows in sorted(by_source.items()):
        buckets: Counter[str] = Counter()
        for row in source_rows:
            opened = parse_dt(row.get("Opened"))
            deadline = parse_dt(row.get("Deadline"))
            if opened and deadline:
                days = (deadline.date() - opened.date()).days
                if days >= 0:
                    buckets[duration_bucket(days)] += 1
        lines.append(
            f"| {source} | {buckets['<=45d']} | {buckets['46-90d']} | {buckets['91-180d']} | {buckets['>180d']} |"
        )

    lines.extend(
        [
            "",
            "## Reading The Pattern",
            "",
            "- `Opening months` are the actual issue/opening dates when the source exposes them.",
            "- `First-seen months` are when Geo-K's monitor first captured the call; this is useful for sources that do not expose a clean opening date.",
            "- `Date pairs` indicates how much evidence supports the open-window statistics for that source.",
            "- The history improves every day the monitor runs. For older years, we still need source-specific backfill, starting with EU Funding & Tenders and ESA Business Applications.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    SITE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPORT, SITE_REPORT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge current monitor outputs into a persistent funding history.")
    parser.add_argument("--include-runs", action="store_true", help="Also ingest local historical run folders as initial backfill.")
    args = parser.parse_args()
    rows = merge_history(include_runs=args.include_runs)
    write_history(rows)
    write_report(rows)
    print(f"Wrote {len(rows)} historical funding records")
    print(HISTORY_CSV)
    print(REPORT)
    print(HISTORY_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
