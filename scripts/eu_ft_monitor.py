#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "eu-funding-tenders" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "eu-funding-tenders" / "runs"
BASE = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
PORTAL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities"

SEARCH_TERMS = [
    "earth observation",
    "remote sensing",
    "satellite data",
    "geospatial",
    "Copernicus",
    "onboard AI",
    "drone",
    "wildfire",
    "water resources",
    "hydrology",
    "drought",
    "agriculture monitoring",
    "archaeology",
    "cultural heritage",
    "critical infrastructure",
    "civil security disaster",
]

STATUS = {
    "31094502": "Open",
}


@dataclass
class Match:
    item: dict[str, Any]
    score: int
    matched_terms: list[str]
    urgency: str
    days_to_deadline: int | None
    consortium_burden: str


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def first(meta: dict[str, list[Any]], key: str) -> str:
    values = meta.get(key) or []
    if not values:
        return ""
    value = values[0]
    return "" if value is None else str(value)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    value = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def contains_term(text: str, term: str) -> bool:
    stripped = term.lower().strip()
    if not stripped:
        return False
    pattern = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----geok-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n'.encode())
        chunks.append(b"Content-Type: application/json\r\n\r\n")
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def fetch_search(term: str, page_size: int) -> dict[str, Any]:
    params = urlencode({"apiKey": "SEDIA", "text": term, "pageSize": str(page_size), "language": "en"})
    query = {
        "bool": {
            "must": [
                {"terms": {"type": ["1", "2", "8"]}},
                {"terms": {"status": ["31094502"]}},
                {"term": {"programmePeriod": "2021 - 2027"}},
                {"term": {"language": "en"}},
            ]
        }
    }
    body, boundary = multipart({"query": json.dumps(query)})
    req = Request(
        f"{BASE}?{params}",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Geo-K funding scout",
        },
    )
    try:
        with urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError):
        result = subprocess.run(
            [
                "curl",
                "-Ls",
                "-X",
                "POST",
                f"{BASE}?{params}",
                "-F",
                f"query={json.dumps(query)};type=application/json",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        return json.loads(result.stdout)


def text_blob(item: dict[str, Any]) -> str:
    meta = item.get("metadata") or {}
    parts = [
        item.get("summary", ""),
        item.get("content", ""),
        first(meta, "title"),
        first(meta, "descriptionByte"),
        first(meta, "destinationDescription"),
        first(meta, "keywords"),
        first(meta, "typesOfAction"),
        first(meta, "callTitle"),
        first(meta, "identifier"),
        first(meta, "callIdentifier"),
    ]
    return clean_html(" ".join(parts))


def score_item(item: dict[str, Any], cfg: dict[str, Any]) -> tuple[int, list[str]]:
    text = text_blob(item)
    for term in cfg["exclude_keywords"]:
        if contains_term(text, term):
            return 0, []
    score = 0
    matched: list[str] = []
    for term in cfg["focus_keywords"]:
        if contains_term(text, term):
            matched.append(term.strip())
            score += cfg.get("priority_terms", {}).get(term, 1)
    return score, sorted(set(matched))


def passes_relevance(item: dict[str, Any], cfg: dict[str, Any], score: int, terms: list[str]) -> bool:
    if score < int(cfg.get("minimum_score", 2)):
        return False
    text = text_blob(item)
    hard_anchors = [
        "earth observation",
        "remote sensing",
        "geospatial",
        "geo-information",
        "Copernicus",
        "satellite",
        "drone",
        "uav",
        "wildfire",
        "water",
        "hydrology",
        "hydrological",
        "wetland",
        "drought",
        "irrigation",
        "flood",
        "pollution",
        "river",
        "lake",
        "agriculture",
        "crop",
        "archaeology",
        "archaeological",
        "critical infrastructure",
        "critical infrastructures",
        "critical entities",
        "infrastructure resilience",
        "stress tests of critical infrastructure",
    ]
    if not any(contains_term(text, term) for term in hard_anchors):
        return False
    generic_only = {
        "ai",
        "artificial intelligence",
        "image",
        "imaging",
        "validation",
        "quality",
        "thermal",
        "processing",
        "security",
        "civil security",
        "heritage",
        "cultural heritage",
    }
    return not set(terms).issubset(generic_only)


def deadline_for(item: dict[str, Any]) -> datetime | None:
    meta = item.get("metadata") or {}
    direct = parse_dt(first(meta, "deadlineDate"))
    if direct:
        return direct
    try:
        actions = json.loads(first(meta, "actions") or "[]")
    except json.JSONDecodeError:
        return None
    for action in actions:
        for date in action.get("deadlineDates") or []:
            parsed = parse_dt(date)
            if parsed:
                return parsed
    return None


def opening_for(item: dict[str, Any]) -> str:
    meta = item.get("metadata") or {}
    direct = parse_dt(first(meta, "startDate") or first(meta, "es_SortDate"))
    if direct:
        return direct.date().isoformat()
    try:
        actions = json.loads(first(meta, "actions") or "[]")
    except json.JSONDecodeError:
        return ""
    for action in actions:
        parsed = parse_dt(action.get("plannedOpeningDate"))
        if parsed:
            return parsed.date().isoformat()
    return ""


def urgency_for(deadline: datetime | None, now: datetime) -> tuple[str, int | None]:
    if not deadline:
        return "BLUE - monitor/no deadline", None
    days = (deadline.date() - now.date()).days
    if days < 0:
        return "GRAY - deadline passed", days
    if days <= 7:
        return "RED - due <=7 days", days
    if days <= 14:
        return "ORANGE - due <=14 days", days
    if days <= 30:
        return "AMBER - due <=30 days", days
    return "GREEN - due >30 days", days


def consortium_burden(item: dict[str, Any]) -> str:
    meta = item.get("metadata") or {}
    text = text_blob(item).lower()
    action = first(meta, "typesOfAction")
    if any(term in text for term in ["consortium", "consortia", "at least three legal entities"]):
        return "HIGH - consortium likely"
    if "horizon" in action.lower() and any(kind in action.lower() for kind in ["research", "innovation"]):
        return "HIGH - Horizon RIA/IA usually consortium"
    if "coordination" in action.lower():
        return "MEDIUM - partner/user network likely"
    return "MEDIUM - check topic rules"


def normalized_url(item: dict[str, Any]) -> str:
    meta = item.get("metadata") or {}
    identifier = first(meta, "identifier")
    if identifier:
        return f"{PORTAL}/topic-details/{identifier}"
    return item.get("url") or ""


def write_outputs(matches: list[Match], now: datetime, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for match in matches:
        item = match.item
        meta = item.get("metadata") or {}
        deadline = deadline_for(item)
        identifier = first(meta, "identifier")
        rows.append(
            {
                "Source": "EU Funding & Tenders",
                "Provider": "European Commission",
                "Programme": first(meta, "callTitle") or first(meta, "frameworkProgramme"),
                "Call ID": first(meta, "callIdentifier"),
                "Topic ID": identifier,
                "Title": first(meta, "title") or clean_html(item.get("summary")),
                "Status": STATUS.get(first(meta, "status"), first(meta, "status") or "Open"),
                "Type": first(meta, "typesOfAction"),
                "Opened": opening_for(item),
                "Deadline": "" if not deadline else deadline.isoformat(),
                "Clarification": "",
                "Geography / Eligibility": "EU/associated country rules; verify topic-specific restrictions",
                "Consortium Burden": match.consortium_burden,
                "Urgency": match.urgency,
                "Days": "" if match.days_to_deadline is None else str(match.days_to_deadline),
                "Score": str(match.score),
                "Matched Terms": ", ".join(match.matched_terms[:12]),
                "Theme": text_blob(item)[:700],
                "URL": normalized_url(item),
            }
        )

    with (out_dir / "geok-eu-ft-monitor.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["Source"])
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "matched-opportunities.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Geo-K EU Funding & Tenders Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Active future-deadline records from the EU Funding & Tenders public SEDIA search API, filtered against the Geo-K profile.",
        "",
        "| Urgency | Days | Topic ID | Title | Type | Opened | Deadline | Consortium | Match |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['Urgency']} | {row['Days']} | {row['Topic ID']} | {row['Title']} | "
            f"{row['Type']} | {row['Opened']} | {row['Deadline']} | {row['Consortium Burden']} | {row['Matched Terms']} |"
        )
    (out_dir / "geok-eu-ft-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    page_size = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    now = datetime.now()
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    seen: dict[str, dict[str, Any]] = {}
    raw: dict[str, Any] = {}
    for term in SEARCH_TERMS:
        data = fetch_search(term, page_size)
        raw[term] = data
        for item in data.get("results") or []:
            meta = item.get("metadata") or {}
            key = first(meta, "identifier") or item.get("reference") or item.get("url")
            if key:
                seen[str(key)] = item

    (run_dir / "raw-search-results.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    matches: list[Match] = []
    for item in seen.values():
        deadline = deadline_for(item)
        if deadline and deadline.date() < now.date():
            continue
        score, terms = score_item(item, cfg)
        if not terms or not passes_relevance(item, cfg, score, terms):
            continue
        urgency, days = urgency_for(deadline, now)
        matches.append(Match(item, score, terms, urgency, days, consortium_burden(item)))

    urgency_rank = {"RED": 0, "ORANGE": 1, "AMBER": 2, "GREEN": 3, "BLUE": 4}
    matches.sort(
        key=lambda m: (
            urgency_rank.get(m.urgency.split()[0], 9),
            9999 if m.days_to_deadline is None else m.days_to_deadline,
            -m.score,
            first(m.item.get("metadata") or {}, "title"),
        )
    )
    write_outputs(matches, now, run_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["geok-eu-ft-monitor.csv", "geok-eu-ft-monitor.md", "matched-opportunities.json", "raw-search-results.json"]:
        shutil.copy2(run_dir / name, OUT_DIR / name)
    print(f"Searched {len(SEARCH_TERMS)} terms; matched {len(matches)} EU Funding & Tenders records.")
    print(f"Archived run: {run_dir}")
    print(OUT_DIR / "geok-eu-ft-monitor.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
