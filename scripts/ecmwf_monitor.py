#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "ecmwf-copernicus" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "ecmwf-copernicus" / "runs"
URL = "https://www.ecmwf.int/en/about/suppliers/copernicus-procurement/update-itts"

EXTRA_TERMS = {
    "C3S": 3,
    "CAMS": 3,
    "Copernicus": 3,
    "reanalysis": 3,
    "forecast": 2,
    "climate": 2,
    "emission": 2,
    "emissions": 2,
    "surface flux": 2,
    "solar radiation": 2,
    "quality control": 2,
    "EQC": 2,
    "evidence layer": 2,
}


@dataclass
class Row:
    reference: str
    ted_url: str
    title: str
    document_links: list[str]
    published: str
    deadline_text: str


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_target = False
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.current_links: list[str] = []
        self.rows: list[Row] = []
        self._last_heading = ""
        self._in_h2 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k: v or "" for k, v in attrs}
        if tag == "h2":
            self._last_heading = ""
            self._in_h2 = True
        if tag == "table" and "Links to published OJEU Contract Notices" in self._last_heading:
            self.in_table = True
        if self.in_table and tag == "tr":
            self.in_row = True
            self.current_row = []
            self.current_links = []
        if self.in_row and tag in ("td", "th"):
            self.in_cell = True
            self.current_cell = []
        if self.in_cell and tag == "a":
            href = attrs_d.get("href", "")
            if href:
                self.current_links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._last_heading = re.sub(r"\s+", " ", self._last_heading).strip()
            self._in_h2 = False
        if self.in_cell and tag in ("td", "th"):
            self.current_row.append(clean(" ".join(self.current_cell)))
            self.current_cell = []
            self.in_cell = False
        if self.in_table and tag == "tr":
            self._finish_row()
            self.in_row = False
        if self.in_table and tag == "table":
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)
        elif self._in_h2:
            self._last_heading += data

    def _finish_row(self) -> None:
        if len(self.current_row) != 4:
            return
        if self.current_row[0].lower() in ("itt reference", ""):
            return
        if not any(cell.strip() for cell in self.current_row):
            return
        links = self.current_links
        ted_url = next((link for link in links if "ted.europa.eu" in link), "")
        docs = [link for link in links if link.endswith(".pdf") or ".pdf?" in link]
        title = re.sub(r"\s+(?:C3S|CAMS)\w*_\w+\s+Volume\b.*$", "", self.current_row[1]).strip()
        self.rows.append(
            Row(
                reference=self.current_row[0].replace(" Change Notice", "").strip(),
                ted_url=ted_url,
                title=title or self.current_row[1],
                document_links=docs,
                published=self.current_row[2],
                deadline_text=self.current_row[3],
            )
        )


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
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    matches = re.findall(r"\d{1,2} [A-Za-z]+ \d{4}(?:, \d{1,2}:\d{2})?", value)
    if not matches:
        return None
    candidate = matches[-1]
    for fmt in ("%d %B %Y, %H:%M", "%d %B %Y"):
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def contains_term(text: str, term: str) -> bool:
    stripped = term.lower().strip()
    if not stripped:
        return False
    pattern = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def score(row: Row, cfg: dict[str, Any]) -> tuple[int, list[str]]:
    text = f"{row.reference} {row.title}"
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


def write_outputs(rows: list[dict[str, str]], out_dir: Path, now: datetime) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "geok-ecmwf-monitor.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["Source"])
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "matched-opportunities.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Geo-K ECMWF Copernicus Procurement Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Urgency | Days | Reference | Title | Published | Deadline | Match |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['Urgency']} | {row['Days']} | {row['Topic ID']} | {row['Title']} | "
            f"{row['Opened']} | {row['Deadline']} | {row['Matched Terms']} |"
        )
    (out_dir / "geok-ecmwf-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now()
    parser = TableParser()
    source_html = fetch_html()
    parser.feed(source_html)
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "source.html").write_text(source_html, encoding="utf-8")

    out_rows: list[dict[str, str]] = []
    for row in parser.rows:
        deadline = parse_date(row.deadline_text)
        if deadline and deadline.date() < now.date():
            continue
        score_value, terms = score(row, cfg)
        if score_value < 2:
            continue
        urgency, days = urgency_for(deadline, now)
        out_rows.append(
            {
                "Source": "ECMWF Copernicus",
                "Provider": "ECMWF",
                "Programme": "Copernicus C3S/CAMS procurement",
                "Call ID": row.reference,
                "Topic ID": row.reference,
                "Title": row.title,
                "Status": "Open",
                "Type": "Invitation to Tender",
                "Opened": row.published,
                "Deadline": "" if not deadline else deadline.isoformat(),
                "Clarification": "",
                "Geography / Eligibility": "EU and Copernicus participating states preferred; verify ITT",
                "Consortium Burden": "MEDIUM - supplier/subcontractor model possible; verify ITT",
                "Urgency": urgency,
                "Days": "" if days is None else str(days),
                "Score": str(score_value),
                "Matched Terms": ", ".join(terms[:12]),
                "Theme": row.title,
                "URL": row.ted_url or URL,
                "Document Links": " ".join(row.document_links),
            }
        )
    out_rows.sort(key=lambda item: (int(item["Days"] or 9999), item["Title"]))
    write_outputs(out_rows, run_dir, now)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["geok-ecmwf-monitor.csv", "geok-ecmwf-monitor.md", "matched-opportunities.json", "source.html"]:
        shutil.copy2(run_dir / name, OUT_DIR / name)
    print(f"Parsed {len(parser.rows)} ECMWF rows; matched {len(out_rows)} active records.")
    print(f"Archived run: {run_dir}")
    print(OUT_DIR / "geok-ecmwf-monitor.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
