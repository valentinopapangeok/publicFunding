#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "esa-open-calls" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "esa-open-calls" / "runs"

OSIP_START_URL = "https://ideas.esa.int/core/servlet/hype/IMT?templateName=MenuItem&userAction=BrowseCurrentUser"
GSTP_ELEMENT_2_URL = (
    "https://ideas.esa.int/core/servlet/hype/IMT?"
    "documentId=d1b0bbb26bfd9c41bd3d3e4471325c40&"
    "documentTableId=45087596271774066&templateName=&userAction=Browse"
)

EXTRA_TERMS = {
    "osip": 3,
    "discovery": 3,
    "r&d": 3,
    "research": 2,
    "science": 2,
    "open call": 3,
    "call for ideas": 3,
    "request for information": 2,
    "gstp": 4,
    "element 2": 3,
    "make": 2,
    "co-funded": 3,
    "outline proposal": 3,
    "market oriented": 2,
    "earth": 1,
    "agri-food": 3,
    "agrifood": 3,
    "software": 2,
    "data": 2,
    "space-based data centres": 2,
    "autonomous software": 4,
    "hera": 2,
    "sustainability": 2,
    "lunar data": 2,
    "pnt": 2,
}

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


@dataclass(frozen=True)
class Opportunity:
    title: str
    kind: str
    url: str
    text: str
    item_id: str
    table_id: str


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
            score += cfg.get("priority_terms", {}).get(term, 1)
    for term, weight in EXTRA_TERMS.items():
        if contains_term(text, term):
            matched.append(term)
            score += weight
    return score, sorted(set(matched))


def parse_exact_date(text: str) -> datetime | None:
    for match in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})(?:,\s*Time\s*)?(?:\(?(\d{1,2}):(\d{2})\)?)?", text):
        day, month, year, hour, minute = match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 23), int(minute or 59))
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2}))?", text):
        year, month, day, hour, minute = match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 23), int(minute or 59))
    return None


def parse_relative_deadline(text: str, now: datetime) -> datetime | None:
    match = re.search(r"\bEnds in (a|\d+)\s+(day|days|week|weeks|month|months)\b", text, flags=re.I)
    if not match:
        return None
    amount_text, unit = match.groups()
    amount = 1 if amount_text.lower() == "a" else int(amount_text)
    if unit.lower().startswith("day"):
        days = amount
    elif unit.lower().startswith("week"):
        days = amount * 7
    else:
        days = amount * 30
    return now + timedelta(days=days)


def deadline_for(text: str, now: datetime) -> datetime | None:
    return parse_exact_date(text) or parse_relative_deadline(text, now)


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


def parse_osip_cards(source_html: str) -> list[Opportunity]:
    cards: list[Opportunity] = []
    pattern = re.compile(
        r'<div data-item-id="([^"]+)"[^>]*data-channel-carousel-item="([^"]+)"[^>]*'
        r'class="([^"]*(?:campaign|channel)[^"]*)">(.*?)(?=<div data-item-id=|</section>)',
        flags=re.I | re.S,
    )
    for match in pattern.finditer(source_html):
        item_id, href, class_name, block = match.groups()
        if "sia" in class_name:
            continue
        title_match = re.search(
            r'<h[14][^>]*>.*?<span class="textToBeCropped">(.*?)</span>',
            block,
            flags=re.I | re.S,
        )
        title = clean(title_match.group(1)) if title_match else ""
        text = clean(block)
        if not title or title.lower() in {"themes", "latest activity"}:
            continue
        kind = "OSIP Channel" if "channel" in class_name.lower() else "OSIP Campaign"
        url = urljoin("https://ideas.esa.int", html.unescape(href))
        table_match = re.search(r"documentTableId=([0-9]+)", url)
        table_id = table_match.group(1) if table_match else ""
        cards.append(Opportunity(title=title, kind=kind, url=url, text=text, item_id=item_id, table_id=table_id))
    return cards


def page_opportunity(url: str, fallback_kind: str) -> Opportunity:
    source_html = fetch_html(url)
    call_id_match = re.search(r"\b(Ca-\d{4}-\d{5})\b", source_html)
    title_match = re.search(r"<h1[^>]*>.*?<bdi[^>]*>(.*?)</bdi>", source_html, flags=re.I | re.S)
    if not title_match:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", source_html, flags=re.I | re.S)
    title = clean(title_match.group(1)) if title_match else "ESA open call"
    text = clean(source_html)
    item_match = re.search(r"documentId=([a-f0-9]{32})", url)
    table_match = re.search(r"documentTableId=([0-9]+)", url)
    return Opportunity(
        title=title,
        kind=fallback_kind,
        url=url,
        text=text,
        item_id=call_id_match.group(1) if call_id_match else (item_match.group(1) if item_match else ""),
        table_id=table_match.group(1) if table_match else "",
    )


def status_for(text: str) -> str:
    match = re.search(r"\bStatus:\s*([A-Za-z &]+)", text, flags=re.I)
    if match:
        return clean(match.group(1))
    if "submit your idea" in text.lower() or "go to campaign" in text.lower() or "open call" in text.lower():
        return "Submission"
    return "Open / check source"


def programme_for(opp: Opportunity) -> str:
    text = f"{opp.title} {opp.text}".lower()
    if "gstp" in text or "element 2" in text:
        return "GSTP Element 2 Make"
    if "discovery" in text:
        return "ESA Discovery / OSIP"
    if "pnt" in text or "navisp" in text:
        return "ESA PNT / OSIP"
    return "ESA OSIP"


def consortium_note(opp: Opportunity) -> str:
    text = f"{opp.title} {opp.text}".lower()
    if "gstp" in text or "element 2" in text:
        return "MEDIUM - industry-driven co-funded route; Outline Proposal, ESA-star registration and National Delegation Letter of Support expected"
    if "accelerator" in text or "commercial" in text or "business" in text or "customer" in text:
        return "MEDIUM - standalone idea possible, but commercial case, customer/user evidence or accelerator fit likely needed"
    if "co-sponsored" in text or "research organisations" in text or "academia" in text:
        return "LOW/MEDIUM - standalone or small-team R&D/science route; partner may help depending on campaign rules"
    if opp.kind == "OSIP Channel":
        return "LOW - open idea channel; standalone submission route possible, eligibility must be checked on OSIP"
    return "LOW/MEDIUM - OSIP campaign; standalone idea route possible, verify campaign-specific eligibility and funding path"


def eligibility_for(opp: Opportunity) -> str:
    text = f"{opp.title} {opp.text}".lower()
    if "gstp" in text or "element 2" in text:
        return "Economic operators in GSTP Element 2 participating states; Italy is listed. National Delegation support required."
    if "participating states" in text:
        return "ESA participating-state rules apply; verify the campaign page."
    return "Open OSIP submission route; implementation funding requires ESA eligibility or campaign-specific rules."


def row_for(opp: Opportunity, cfg: dict[str, Any], now: datetime) -> dict[str, str] | None:
    text_l = f"{opp.title} {opp.text}".lower()
    if "business applications & space solutions" in text_l or "artes competitiveness" in text_l:
        return None
    deadline = deadline_for(opp.text, now)
    if deadline and deadline.date() < now.date():
        return None
    score, matched = score_text(f"{opp.title} {opp.text}", cfg)
    strategic = any(term in text_l for term in ("osip", "gstp", "discovery", "open call"))
    if score < cfg.get("minimum_score", 2) and not strategic:
        return None
    urgency, days = urgency_for(deadline, now)
    programme = programme_for(opp)
    source = "ESA GSTP" if "gstp" in programme.lower() else "ESA OSIP"
    return {
        "Source": source,
        "Provider": "European Space Agency",
        "Programme": programme,
        "Call ID": opp.item_id,
        "Topic ID": opp.table_id,
        "Title": opp.title,
        "Status": status_for(opp.text),
        "Type": opp.kind,
        "Opened": "",
        "Deadline": "" if not deadline else deadline.isoformat(),
        "Clarification": "",
        "Geography / Eligibility": eligibility_for(opp),
        "Consortium Burden": consortium_note(opp),
        "Urgency": urgency,
        "Days": days,
        "Score": str(score),
        "Matched Terms": ", ".join(matched),
        "Theme": clean(opp.text)[:900],
        "URL": opp.url,
    }


def write_outputs(rows: list[dict[str, str]], out_dir: Path, now: datetime) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "geok-esa-open-calls-monitor.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "matched-opportunities.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Geo-K ESA Open Calls Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Urgency | Days | Source | Programme | Title | Deadline | Match |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['Urgency']} | {row['Days']} | {row['Source']} | {row['Programme']} | "
            f"[{row['Title']}]({row['URL']}) | {row['Deadline']} | {row['Matched Terms']} |"
        )
    (out_dir / "geok-esa-open-calls-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now()
    source_html = fetch_html(OSIP_START_URL)
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "osip-start.html").write_text(source_html, encoding="utf-8")

    opportunities = parse_osip_cards(source_html)
    opportunities.append(page_opportunity(GSTP_ELEMENT_2_URL, "OSIP Channel"))

    rows_by_url: dict[str, dict[str, str]] = {}
    for opp in opportunities:
        row = row_for(opp, cfg, now)
        if row:
            rows_by_url[row["URL"]] = row

    rows = sorted(
        rows_by_url.values(),
        key=lambda row: (int(row["Days"]) if row["Days"].lstrip("-").isdigit() else 9999, row["Title"].lower()),
    )
    write_outputs(rows, OUT_DIR, now)
    print(f"Matched {len(rows)} ESA open-call records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
