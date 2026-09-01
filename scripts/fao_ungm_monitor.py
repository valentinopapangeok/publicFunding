#!/usr/bin/env python3
"""Monitor FAO procurement notices published through UNGM."""

from __future__ import annotations

import csv
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import request
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "fao-ungm" / "latest"
SEARCH_URL = "https://www.ungm.org/Public/Notice/Search"
PUBLIC_NOTICE_BASE = "https://www.ungm.org/Public/Notice"
FAO_AGENCY_ID = 49

SEARCH_TERMS = [
    "satellite",
    "remote sensing",
    "earth observation",
    "geospatial",
    "GIS",
    "drone",
    "UAV",
    "crop monitoring",
    "water resources",
    "hydrology",
    "drought",
    "wildfire",
    "forest fire",
    "archaeology",
    "cultural heritage",
]

GEOGRAPHY_KEEP = {
    "italy",
    "europe",
    "european",
    "global",
    "worldwide",
    "multiple",
    "regional",
    "mediterranean",
}


@dataclass(frozen=True)
class Notice:
    notice_id: str
    title: str
    deadline: str
    published: str
    agency: str
    notice_type: str
    reference: str
    country: str
    matched_terms: tuple[str, ...]


def post_search(term: str, field: str) -> str:
    payload = {
        "PageIndex": 0,
        "PageSize": 50,
        "Title": term if field == "Title" else "",
        "Description": term if field == "Description" else "",
        "Reference": "",
        "PublishedFrom": "",
        "PublishedTo": "",
        "DeadlineFrom": "",
        "DeadlineTo": "",
        "Countries": [],
        "Agencies": [FAO_AGENCY_ID],
        "UNSPSCs": [],
        "NoticeTypes": [],
        "SortField": "DatePublished",
        "SortAscending": False,
        "isPicker": False,
        "IsSustainable": False,
        "IsActive": True,
        "NoticeDisplayType": None,
        "NoticeSearchTotalLabelId": "noticeSearchTotal",
        "TypeOfCompetitions": [],
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        SEARCH_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Geo-K funding monitor"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=45) as response:
            return response.read().decode("utf-8", errors="replace")
    except URLError:
        result = subprocess.run(
            [
                "curl",
                "-Ls",
                "-X",
                "POST",
                SEARCH_URL,
                "-H",
                "Content-Type: application/json",
                "--data",
                json.dumps(payload),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_rows(page: str, term: str) -> list[Notice]:
    notices: list[Notice] = []
    for block in re.findall(
        r'<div role="row"[^>]+data-noticeid="([^"]+)"[^>]*class="[^"]*dataRow[^"]*"[^>]*>(.*?)</div>\s*<script>',
        page,
        flags=re.S,
    ):
        notice_id, row_html = block
        cells = re.findall(r'<div role="cell" class="tableCell[^"]*"(?: [^>]*)?>(.*?)</div>', row_html, flags=re.S)
        if len(cells) < 7:
            continue
        title = clean_text(cells[1])
        deadline = clean_text(cells[2])
        published = clean_text(cells[3])
        agency = clean_text(cells[4])
        notice_type = clean_text(cells[5])
        reference = clean_text(cells[6])
        country = clean_text(cells[7]) if len(cells) > 7 else ""
        notices.append(
            Notice(
                notice_id=notice_id,
                title=title,
                deadline=deadline,
                published=published,
                agency=agency,
                notice_type=notice_type,
                reference=reference,
                country=country,
                matched_terms=(term,),
            )
        )
    return notices


def geography_allowed(country: str) -> bool:
    normalized = country.strip().lower()
    if not normalized:
        return True
    return any(token in normalized for token in GEOGRAPHY_KEEP)


def urgency(deadline: str) -> tuple[str, str]:
    match = re.search(r"(\d{2})-([A-Za-z]{3})-(\d{4})", deadline)
    if not match:
        return "GREY - date check", ""
    day, mon, year = match.groups()
    try:
        date = datetime.strptime(f"{day}-{mon}-{year}", "%d-%b-%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return "GREY - date check", ""
    days = (date - datetime.now(timezone.utc)).days
    if days <= 7:
        return "RED - immediate", str(days)
    if days <= 21:
        return "ORANGE - urgent", str(days)
    if days <= 45:
        return "AMBER - plan now", str(days)
    return "GREEN - monitor", str(days)


def theme_for(notice: Notice) -> str:
    text = f"{notice.title} {' '.join(notice.matched_terms)}".lower()
    themes = []
    if any(t in text for t in ("satellite", "remote sensing", "earth observation", "geospatial", "gis")):
        themes.append("EO / geospatial")
    if any(t in text for t in ("drone", "uav")):
        themes.append("drones")
    if any(t in text for t in ("water", "hydrology", "drought")):
        themes.append("water resources")
    if any(t in text for t in ("crop", "agriculture")):
        themes.append("agriculture monitoring")
    if any(t in text for t in ("wildfire", "forest fire")):
        themes.append("wildfire")
    if any(t in text for t in ("archaeology", "heritage")):
        themes.append("archaeology / cultural heritage")
    return "; ".join(themes) or "FAO procurement with possible geospatial component"


def merge_notices(notice_sets: list[Notice]) -> list[Notice]:
    merged: dict[str, Notice] = {}
    terms: dict[str, set[str]] = {}
    for notice in notice_sets:
        terms.setdefault(notice.notice_id, set()).update(notice.matched_terms)
        if notice.notice_id not in merged:
            merged[notice.notice_id] = notice
    return [
        Notice(
            notice_id=n.notice_id,
            title=n.title,
            deadline=n.deadline,
            published=n.published,
            agency=n.agency,
            notice_type=n.notice_type,
            reference=n.reference,
            country=n.country,
            matched_terms=tuple(sorted(terms[n.notice_id])),
        )
        for n in merged.values()
    ]


def main() -> int:
    all_matches: list[Notice] = []
    for term in SEARCH_TERMS:
        for field in ("Title", "Description"):
            page = post_search(term, field)
            all_matches.extend(parse_rows(page, term))

    notices = [n for n in merge_notices(all_matches) if geography_allowed(n.country)]
    notices.sort(key=lambda n: n.deadline)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "geok-fao-ungm-monitor.csv"
    md_path = OUT_DIR / "geok-fao-ungm-monitor.md"
    json_path = OUT_DIR / "geok-fao-ungm-monitor.json"

    fields = [
        "Source",
        "Provider",
        "Programme",
        "Call ID",
        "Topic ID",
        "Title",
        "Status",
        "Type",
        "Opened",
        "Deadline",
        "Clarification",
        "Geography / Eligibility",
        "Consortium Burden",
        "Urgency",
        "Days",
        "Score",
        "Matched Terms",
        "Theme",
        "URL",
    ]
    rows = []
    for notice in notices:
        urgency_label, days = urgency(notice.deadline)
        rows.append(
            {
                "Source": "UNGM",
                "Provider": "FAO",
                "Programme": "FAO procurement",
                "Call ID": notice.reference,
                "Topic ID": notice.notice_id,
                "Title": notice.title,
                "Status": "Open",
                "Type": notice.notice_type,
                "Opened": notice.published,
                "Deadline": notice.deadline,
                "Clarification": "",
                "Geography / Eligibility": notice.country or "Not specified",
                "Consortium Burden": "LOW/MEDIUM - supplier tender; verify registration and documents",
                "Urgency": urgency_label,
                "Days": days,
                "Score": str(20 + 5 * len(notice.matched_terms)),
                "Matched Terms": ", ".join(notice.matched_terms),
                "Theme": theme_for(notice),
                "URL": f"{PUBLIC_NOTICE_BASE}/{notice.notice_id}",
            }
        )

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    lines = [
        "# Geo-K FAO / UNGM Monitor",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Scope: active FAO notices on UNGM matching Geo-K EO/geospatial terms, restricted to Italian, European, Mediterranean, regional, global, or multi-country geography.",
        "",
    ]
    if rows:
        lines.append("| Urgency | Deadline | Geography | Title | Type | Match | Link |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in rows:
            lines.append(
                f"| {row['Urgency']} | {row['Deadline']} | {row['Geography / Eligibility']} | "
                f"{row['Title']} | {row['Type']} | {row['Matched Terms']} | [UNGM]({row['URL']}) |"
            )
    else:
        lines.extend(
            [
                "No active FAO notices matched the Geo-K profile after geography filtering.",
                "",
                "Operational note: UNGM is still worth monitoring because FAO occasionally publishes satellite-enabled agriculture and crop-monitoring tenders, but most active FAO procurement is country-specific and outside Geo-K's preferred geography.",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Matched {len(rows)} active FAO/UNGM records.")
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
