#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "monitoring" / "funding-timing-patterns.md"

SOURCES = [
    ("ESA-star", ROOT / "funding-scout" / "monitoring" / "esa-star" / "latest" / "geok-opportunity-monitor.csv"),
    ("ESA Open Calls", ROOT / "funding-scout" / "monitoring" / "esa-open-calls" / "latest" / "geok-esa-open-calls-monitor.csv"),
    ("ESA Business Applications", ROOT / "funding-scout" / "monitoring" / "esa-business" / "latest" / "geok-esa-business-monitor.csv"),
    ("ESA Business Applications History", ROOT / "funding-scout" / "monitoring" / "esa-business" / "latest" / "geok-esa-business-all-calls.csv"),
    ("EU Funding & Tenders", ROOT / "funding-scout" / "monitoring" / "eu-funding-tenders" / "latest" / "geok-eu-ft-monitor.csv"),
    ("ECMWF Copernicus", ROOT / "funding-scout" / "monitoring" / "ecmwf-copernicus" / "latest" / "geok-ecmwf-monitor.csv"),
    ("LIFE CINEA", ROOT / "funding-scout" / "monitoring" / "life-cinea" / "latest" / "geok-life-monitor.csv"),
    ("FAO / UNGM", ROOT / "funding-scout" / "monitoring" / "fao-ungm" / "latest" / "geok-fao-ungm-monitor.csv"),
    ("Italian National", ROOT / "funding-scout" / "monitoring" / "italian-national" / "latest" / "geok-italian-national-monitor.csv"),
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    for candidate in (value, value.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y %H:%M:%S %Z", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def month_name(month: int) -> str:
    return datetime(2000, month, 1).strftime("%b")


def bucket_lead(days: int | None) -> str:
    if days is None:
        return "no open/close pair"
    if days <= 30:
        return "<=30d"
    if days <= 60:
        return "31-60d"
    if days <= 90:
        return "61-90d"
    return ">90d"


def source_profile(rows: list[dict[str, str]], source: str) -> dict[str, object]:
    now = datetime.now()
    lead_days: list[int] = []
    opened_months: Counter[int] = Counter()
    deadline_months: Counter[int] = Counter()
    urgency_counts: Counter[str] = Counter()
    evergreen = 0
    active_deadline_days: list[int] = []

    for row in rows:
        opened = parse_dt(row.get("Opened"))
        deadline = parse_dt(row.get("Deadline"))
        if opened:
            opened_months[opened.month] += 1
        if deadline:
            deadline_months[deadline.month] += 1
        else:
            evergreen += 1
        if opened and deadline:
            lead_days.append((deadline.date() - opened.date()).days)
        urgency = (row.get("Urgency") or "").split(" ", 1)[0]
        if urgency:
            urgency_counts[urgency] += 1
        days_raw = row.get("Days", "")
        try:
            days = int(float(days_raw)) if days_raw != "" else None
        except ValueError:
            days = None
        if days is not None and days >= 0:
            active_deadline_days.append(days)
        elif deadline and deadline.date() >= now.date():
            active_deadline_days.append((deadline.date() - now.date()).days)

    lead_bucket_counts = Counter(bucket_lead(days) for days in lead_days)
    active_urgent = sum(1 for days in active_deadline_days if days <= 30)
    urgent_share = active_urgent / len(active_deadline_days) if active_deadline_days else 0
    median_lead = median(lead_days) if lead_days else None
    min_lead = min(lead_days) if lead_days else None
    max_lead = max(lead_days) if lead_days else None
    likely_pattern = "Evergreen / rolling" if evergreen and evergreen >= max(1, len(rows) // 2) else "Fixed deadlines"
    if urgent_share >= 0.5 and active_deadline_days:
        likely_pattern = "Urgent-heavy current view"
    elif median_lead is not None and median_lead <= 45:
        likely_pattern = "Short windows"
    elif median_lead is not None and median_lead >= 90:
        likely_pattern = "Long windows"

    return {
        "source": source,
        "count": len(rows),
        "evergreen": evergreen,
        "median_lead": median_lead,
        "min_lead": min_lead,
        "max_lead": max_lead,
        "opened_months": opened_months,
        "deadline_months": deadline_months,
        "urgency_counts": urgency_counts,
        "lead_bucket_counts": lead_bucket_counts,
        "active_urgent": active_urgent,
        "active_deadlines": len(active_deadline_days),
        "likely_pattern": likely_pattern,
    }


def top_months(counter: Counter[int]) -> str:
    if not counter:
        return ""
    return ", ".join(f"{month_name(month)} ({count})" for month, count in counter.most_common(4))


def fmt_days(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(round(value)))
    return str(value)


def write_report(profiles: list[dict[str, object]], rows_by_source: dict[str, list[dict[str, str]]]) -> None:
    now = datetime.now()
    lines = [
        "# Funding Timing Patterns",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "This report uses the current monitor outputs. It is good enough to spot operating patterns, but it is not a complete multi-year procurement history unless the source exposes historic calls in its current feed.",
        "",
        "## Source Timing Summary",
        "",
        "| Source | Records | Pattern | Evergreen | Median lead days | Lead range | Main opening months | Main deadline months | Active <=30d |",
        "| --- | ---: | --- | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for profile in profiles:
        lead_range = ""
        if profile["min_lead"] is not None and profile["max_lead"] is not None:
            lead_range = f"{profile['min_lead']}-{profile['max_lead']}"
        active = f"{profile['active_urgent']}/{profile['active_deadlines']}" if profile["active_deadlines"] else ""
        lines.append(
            f"| {profile['source']} | {profile['count']} | {profile['likely_pattern']} | {profile['evergreen']} | "
            f"{fmt_days(profile['median_lead'])} | {lead_range} | {top_months(profile['opened_months'])} | "
            f"{top_months(profile['deadline_months'])} | {active} |"
        )

    lines.extend(
        [
            "",
            "## Working Interpretation",
            "",
            "- The monitor is deadline-driven, so it naturally feels urgent when we only react to RED/ORANGE rows.",
            "- ESA-star tenders can be especially unforgiving: when an item appears as issued, administrative setup, tender-package review, consortium decisions and ECOS costing may all be needed before the deadline.",
            "- ESA Business Applications/BASS has a different rhythm: the generic APQ route is rolling, while thematic calls can have fixed APQ windows. This makes BASS suitable for preparing reusable service concepts before a specific window appears.",
            "- EU and LIFE calls tend to have more predictable annual programmes, but they often need partners, users and consortium preparation before the portal deadline.",
            "- Procurement sources such as ECMWF, UNGM/FAO, ARPA/ISPRA and Italian national portals can still appear with short response windows, so the monitor should be treated as an alert layer, not the start of proposal preparation.",
            "",
            "## Practical Rule",
            "",
            "- RED/ORANGE: only pursue if concept, team, admin route and budget are already mostly ready.",
            "- AMBER: start only if the tender is narrow or Geo-K can reuse existing material.",
            "- GREEN/BLUE: use these to prepare the reusable concept, partner/user contacts, budget envelope and standard admin package.",
            "",
            "## Source Detail",
            "",
        ]
    )
    for source, rows in rows_by_source.items():
        lines.append(f"### {source}")
        if not rows:
            lines.append("")
            lines.append("No current rows.")
            lines.append("")
            continue
        for row in rows[:12]:
            bits = [
                row.get("Urgency", ""),
                row.get("Opened", ""),
                row.get("Deadline", ""),
                row.get("Title", ""),
            ]
            lines.append(f"- {' | '.join(bit for bit in bits if bit)}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rows_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for label, path in SOURCES:
        rows = read_rows(path)
        if label == "ESA Business Applications History":
            rows_by_source[label] = rows
        else:
            rows_by_source[label] = rows
    profiles = [source_profile(rows, source) for source, rows in rows_by_source.items()]
    write_report(profiles, rows_by_source)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
