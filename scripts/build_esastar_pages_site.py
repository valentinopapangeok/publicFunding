#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "funding-scout" / "monitoring" / "esa-star" / "latest"
SITE = ROOT / "site" / "esa-star-monitor"


COLORS = {
    "RED": "#f8d7da",
    "ORANGE": "#fce4d6",
    "AMBER": "#fff3cd",
    "GREEN": "#d1e7dd",
    "BLUE": "#dbeafe",
}


def load_rows() -> list[dict[str, str]]:
    with (LATEST / "geok-opportunity-monitor.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def urgency_key(value: str) -> str:
    return value.split(" ", 1)[0]


def render_table(rows: list[dict[str, str]]) -> str:
    cells = []
    for row in rows:
        urgency = urgency_key(row["Urgency"])
        color = COLORS.get(urgency, "#f8f9fa")
        cells.append(
            "<tr>"
            f"<td><span class='badge' style='background:{color}'>{html.escape(row['Urgency'])}</span></td>"
            f"<td class='num'>{html.escape(row['Days'])}</td>"
            f"<td>{html.escape(row['TA'])}</td>"
            f"<td>{html.escape(row['ID'])}</td>"
            f"<td><a href='{html.escape(row['ESA-star'])}'>{html.escape(row['Title'])}</a></td>"
            f"<td>{html.escape(row['Status'])}</td>"
            f"<td>{html.escape(row['Type'])}</td>"
            f"<td>{html.escape(row.get('Scope', ''))}</td>"
            f"<td>{html.escape(row['Opened'])}</td>"
            f"<td>{html.escape(row['Deadline'])}</td>"
            f"<td>{html.escape(row['Clarification'])}</td>"
            f"<td>{html.escape(row['Matched Terms'])}</td>"
            "</tr>"
        )
    return "\n".join(cells)


def main() -> int:
    rows = load_rows()
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    (SITE / "data.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Geo-K ESA-star Funding Monitor</title>
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
      max-width: 1440px;
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
    }}
    .panel {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 20px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .badge {{
      display: inline-block;
      border: 1px solid rgba(17, 24, 39, .18);
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      background: #fff;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1180px;
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
    ul {{
      margin: 10px 0 0 20px;
      padding: 0;
    }}
    li {{
      margin-bottom: 6px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Geo-K ESA-star Funding Monitor</h1>
    <p>Active-only ESA-star opportunities filtered for Geo-K themes and broad European or Italian eligibility. Generated {html.escape(generated)}.</p>
    <div class="legend">
      <span class="badge" style="background:{COLORS['RED']}">RED <=7 days</span>
      <span class="badge" style="background:{COLORS['ORANGE']}">ORANGE <=14 days</span>
      <span class="badge" style="background:{COLORS['AMBER']}">AMBER <=30 days</span>
      <span class="badge" style="background:{COLORS['GREEN']}">GREEN >30 days</span>
      <span class="badge" style="background:{COLORS['BLUE']}">BLUE no deadline/intended</span>
    </div>
  </header>
  <main>
    <section class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Urgency</th>
            <th>Days</th>
            <th>TA</th>
            <th>ID</th>
            <th>Title</th>
            <th>Status</th>
            <th>Type</th>
            <th>Scope</th>
            <th>Opened</th>
            <th>Deadline</th>
            <th>Clarification</th>
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
