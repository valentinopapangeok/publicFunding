#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "esa-business" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "esa-business" / "runs"
OPEN_CFP_LIST_URL = "https://business.esa.int/OpenCfPlist"

FIELDNAMES = [
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

BUSINESS_TERMS = {
    "business applications": 4,
    "space solutions": 4,
    "artes": 3,
    "bass": 4,
    "downstream applications": 4,
    "activity pitch questionnaire": 4,
    "apq": 3,
    "outline proposal": 3,
    "demonstration project": 3,
    "feasibility study": 2,
    "pilot project": 3,
    "kick-start": 3,
    "customer": 2,
    "users": 2,
    "national delegation": 3,
}


@dataclass(frozen=True)
class BusinessCall:
    title: str
    url: str
    list_title: str
    source_text: str


def clean(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value.replace("\xa0", " "))
    return re.sub(r"\s+", " ", value).strip()


def fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Geo-K funding scout"})
    try:
        with urlopen(req, timeout=45) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        curl = shutil.which("curl")
        if not curl:
            raise
        result = subprocess.run(
            [curl, "-Ls", url],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        return result.stdout


def contains_term(text: str, term: str) -> bool:
    stripped = term.lower().strip()
    if not stripped:
        return False
    pattern = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def score_text(text: str, cfg: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for term in cfg["focus_keywords"]:
        if contains_term(text, term):
            matched.append(term.strip())
            score += int(cfg.get("priority_terms", {}).get(term, 1))
    for term, weight in BUSINESS_TERMS.items():
        if contains_term(text, term):
            matched.append(term)
            score += weight
    return score, sorted(set(matched))


def parse_date(value: str) -> datetime | None:
    value = value.strip()
    for pattern in (r"(\d{1,2})-(\d{1,2})-(20\d{2})", r"(\d{1,2})/(\d{1,2})/(20\d{2})"):
        match = re.search(pattern, value)
        if match:
            day, month, year = match.groups()
            return datetime(int(year), int(month), int(day), 23, 59)
    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", value)
    if match:
        day, month, year = match.groups()
        month_num = month_names.get(month.lower())
        if month_num:
            return datetime(int(year), month_num, int(day), 23, 59)
    return None


def first_date_after(label: str, text: str) -> datetime | None:
    match = re.search(rf"{label}\s+([0-9]{{1,2}}[-/][0-9]{{1,2}}[-/][0-9]{{4}})", text, flags=re.I)
    return parse_date(match.group(1)) if match else None


def apq_window(text: str) -> tuple[datetime | None, datetime | None]:
    match = re.search(
        r"Submission of APQ is possible from\s+(\d{1,2}\s+[A-Za-z]+\s+20\d{2})\s+until\s+(\d{1,2}\s+[A-Za-z]+\s+20\d{2})",
        text,
        flags=re.I,
    )
    if not match:
        return None, None
    return parse_date(match.group(1)), parse_date(match.group(2))


def urgency_for(deadline: datetime | None, now: datetime) -> tuple[str, str]:
    if not deadline:
        return "BLUE - open channel/no fixed deadline", ""
    days = (deadline.date() - now.date()).days
    if days < 0:
        return "GRAY - deadline passed", str(days)
    if days <= 7:
        return "RED - due <=7 days", str(days)
    if days <= 21:
        return "ORANGE - due <=21 days", str(days)
    if days <= 45:
        return "AMBER - due <=45 days", str(days)
    return "GREEN - due >45 days", str(days)


def call_id_for(title: str, text: str) -> str:
    match = re.search(r"\bAO\s*[-]?\s*(\d+-\d+)\b", f"{title} {text}", flags=re.I)
    if match:
        return f"AO {match.group(1)}"
    match = re.search(r"\bAO(\d{5})\b", f"{title} {text}", flags=re.I)
    return f"AO {match.group(1)}" if match else ""


def title_from_page(source: str, fallback: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", source, flags=re.I | re.S)
    title = clean(match.group(1)) if match else ""
    if title and "page not found" not in title.lower():
        return title
    match = re.search(r"<title[^>]*>(.*?)</title>", source, flags=re.I | re.S)
    title = clean(match.group(1)) if match else ""
    if title and "page not found" not in title.lower():
        return title.split("|", 1)[0].strip()
    return fallback


def parse_open_cfp_list(source: str) -> list[BusinessCall]:
    calls: list[BusinessCall] = []
    seen: set[str] = set()
    block_match = re.search(r'<div property="content:encoded".*?</blockquote>', source, flags=re.I | re.S)
    block = block_match.group(0) if block_match else source
    for match in re.finditer(r'<h4>\s*<a href="([^"]+)">(.*?)</a>\s*</h4>', block, flags=re.I | re.S):
        href, title_html = match.groups()
        title = clean(title_html)
        url = urljoin(OPEN_CFP_LIST_URL, href)
        if not title or url in seen:
            continue
        seen.add(url)
        calls.append(BusinessCall(title=title, url=url, list_title=title, source_text=""))
    return calls


def row_for(call: BusinessCall, cfg: dict[str, Any], now: datetime, include_closed: bool) -> dict[str, str] | None:
    source = fetch_html(call.url)
    title = title_from_page(source, call.title)
    if title == "ESA Space Solutions":
        title = call.list_title
    text = clean(source)
    if "page not found" in title.lower() and not call.list_title:
        return None
    opened = first_date_after("Opening date", text)
    deadline = first_date_after("Closing date", text)
    apq_opened, apq_deadline = apq_window(text)
    opened = opened or apq_opened
    deadline = deadline or apq_deadline
    if deadline and deadline.date() < now.date() and not include_closed:
        return None
    score, matched = score_text(f"{title} {text}", cfg)
    strategic = any(contains_term(f"{title} {text}", term) for term in BUSINESS_TERMS)
    if score < int(cfg.get("minimum_score", 2)) and not strategic:
        return None
    urgency, days = urgency_for(deadline, now)
    status = "Closed" if deadline and deadline.date() < now.date() else "Open"
    if not deadline:
        status = "Open / APQ any time"
    kind = "BASS Thematic Call" if "thematic call" in call.list_title.lower() or "thematic call" in text.lower() else "BASS Open Call"
    return {
        "Source": "ESA Business Applications",
        "Provider": "European Space Agency",
        "Programme": "ARTES 4.0 BASS",
        "Call ID": call_id_for(call.list_title, text),
        "Topic ID": "",
        "Title": title,
        "Status": status,
        "Type": kind,
        "Opened": "" if not opened else opened.isoformat(),
        "Deadline": "" if not deadline else deadline.isoformat(),
        "Clarification": "",
        "Geography / Eligibility": "Companies in ESA Member States subscribed to ARTES 4.0 BASS; check national delegation funding availability.",
        "Consortium Burden": "MEDIUM - BASS route; customer/user evidence, business case and National Delegation authorisation normally matter.",
        "Urgency": urgency,
        "Days": days,
        "Score": str(score),
        "Matched Terms": ", ".join(matched[:16]),
        "Theme": text[:900],
        "URL": call.url,
    }


def write_outputs(rows: list[dict[str, str]], all_rows: list[dict[str, str]], out_dir: Path, now: datetime) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "geok-esa-business-monitor.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    with (out_dir / "geok-esa-business-all-calls.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)
    (out_dir / "matched-opportunities.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Geo-K ESA Business Applications Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Urgency | Days | Type | Title | Opened | Deadline | Match |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['Urgency']} | {row['Days']} | {row['Type']} | [{row['Title']}]({row['URL']}) | "
            f"{row['Opened']} | {row['Deadline']} | {row['Matched Terms']} |"
        )
    (out_dir / "geok-esa-business-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now()
    source = fetch_html(OPEN_CFP_LIST_URL)
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "open-cfp-list.html").write_text(source, encoding="utf-8")
    calls = parse_open_cfp_list(source)
    all_rows = [row for call in calls if (row := row_for(call, cfg, now, include_closed=True))]
    rows = [row for row in all_rows if not row["Deadline"] or not row["Days"].startswith("-")]
    rows.sort(key=lambda row: (int(row["Days"]) if row["Days"].lstrip("-").isdigit() else 9999, row["Title"].lower()))
    all_rows.sort(key=lambda row: (row["Deadline"] or "9999", row["Title"].lower()))
    write_outputs(rows, all_rows, OUT_DIR, now)
    print(f"Matched {len(rows)} active ESA Business Applications records; retained {len(all_rows)} records for timing analysis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
