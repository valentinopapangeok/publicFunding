#!/usr/bin/env python3
"""Monitor Italian national ASI, CNR and Aeronautica public opportunity pages."""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "italian-national" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "italian-national" / "runs"

SOURCE_SEARCHES = {
    "ASI": {
        "provider": "Agenzia Spaziale Italiana",
        "programme": "ASI national calls and procurements",
        "terms": [
            "IRIDE",
            "Space Economy",
            "Space and Blue",
            "osservazione terra",
            "servizi geospaziali",
            "telerilevamento",
        ],
        "base_urls": [
            "https://www.asi.it/bandi/",
            "https://www.asi.it/concorsi_e_opportunita/concorsi/",
            "https://selezioni.asi.it/home?lang=it",
        ],
        "seed_urls": [
            "https://www.asi.it/bandi_e_concorsi/procedura-negoziata-per-laffidamento-dei-servizi-di-ricerca-e-sviluppo-relativi-a-iniziative-a-supporto-della-space-economy-e-nello-specifico-delliniziativa-space-and-blue/",
        ],
        "search_urls": ["https://www.asi.it/?s={term}"],
        "keep_link": r"asi\.it/(bandi_e_concorsi|20\d{2}/)",
    },
    "CNR": {
        "provider": "Consiglio Nazionale delle Ricerche",
        "programme": "CNR calls, procurements and research selections",
        "terms": [
            "osservazione terra",
            "telerilevamento",
            "dati satellitari",
            "SAR",
            "agricoltura di precisione",
            "SpaceItUp",
        ],
        "base_urls": [
            "https://selezionionline.cnr.it/jconon/",
        ],
        "seed_urls": [],
        "search_urls": [
            "https://selezionionline.cnr.it/jconon/search-call?filters-keyword={term}",
            "https://www.urp.cnr.it/search/node/{term}",
        ],
        "keep_link": r"(selezionionline\.cnr\.it/jconon/call-detail|urp\.cnr\.it/node/)",
    },
    "Aeronautica Militare": {
        "provider": "Aeronautica Militare",
        "programme": "Aeronautica Militare procurement",
        "terms": [
            "UAV",
            "droni",
            "Lidar",
            "aerofotogrammetria",
            "SATCOM",
            "Space Situational Awareness",
        ],
        "base_urls": [
            "https://www.aeronautica.difesa.it/amministrazione-trasparente/bandi-di-gara-e-contratti/",
        ],
        "seed_urls": [
            "https://www.aeronautica.difesa.it/tender/id-2024676-3-stormo-fornitura-di-strumentazione-gps-lidar-uav-e-ugv/",
            "https://www.aeronautica.difesa.it/tender/avviso-pubblico-di-manifestazione-di-interesse-a-partecipare-alle-procedure-di-affidamento-ex-art-50-comma-1-decreto-legislativo-31-marzo-2023-n-36-per-il-biennio-2026-2027/",
            "https://www.aeronautica.difesa.it/tender/pisq-perdasdefogu-servizio-di-direzione-lavori-per-lintervento-di-sistema-ssa-space-situational-awareness-realizzazione-di-opere-di-ingegneria-civile-per-impianto-radar/",
            "https://www.aeronautica.difesa.it/en/tender/acquisizione-di-un-collegamento-satcom-commerciale-in-banda-ku-per-le-esigenze-operative-dellassetto-mq-9a-in-dotazione-al-61-gruppo-volo/",
        ],
        "search_urls": ["https://www.aeronautica.difesa.it/?s={term}"],
        "keep_link": r"aeronautica\.difesa\.it/tender/",
    },
}

EXTRA_TERMS = {
    "osservazione della terra": 4,
    "osservazione terra": 4,
    "telerilevamento": 4,
    "dati satellitari": 4,
    "geospaziale": 3,
    "servizi geospaziali": 4,
    "space economy": 3,
    "iride": 4,
    "space and blue": 4,
    "lidar": 4,
    "aerofotogrammetria": 5,
    "uav": 4,
    "ugv": 2,
    "droni": 4,
    "apr": 2,
    "satcom": 4,
    "mq-9": 3,
    "mq-9a": 3,
    "space situational awareness": 3,
    "ssa": 2,
    "spaceitup": 3,
    "imaging": 2,
    "acquisizione": 1,
    "manifestazione di interesse": 2,
    "procedura negoziata": 2,
    "fornitura": 1,
}

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


@dataclass(frozen=True)
class LinkCandidate:
    source: str
    provider: str
    programme: str
    title: str
    url: str
    context: str


class LinkContextParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_d = {key: value or "" for key, value in attrs}
        href = attrs_d.get("href", "")
        if href:
            self._href = urljoin(self.base_url, href)
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            text = clean(" ".join(self._text))
            if text:
                self.links.append((self._href, text))
            self._href = None
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)


def clean(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value.replace("\xa0", " "))
    return re.sub(r"\s+", " ", value).strip()


def fetch_html(url: str) -> str:
    result = subprocess.run(
        [
            "curl",
            "-Lsk",
            "--connect-timeout",
            "8",
            "--max-time",
            "15",
            "-A",
            "Geo-K funding scout",
            url,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )
    return result.stdout


def contains_term(text: str, term: str) -> bool:
    stripped = term.lower().strip()
    if not stripped:
        return False
    pattern = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def context_for_link(page_html: str, href: str, title: str) -> str:
    marker = html.escape(href, quote=True)
    idx = page_html.find(marker)
    if idx < 0:
        idx = page_html.find(href)
    if idx < 0:
        idx = page_html.lower().find(title.lower())
    if idx < 0:
        return title
    start = max(0, idx - 900)
    end = min(len(page_html), idx + 1400)
    return clean(page_html[start:end])


def page_title(page_html: str, fallback: str) -> str:
    for pattern in (
        r"<h1[^>]*>(.*?)</h1>",
        r"<h2[^>]*>\s*OGGETTO\s*</h2>\s*<h2[^>]*>(.*?)</h2>",
        r"<title[^>]*>(.*?)</title>",
    ):
        match = re.search(pattern, page_html, flags=re.I | re.S)
        if match:
            title = clean(match.group(1))
            if title:
                return title
    return fallback


def score_text(text: str, cfg: dict[str, Any]) -> tuple[int, list[str]]:
    for term in cfg["exclude_keywords"]:
        if contains_term(text, term):
            return 0, []
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


def parse_date(value: str) -> datetime | None:
    value_l = value.lower()
    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[ t](\d{1,2}):(\d{2}))?", value_l)
    if iso_match:
        year, month, day, hour, minute = iso_match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 18), int(minute or 0))

    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})(?:\s+(\d{1,2}):(\d{2}))?", value_l)
    if slash_match:
        day, month, year, hour, minute = slash_match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 18), int(minute or 0))

    for match in re.finditer(
        r"\b(\d{1,2})\s+("
        + "|".join(MONTHS)
        + r")\s+(20\d{2})(?:\s+(?:alle|ore)\s+(\d{1,2})[:.](\d{2}))?",
        value_l,
    ):
        day, month_name, year, hour, minute = match.groups()
        hour_i = int(hour or 18)
        minute_i = int(minute or 0)
        if hour_i > 23 or minute_i > 59:
            continue
        return datetime(int(year), MONTHS[month_name], int(day), hour_i, minute_i)
    return None


def deadline_for(context: str) -> datetime | None:
    deadline_patterns = [
        r"(?:scadenza|data di scadenza|deadline|expiration)[^.;|]{0,180}",
        r"entro\s+il[^.;|]{0,120}",
    ]
    for pattern in deadline_patterns:
        for match in re.finditer(pattern, context, flags=re.I):
            parsed = parse_date(match.group(0))
            if parsed:
                return parsed
    return None


def urgency_for(deadline: datetime | None, now: datetime) -> tuple[str, str]:
    if not deadline:
        return "BLUE - check source/no deadline", ""
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


def type_for(source: str, text: str) -> str:
    text_l = text.lower()
    if "manifestazione di interesse" in text_l:
        return "Expression of interest"
    if "procedura negoziata" in text_l or "gara" in text_l or "fornitura" in text_l:
        return "Procurement"
    if "borsa" in text_l or "contratto di ricerca" in text_l or "selezione" in text_l:
        return "Research/recruitment call"
    if source == "Aeronautica Militare":
        return "Procurement"
    return "Call / notice"


def consortium_note(source: str, kind: str) -> str:
    if source == "Aeronautica Militare":
        return "LOW/MEDIUM - supplier procurement; verify tender documents and registration route"
    if source == "CNR" and kind == "Research/recruitment call":
        return "LOW as funding route - mainly partner/project intelligence unless procurement is present"
    if source == "ASI":
        return "MEDIUM - national space route; verify SME/industry eligibility and ASI portal requirements"
    return "MEDIUM - verify eligibility and role"


def canonical_url(value: str) -> str:
    return value.split("#", 1)[0].replace(
        "://www.aeronautica.difesa.it/en/tender/",
        "://www.aeronautica.difesa.it/tender/",
    )


def source_relevant(source: str, candidate: LinkCandidate, terms: list[str], score: int) -> bool:
    title_l = candidate.title.lower()
    if source == "ASI":
        opportunity_words = (
            "bando",
            "bandi",
            "call",
            "opportunit",
            "incentiv",
            "finanziament",
            "procedura",
            "gara",
            "manifestazione di interesse",
        )
        return "bandi_e_concorsi" in candidate.url or any(word in title_l for word in opportunity_words)
    if source == "Aeronautica Militare":
        strong_terms = {
            "uav",
            "lidar",
            "aerofotogrammetria",
            "satcom",
            "mq-9",
            "mq-9a",
            "space situational awareness",
            "ssa",
        }
        if any(term in strong_terms for term in terms):
            return True
        return "manifestazione di interesse" in title_l
    if source == "CNR":
        return score >= 4
    return True


def scan_source(source: str, meta: dict[str, Any], cfg: dict[str, Any], run_dir: Path) -> list[dict[str, str]]:
    urls: list[str] = []
    seed_urls = set(meta.get("seed_urls", []))
    for url in meta["base_urls"]:
        urls.append(url)
    for url in seed_urls:
        urls.append(url)
    for term in meta["terms"]:
        encoded = quote_plus(term)
        for template in meta["search_urls"]:
            urls.append(template.format(term=encoded))

    pages: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_urls = {executor.submit(fetch_html, url): url for url in urls}
        for future in as_completed(future_urls):
            url = future_urls[future]
            try:
                pages.append((url, future.result()))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue

    source_dir = run_dir / slug(source)
    source_dir.mkdir(parents=True, exist_ok=True)
    candidates: dict[str, LinkCandidate] = {}
    keep_re = re.compile(meta["keep_link"], flags=re.I)

    for index, (url, body) in enumerate(pages):
        (source_dir / f"source-{index + 1:02d}.html").write_text(body, encoding="utf-8")
        key = canonical_url(url)
        if url in seed_urls:
            candidates[key] = LinkCandidate(
                source=source,
                provider=meta["provider"],
                programme=meta["programme"],
                title=page_title(body, url.rsplit("/", 2)[-2]),
                url=key,
                context=clean(body)[:5000],
            )
        parser = LinkContextParser(url)
        parser.feed(body)
        for href, title in parser.links:
            if not keep_re.search(href):
                continue
            context = context_for_link(body, href, title)
            key = canonical_url(href)
            existing = candidates.get(key)
            if existing and len(existing.context) >= len(context):
                continue
            candidates[key] = LinkCandidate(
                source=source,
                provider=meta["provider"],
                programme=meta["programme"],
                title=title,
                url=key,
                context=context,
            )

    now = datetime.now()
    rows: list[dict[str, str]] = []
    for candidate in candidates.values():
        score, terms = score_text(candidate.title, cfg)
        if score < 2:
            continue
        if not source_relevant(source, candidate, terms, score):
            continue
        combined = f"{candidate.title} {candidate.context}"
        deadline = deadline_for(candidate.context)
        urgency, days = urgency_for(deadline, now)
        if urgency.startswith("GRAY"):
            continue
        kind = type_for(source, combined)
        rows.append(
            {
                "Source": source,
                "Provider": candidate.provider,
                "Programme": candidate.programme,
                "Call ID": "",
                "Topic ID": candidate.url.rsplit("/", 2)[-2] if candidate.url.endswith("/") else candidate.url.rsplit("/", 1)[-1],
                "Title": candidate.title,
                "Status": "Open/check source" if deadline else "Check source",
                "Type": kind,
                "Opened": "",
                "Deadline": "" if not deadline else deadline.isoformat(),
                "Clarification": "",
                "Geography / Eligibility": "Italy / Italian public source; verify tender-specific eligibility",
                "Consortium Burden": consortium_note(source, kind),
                "Urgency": urgency,
                "Days": days,
                "Score": str(score),
                "Matched Terms": ", ".join(terms[:12]),
                "Theme": candidate.context[:700],
                "URL": candidate.url,
            }
        )
    return rows


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def write_outputs(rows: list[dict[str, str]], out_dir: Path, now: datetime) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
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
    with (out_dir / "geok-italian-national-monitor.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "matched-opportunities.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    lines = [
        "# Geo-K Italian National Sources Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Scope: ASI, CNR and Aeronautica Militare public pages matching Geo-K EO/geospatial/UAV terms. Rows without machine-readable deadlines are retained as check-source items.",
        "",
    ]
    if rows:
        lines.append("| Urgency | Source | Title | Type | Deadline | Match | Link |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in rows:
            lines.append(
                f"| {row['Urgency']} | {row['Source']} | {row['Title']} | {row['Type']} | "
                f"{row['Deadline']} | {row['Matched Terms']} | [source]({row['URL']}) |"
            )
    else:
        lines.append("No active or check-source ASI/CNR/Aeronautica items matched the Geo-K profile.")
    (out_dir / "geok-italian-national-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now()
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for source, meta in SOURCE_SEARCHES.items():
        rows.extend(scan_source(source, meta, cfg, run_dir))
    rows.sort(key=lambda row: (row["Source"], int(row["Days"] or 9999), row["Title"].lower()))

    write_outputs(rows, run_dir, now)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["geok-italian-national-monitor.csv", "geok-italian-national-monitor.md", "matched-opportunities.json"]:
        shutil.copy2(run_dir / name, OUT_DIR / name)
    print(f"Matched {len(rows)} ASI/CNR/Aeronautica records.")
    print(f"Archived run: {run_dir}")
    print(OUT_DIR / "geok-italian-national-monitor.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
