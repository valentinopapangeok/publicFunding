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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "life-cinea" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "life-cinea" / "runs"
URL = "https://cinea.ec.europa.eu/life-calls-proposals-2026_en"
COMMON_OPENING_DATE = "2026-04-21"

EXTRA_TERMS = {
    "LIFE": 1,
    "climate": 2,
    "adaptation": 2,
    "nature": 2,
    "biodiversity": 2,
    "zero pollution": 2,
    "environment": 1,
    "governance": 1,
    "digitalisation": 2,
    "distribution system operators": 2,
}


@dataclass
class Call:
    title: str
    url: str
    deadline_text: str


class ParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_p = False
        self.current: list[str] = []
        self.current_links: list[str] = []
        self.calls: list[Call] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self.in_p = True
            self.current = []
            self.current_links = []
        if self.in_p and tag == "a":
            attrs_d = {k: v or "" for k, v in attrs}
            if attrs_d.get("href"):
                self.current_links.append(normalize_url(attrs_d["href"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.in_p:
            text = clean(" ".join(self.current))
            if "Deadline date:" in text and len(text) > 20:
                title = text.split("Deadline date:", 1)[0]
                title = re.sub(r"Concept notes:\s*$", "", title).strip()
                title = re.sub(r"Full proposals:\s*$", "", title).strip()
                if title:
                    self.calls.append(Call(title=title, url=self.current_links[0] if self.current_links else URL, deadline_text=text))
            self.in_p = False

    def handle_data(self, data: str) -> None:
        if self.in_p:
            self.current.append(data)


def normalize_url(value: str) -> str:
    if "safelinks.protection.outlook.com" not in value:
        return value
    parsed = urlparse(html.unescape(value))
    original = parse_qs(parsed.query).get("url", [""])[0]
    return original or value


def clean(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html.unescape(value.replace("\xa0", " "))).strip()


def fetch_html() -> str:
    req = Request(URL, headers={"User-Agent": "Geo-K funding scout"})
    try:
        with urlopen(req, timeout=45) as resp:
            return resp.read().decode("utf-8")
    except (HTTPError, URLError):
        result = subprocess.run(
            ["curl", "-Ls", URL],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        return result.stdout


def parse_date(value: str) -> datetime | None:
    matches = re.findall(r"\d{1,2} [A-Za-z]+ \d{4}", value)
    for candidate in matches:
        try:
            parsed = datetime.strptime(candidate, "%d %B %Y")
        except ValueError:
            continue
        return parsed.replace(hour=17)
    return None


def parse_future_deadline(value: str, now: datetime) -> tuple[str, datetime | None]:
    matches = re.findall(r"(?:(Concept notes|Full proposals):\s*)?Deadline date:\s*(\d{1,2} [A-Za-z]+ \d{4})", value)
    for phase, date_text in matches:
        try:
            parsed = datetime.strptime(date_text, "%d %B %Y").replace(hour=17)
        except ValueError:
            continue
        if parsed.date() >= now.date():
            return (phase or "Deadline").strip(), parsed
    return "Deadline", parse_date(value)


def contains_term(text: str, term: str) -> bool:
    stripped = term.lower().strip()
    if not stripped:
        return False
    pattern = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def score(call: Call, cfg: dict[str, Any]) -> tuple[int, list[str]]:
    text = call.title
    score_value = 0
    matches: list[str] = []
    for term in cfg["focus_keywords"]:
        if contains_term(text, term):
            matches.append(term.strip())
            score_value += cfg.get("priority_terms", {}).get(term, 1)
    for term, weight in EXTRA_TERMS.items():
        if contains_term(text, term):
            matches.append(term)
            score_value += weight
    return score_value, sorted(set(matches))


def relevant(call: Call, terms: list[str], score_value: int) -> bool:
    if score_value < 2:
        return False
    text = call.title.lower()
    if any(term in text for term in ["operating grant", "framework partnership", "non-governmental organisations"]):
        return False
    keep_terms = {
        "climate",
        "adaptation",
        "nature",
        "biodiversity",
        "zero pollution",
        "environment",
        "digitalisation",
        "distribution system operators",
        "water",
        "hydrology",
        "wildfire",
        "forest",
        "pollution",
    }
    return any(term in keep_terms for term in terms)


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


def consortium_burden(call: Call) -> str:
    title = call.title.lower()
    if "strategic" in title or "integrated" in title:
        return "HIGH - large strategic LIFE project likely"
    if "technical assistance" in title:
        return "MEDIUM - may fit as specialist support"
    return "MEDIUM - LIFE SAP may allow focused partnership; verify topic"


def write_outputs(rows: list[dict[str, str]], out_dir: Path, now: datetime) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "geok-life-monitor.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["Source"])
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "matched-opportunities.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Geo-K LIFE/CINEA Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Urgency | Days | Title | Deadline | Consortium | Match |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['Urgency']} | {row['Days']} | {row['Title']} | {row['Deadline']} | "
            f"{row['Consortium Burden']} | {row['Matched Terms']} |"
        )
    (out_dir / "geok-life-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now()
    source_html = fetch_html()
    parser = ParagraphParser()
    parser.feed(source_html)
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "source.html").write_text(source_html, encoding="utf-8")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for call in parser.calls:
        phase, deadline = parse_future_deadline(call.deadline_text, now)
        if deadline and deadline.date() < now.date():
            continue
        score_value, terms = score(call, cfg)
        if not relevant(call, terms, score_value):
            continue
        key = f"{call.title}|{phase}|{deadline}"
        if key in seen:
            continue
        seen.add(key)
        urgency, days = urgency_for(deadline, now)
        rows.append(
            {
                "Source": "LIFE/CINEA",
                "Provider": "CINEA / European Commission",
                "Programme": "LIFE Programme 2026",
                "Call ID": "",
                "Topic ID": call.title,
                "Title": call.title,
                "Status": "Open",
                "Type": "Call for proposals",
                "Opened": COMMON_OPENING_DATE,
                "Deadline": "" if not deadline else deadline.isoformat(),
                "Clarification": "",
                "Geography / Eligibility": "EU LIFE eligible countries; verify topic",
                "Consortium Burden": consortium_burden(call),
                "Urgency": urgency,
                "Days": "" if days is None else str(days),
                "Score": str(score_value),
                "Matched Terms": ", ".join(terms[:12]),
                "Theme": f"{call.title}. Deadline phase: {phase}.",
                "URL": call.url,
            }
        )
    rows.sort(key=lambda item: (int(item["Days"] or 9999), item["Title"]))
    write_outputs(rows, run_dir, now)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["geok-life-monitor.csv", "geok-life-monitor.md", "matched-opportunities.json", "source.html"]:
        shutil.copy2(run_dir / name, OUT_DIR / name)
    print(f"Parsed {len(parser.calls)} LIFE rows; matched {len(rows)} active records.")
    print(f"Archived run: {run_dir}")
    print(OUT_DIR / "geok-life-monitor.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
