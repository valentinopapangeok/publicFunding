#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "esa-star-monitor"

SOURCE_CSVS = [
    ("ESA-star", ROOT / "funding-scout" / "monitoring" / "esa-star" / "latest" / "geok-opportunity-monitor.csv"),
    ("EU Funding & Tenders", ROOT / "funding-scout" / "monitoring" / "eu-funding-tenders" / "latest" / "geok-eu-ft-monitor.csv"),
    ("ECMWF Copernicus", ROOT / "funding-scout" / "monitoring" / "ecmwf-copernicus" / "latest" / "geok-ecmwf-monitor.csv"),
    ("LIFE CINEA", ROOT / "funding-scout" / "monitoring" / "life-cinea" / "latest" / "geok-life-monitor.csv"),
    ("FAO / UNGM", ROOT / "funding-scout" / "monitoring" / "fao-ungm" / "latest" / "geok-fao-ungm-monitor.csv"),
]

COLORS = {
    "RED": "#f8d7da",
    "ORANGE": "#fce4d6",
    "AMBER": "#fff3cd",
    "GREEN": "#d1e7dd",
    "BLUE": "#dbeafe",
    "GREY": "#e5e7eb",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_esa(row: dict[str, str]) -> dict[str, str]:
    return {
        "Source": "ESA-star",
        "Provider": "ESA",
        "Programme": "",
        "Call ID": row.get("TA", ""),
        "Topic ID": row.get("ID", ""),
        "Title": row.get("Title", ""),
        "Status": row.get("Status", ""),
        "Type": row.get("Type", ""),
        "Opened": row.get("Opened", ""),
        "Deadline": row.get("Deadline", ""),
        "Clarification": row.get("Clarification", ""),
        "Geography / Eligibility": row.get("Scope", ""),
        "Consortium Burden": "LOW/MEDIUM - ESA tender; verify ITT conditions",
        "Urgency": row.get("Urgency", ""),
        "Days": row.get("Days", ""),
        "Score": row.get("Score", ""),
        "Matched Terms": row.get("Matched Terms", ""),
        "Theme": row.get("Theme", ""),
        "URL": row.get("ESA-star", ""),
    }


def normalize_row(source: str, row: dict[str, str]) -> dict[str, str]:
    if source == "ESA-star":
        return normalize_esa(row)
    return {
        "Source": row.get("Source", source),
        "Provider": row.get("Provider", source),
        "Programme": row.get("Programme", ""),
        "Call ID": row.get("Call ID", ""),
        "Topic ID": row.get("Topic ID", ""),
        "Title": row.get("Title", ""),
        "Status": row.get("Status", ""),
        "Type": row.get("Type", ""),
        "Opened": row.get("Opened", ""),
        "Deadline": row.get("Deadline", ""),
        "Clarification": row.get("Clarification", ""),
        "Geography / Eligibility": row.get("Geography / Eligibility", ""),
        "Consortium Burden": row.get("Consortium Burden", ""),
        "Urgency": row.get("Urgency", ""),
        "Days": row.get("Days", ""),
        "Score": row.get("Score", ""),
        "Matched Terms": row.get("Matched Terms", ""),
        "Theme": row.get("Theme", ""),
        "URL": row.get("URL", ""),
    }


def sort_key(row: dict[str, str]) -> tuple[int, int, str]:
    urgency_rank = {"RED": 0, "ORANGE": 1, "AMBER": 2, "GREEN": 3, "BLUE": 4, "GREY": 5}
    urgency = row.get("Urgency", "").split(" ", 1)[0]
    try:
        days = int(float(row.get("Days", "") or "9999"))
    except ValueError:
        days = 9999
    return (urgency_rank.get(urgency, 9), days, row.get("Title", "").lower())


def load_rows() -> tuple[list[dict[str, str]], dict[str, int]]:
    rows: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}
    for source, path in SOURCE_CSVS:
        source_rows = [normalize_row(source, row) for row in read_csv(path)]
        rows.extend(source_rows)
        source_counts[source] = len(source_rows)
    rows.sort(key=sort_key)
    return rows, source_counts


def urgency_key(value: str) -> str:
    return (value or "GREY").split(" ", 1)[0]


def table_link(row: dict[str, str]) -> str:
    title = html.escape(row.get("Title", ""))
    url = row.get("URL", "")
    if not url:
        return title
    return f"<a href='{html.escape(url, quote=True)}'>{title}</a>"


def clip(value: str, limit: int = 260) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def render_table(rows: list[dict[str, str]]) -> str:
    cells = []
    for row in rows:
        urgency = urgency_key(row.get("Urgency", ""))
        color = COLORS.get(urgency, COLORS["GREY"])
        call = " / ".join(part for part in [row.get("Call ID", ""), row.get("Topic ID", "")] if part)
        cells.append(
            "<tr>"
            f"<td><span class='badge' style='background:{color}'>{html.escape(row.get('Urgency', ''))}</span></td>"
            f"<td class='num'>{html.escape(row.get('Days', ''))}</td>"
            f"<td>{html.escape(row.get('Source', ''))}</td>"
            f"<td>{html.escape(row.get('Provider', ''))}</td>"
            f"<td>{html.escape(call)}</td>"
            f"<td>{table_link(row)}</td>"
            f"<td>{html.escape(row.get('Status', ''))}</td>"
            f"<td>{html.escape(row.get('Type', ''))}</td>"
            f"<td>{html.escape(clip(row.get('Geography / Eligibility', ''), 180))}</td>"
            f"<td>{html.escape(clip(row.get('Consortium Burden', ''), 180))}</td>"
            f"<td>{html.escape(row.get('Opened', ''))}</td>"
            f"<td>{html.escape(row.get('Deadline', ''))}</td>"
            f"<td>{html.escape(row.get('Clarification', ''))}</td>"
            f"<td>{html.escape(clip(row.get('Theme', ''), 280))}</td>"
            f"<td>{html.escape(clip(row.get('Matched Terms', ''), 180))}</td>"
            "</tr>"
        )
    return "\n".join(cells)


def render_summary(source_counts: dict[str, int], rows: list[dict[str, str]]) -> str:
    by_urgency = Counter(urgency_key(row.get("Urgency", "")) for row in rows)
    source_items = "".join(
        f"<span class='metric'><strong>{html.escape(source)}</strong>{count}</span>"
        for source, count in source_counts.items()
    )
    urgency_items = "".join(
        f"<span class='metric'><strong>{html.escape(label)}</strong>{count}</span>"
        for label, count in by_urgency.items()
    )
    return f"""
      <div class="metrics">
        <span class="metric"><strong>Total</strong>{len(rows)}</span>
        {source_items}
      </div>
      <div class="metrics">
        {urgency_items}
      </div>
    """


def main() -> int:
    rows, source_counts = load_rows()
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    (SITE / "data.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Geo-K Funding Monitor</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #4b5563;
      --line: #d1d5db;
      --head: #e8eef5;
      --blue: #1f4e79;
      --bg: #f8fafc;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header, main {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 28px 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      color: var(--blue);
      font-size: 30px;
      letter-spacing: 0;
    }}
    p {{
      margin: 0 0 14px;
      color: var(--muted);
      max-width: 1100px;
    }}
    .panel {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .legend, .metrics {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .badge, .metric {{
      display: inline-block;
      border: 1px solid rgba(17, 24, 39, .18);
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .metric {{
      background: #fff;
      color: var(--muted);
    }}
    .metric strong {{
      color: var(--blue);
      margin-right: 7px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      background: #fff;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1660px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: var(--head);
      color: var(--blue);
      z-index: 1;
    }}
    .num {{
      text-align: right;
      white-space: nowrap;
    }}
    a {{
      color: #0f5f9c;
      font-weight: 700;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Geo-K Funding Monitor</h1>
    <p>Active-only opportunities filtered for Geo-K's profile: satellite image processing, EO pipelines, onboard/edge AI, drones and image campaigns, wildfire, water and hydrology, agriculture, archaeology and cultural heritage, critical infrastructure, and broad European or Italian relevance. Generated {html.escape(generated)}.</p>
    <div class="legend">
      <span class="badge" style="background:{COLORS['RED']}">RED <=7 days</span>
      <span class="badge" style="background:{COLORS['ORANGE']}">ORANGE <=21 days</span>
      <span class="badge" style="background:{COLORS['AMBER']}">AMBER <=45 days</span>
      <span class="badge" style="background:{COLORS['GREEN']}">GREEN later</span>
      <span class="badge" style="background:{COLORS['BLUE']}">BLUE intended/no deadline</span>
    </div>
  </header>
  <main>
    <section class="panel">
      {render_summary(source_counts, rows)}
    </section>
    <section class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Urgency</th>
            <th>Days</th>
            <th>Source</th>
            <th>Giver</th>
            <th>Call / Topic</th>
            <th>Title</th>
            <th>Status</th>
            <th>Type</th>
            <th>Geography / Eligibility</th>
            <th>Consortium / Partner Note</th>
            <th>Opening Date</th>
            <th>Deadline</th>
            <th>Clarification</th>
            <th>Theme</th>
            <th>Match</th>
          </tr>
        </thead>
        <tbody>
          {render_table(rows)}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print(SITE / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
