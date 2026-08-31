#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "monitoring" / "esa-star" / "geok-keywords.json"
OUT_DIR = ROOT / "funding-scout" / "monitoring" / "esa-star" / "latest"
RUNS_DIR = ROOT / "funding-scout" / "monitoring" / "esa-star" / "runs"
BASE = "https://esastar-publication-ext.sso.esa.int"

STATUS = {
    1: "Intended",
    2: "Issued",
    3: "Tender Opening in Progress",
    5: "Evaluation",
    6: "Negotiation",
    7: "Awarded",
    8: "TOB Completed",
    9: "Completed",
    10: "Finalised - Stage 1 completed",
}

TENDER_TYPE = {
    5: "Open Competition",
    7: "Call for Proposals",
}


@dataclass
class Match:
    tender: dict[str, Any]
    score: int
    matched_terms: list[str]
    scope: str
    urgency: str
    days_to_deadline: int | None


def fetch_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{BASE}{path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "Geo-K funding scout"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError):
        result = subprocess.run(
            ["curl", "-Ls", "-H", "Accept: application/json", url],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45,
        )
        return json.loads(result.stdout)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def contains_term(text: str, term: str) -> bool:
    term_l = term.lower()
    text_l = text.lower()
    stripped = term_l.strip()
    if not stripped:
        return False
    pattern = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text_l) is not None


EUROPEAN_SCOPE_TERMS = [
    "european space agency",
    "esa member states",
    "esa member state",
    "all esa",
    "all member states",
    "associate members",
    "european cooperating states",
    "european industry",
    "european space sector",
    "european",
    "worldwide",
    "international",
]

ITALY_SCOPE_TERMS = [
    "italy",
    "italian",
    "esrin",
    "frascati",
]

COUNTRY_LIMIT_TERMS = [
    "bulgaria",
    "bulgarian",
    "spain",
    "spanish",
    "portugal",
    "portuguese",
    "greece",
    "greek",
    "romania",
    "romanian",
    "poland",
    "polish",
    "hungary",
    "hungarian",
    "czech",
    "slovakia",
    "slovak",
    "slovenia",
    "slovenian",
    "croatia",
    "croatian",
    "latvia",
    "lithuania",
    "estonia",
    "austria",
    "austrian",
    "belgium",
    "belgian",
    "denmark",
    "danish",
    "finland",
    "finnish",
    "france",
    "french",
    "germany",
    "german",
    "ireland",
    "irish",
    "luxembourg",
    "netherlands",
    "dutch",
    "norway",
    "norwegian",
    "sweden",
    "swedish",
    "switzerland",
    "swiss",
    "united kingdom",
    "uk",
]


def text_blob(tender: dict[str, Any]) -> str:
    return f"{tender.get('title') or ''} {tender.get('description') or ''}".lower()


def eligibility_scope(tender: dict[str, Any]) -> tuple[bool, str]:
    text = text_blob(tender)
    countries = tender.get("countries") or []
    country_count = len(countries)
    has_italy = any(contains_term(text, term) for term in ITALY_SCOPE_TERMS)
    if has_italy:
        return True, "Italy-relevant"

    country_limited_patterns = [
        r"addressed\s+only\s+to\s+[^.]{0,120}legal\s+entities",
        r"only\s+open\s+to\s+[^.]{0,120}legal\s+entities",
        r"restricted\s+to\s+[^.]{0,120}legal\s+entities",
        r"limited\s+to\s+[^.]{0,120}legal\s+entities",
        r"\bspace\s+weather\s+centre\s+for\s+[a-z ]+",
        r"\bunder\s+the\s+plan\s+for\s+european\s+cooperating\s+states\s+\(pecs\)\s+in\s+[a-z ]+",
    ]
    if any(re.search(pattern, text) for pattern in country_limited_patterns):
        return False, "Excluded: national/legal-entity restricted"

    for country in COUNTRY_LIMIT_TERMS:
        country_pattern = re.escape(country).replace(r"\ ", r"\s+")
        if re.search(rf"\b(for|in|of)\s+(the\s+)?{country_pattern}\b", text):
            return False, f"Excluded: country-specific ({country})"

    if country_count >= 10:
        return True, "Wide ESA/European scope"

    if any(contains_term(text, term) for term in EUROPEAN_SCOPE_TERMS):
        return True, "European/open scope"

    if country_count == 0:
        return True, "Open scope not country-coded"

    return False, f"Excluded: limited country list ({country_count})"


def urgency_for(tender: dict[str, Any], now: datetime) -> tuple[str, int | None]:
    status_id = tender.get("status", {}).get("id")
    if tender.get("isArchived") or tender.get("isCancelled") or status_id not in (1, 2, 3):
        return "GRAY - closed/not active", None
    closing = parse_dt(tender.get("closingDate"))
    if not closing:
        return "BLUE - monitor/no deadline", None
    days = (closing.date() - now.date()).days
    if days < 0:
        return "GRAY - deadline passed", days
    if days <= 7:
        return "RED - due <=7 days", days
    if days <= 14:
        return "ORANGE - due <=14 days", days
    if days <= 30:
        return "AMBER - due <=30 days", days
    return "GREEN - due >30 days", days


def is_active_tender(tender: dict[str, Any], now: datetime) -> bool:
    status_id = tender.get("status", {}).get("id")
    if tender.get("isArchived") or tender.get("isCancelled") or status_id not in (1, 2, 3):
        return False
    closing = parse_dt(tender.get("closingDate"))
    return not closing or closing.date() >= now.date()


def score_tender(tender: dict[str, Any], cfg: dict[str, Any]) -> tuple[int, list[str]]:
    text = f"{tender.get('title') or ''} {tender.get('description') or ''}"
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


def get_all_tenders(max_items: int) -> list[dict[str, Any]]:
    tenders: list[dict[str, Any]] = []
    page_size = 50
    start = 0
    while len(tenders) < max_items:
        take = min(page_size, max_items - len(tenders))
        path = f"/api/tenderAction/filter/{take}" if start == 0 else f"/api/tenderAction/filter/{take}/{start}"
        data = fetch_json(
            path,
            {
                "all": "true",
                "sortBy": "FirstPublicationDate",
                "sortDir": "1",
            },
        )
        items = data.get("items", [])
        if not items:
            break
        tenders.extend(items)
        start += len(items)
        if start >= data.get("total", 0):
            break
    return tenders


def read_previous_matches() -> dict[str, dict[str, Any]]:
    path = OUT_DIR / "matched-tenders.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    previous = {}
    for item in data:
        tender = item["tender"]
        previous[str(tender["id"])] = item
    return previous


def detect_changes(matches: list[Match], previous: dict[str, dict[str, Any]]) -> list[str]:
    changes: list[str] = []
    for m in matches:
        tender = m.tender
        key = str(tender["id"])
        old = previous.get(key)
        title = clean(tender.get("title"))
        status = STATUS.get(tender.get("status", {}).get("id"), str(tender.get("status", {}).get("id")))
        if not old:
            changes.append(f"NEW: {tender.get('tanumber')} / {tender.get('id')} - {title} [{m.urgency}, status {status}]")
            continue
        old_tender = old["tender"]
        old_status = STATUS.get(old_tender.get("status", {}).get("id"), str(old_tender.get("status", {}).get("id")))
        changed_fields = []
        for field, label in [
            ("openDate", "open date"),
            ("closingDate", "deadline"),
            ("clarificationRequestDeadline", "clarification deadline"),
            ("extensionRequestDeadline", "extension deadline"),
        ]:
            if old_tender.get(field) != tender.get(field):
                changed_fields.append(f"{label}: {old_tender.get(field) or 'none'} -> {tender.get(field) or 'none'}")
        if old_status != status:
            changed_fields.append(f"status: {old_status} -> {status}")
        if old.get("urgency") != m.urgency:
            changed_fields.append(f"urgency: {old.get('urgency')} -> {m.urgency}")
        if changed_fields:
            changes.append(f"CHANGED: {tender.get('tanumber')} / {tender.get('id')} - {title} ({'; '.join(changed_fields)})")
    return changes


def write_report(matches: list[Match], now: datetime, changes: list[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in matches:
        t = m.tender
        rows.append(
            {
                "Urgency": m.urgency,
                "Days": "" if m.days_to_deadline is None else str(m.days_to_deadline),
                "TA": t.get("tanumber", ""),
                "ID": t.get("id", ""),
                "Title": clean(t.get("title")),
                "Status": STATUS.get(t.get("status", {}).get("id"), str(t.get("status", {}).get("id"))),
                "Type": TENDER_TYPE.get(t.get("tenderType", {}).get("id"), str(t.get("tenderType", {}).get("id"))),
                "Opened": t.get("openDate") or "",
                "Deadline": t.get("closingDate") or "",
                "Clarification": t.get("clarificationRequestDeadline") or "",
                "Score": str(m.score),
                "Scope": m.scope,
                "Matched Terms": ", ".join(m.matched_terms[:12]),
                "Theme": clean(t.get("description"))[:700],
                "ESA-star": f"{BASE}/ESATenderActions/details/{t.get('id')}",
            }
        )

    with (out_dir / "geok-opportunity-monitor.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["Urgency"])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Geo-K ESA-star Opportunity Monitor",
        "",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Active-only report. Closed, passed-deadline, evaluation, awarded, completed, archived and cancelled records are excluded. Country-limited calls are excluded unless they are Italy-relevant or broad European/open scope.",
        "",
        "Urgency: RED <=7 days; ORANGE <=14 days; AMBER <=30 days; GREEN >30 days; BLUE no deadline/intended.",
        "",
        "## New Or Changed Since Previous Run",
        "",
    ]
    if changes:
        lines.extend(f"- {change}" for change in changes[:30])
        if len(changes) > 30:
            lines.append(f"- ...and {len(changes) - 30} more changes.")
    else:
        lines.append("- No matched tender changed materially since the previous run.")
    lines.extend([
        "",
        "## Matched Opportunities",
        "",
        "| Urgency | Days | TA | ID | Title | Status | Scope | Opened | Deadline | Match |",
        "| --- | ---: | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ])
    for row in rows:
        lines.append(
            f"| {row['Urgency']} | {row['Days']} | {row['TA']} | {row['ID']} | "
            f"{row['Title']} | {row['Status']} | {row['Scope']} | {row['Opened']} | {row['Deadline']} | {row['Matched Terms']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report reads ESA-star public API data, not just the visible JavaScript page.",
            "- Treat document downloads and restricted tender packages as requiring ESA-star login/permissions.",
            "- Review any RED/ORANGE/AMBER item immediately for fit, partner/user need, and proposal workload.",
            "- Closed and inactive records are not shown in this report.",
        ]
    )
    (out_dir / "geok-opportunity-monitor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    max_items = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    now = datetime.now()
    run_dir = RUNS_DIR / now.strftime("%Y%m%d-%H%M%S")
    previous = read_previous_matches()
    tenders = get_all_tenders(max_items)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "all-tenders.json").write_text(json.dumps(tenders, indent=2), encoding="utf-8")

    matches: list[Match] = []
    for tender in tenders:
        if not is_active_tender(tender, now):
            continue
        score, terms = score_tender(tender, cfg)
        if score <= 0:
            continue
        include_scope, scope = eligibility_scope(tender)
        if not include_scope:
            continue
        urgency, days = urgency_for(tender, now)
        matches.append(Match(tender, score, terms, scope, urgency, days))

    urgency_rank = {
        "RED": 0,
        "ORANGE": 1,
        "AMBER": 2,
        "GREEN": 3,
        "BLUE": 4,
        "GRAY": 5,
    }
    matches.sort(
        key=lambda m: (
            urgency_rank.get(m.urgency.split()[0], 9),
            -(m.score),
            9999 if m.days_to_deadline is None else m.days_to_deadline,
            clean(m.tender.get("title")),
        )
    )
    changes = detect_changes(matches, previous)
    (run_dir / "matched-tenders.json").write_text(
        json.dumps(
            [
                {
                    "score": m.score,
                    "matched_terms": m.matched_terms,
                    "scope": m.scope,
                    "urgency": m.urgency,
                    "tender": m.tender,
                }
                for m in matches
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    write_report(matches, now, changes, run_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["all-tenders.json", "matched-tenders.json", "geok-opportunity-monitor.md", "geok-opportunity-monitor.csv"]:
        shutil.copy2(run_dir / name, OUT_DIR / name)
    print(f"Fetched {len(tenders)} tenders; matched {len(matches)} Geo-K-relevant records.")
    print(f"Archived run: {run_dir}")
    print(OUT_DIR / "geok-opportunity-monitor.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
