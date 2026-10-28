# Funding History Patterns

Generated: 2026-10-28 12:12

This report uses the accumulated Geo-K monitor history. Opening/deadline statistics are only computed when a source exposes those dates.

## Source Seasonality

| Source | Calls | Current | Date pairs | Median open window | Window range | Opening months | Deadline months | First-seen months | Typical pattern |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| ARPA | 2 | 0 | 0 |  |  |  |  | Sep (1), Oct (1) | rolling/no fixed deadline |
| ASI | 4 | 3 | 0 |  |  |  | Oct (2), Sep (1), Nov (1) | Sep (2), Oct (2) | needs more history |
| ECMWF Copernicus | 6 | 1 | 6 | 65d | 42-91d | Jul (3), Sep (2), Jun (1) | Sep (3), Nov (2), Oct (1) | Sep (6) | medium-window |
| ESA Business Applications | 3 | 2 | 0 |  |  | Dec (1), Mar (1) |  | Sep (3) | rolling/no fixed deadline |
| ESA GSTP | 52 | 0 | 0 |  |  |  | Nov (30), Oct (4) | Sep (31), Oct (21) | needs more history |
| ESA OSIP | 188 | 1 | 0 |  |  |  | Sep (29), Nov (17), Jan (17), Oct (12), Dec (3) | Sep (121), Oct (67) | needs more history |
| ESA-star | 48 | 35 | 35 | 56d | 14-962d | Sep (14), Jul (10), Oct (4), May (3), Dec (2) | Oct (12), Sep (10), Nov (9), Dec (4) | Sep (37), Oct (11) | medium-window |
| EU Funding & Tenders | 34 | 15 | 34 | 153d | 91-231d | Apr (11), May (8), Oct (7), Feb (4), Mar (2) | Sep (19), Jan (6), Nov (5), Feb (2), Oct (1) | Sep (27), Oct (7) | long-window |
| LIFE/CINEA | 9 | 1 | 9 | 154d | 154-317d | Apr (9) | Sep (8), Mar (1) | Sep (9) | long-window |
| Local innovation contests | 1 | 0 | 0 |  |  |  | Sep (1) | Sep (1) | needs more history |
| MIMIT / Invitalia | 2 | 0 | 0 |  |  |  |  | Sep (2) | rolling/no fixed deadline |
| PID / Camere di Commercio | 10 | 5 | 0 |  |  |  |  | Sep (5), Oct (5) | rolling/no fixed deadline |

## Window Buckets

| Source | <=45d | 46-90d | 91-180d | >180d |
| --- | ---: | ---: | ---: | ---: |
| ARPA | 0 | 0 | 0 | 0 |
| ASI | 0 | 0 | 0 | 0 |
| ECMWF Copernicus | 2 | 3 | 1 | 0 |
| ESA Business Applications | 0 | 0 | 0 | 0 |
| ESA GSTP | 0 | 0 | 0 | 0 |
| ESA OSIP | 0 | 0 | 0 | 0 |
| ESA-star | 15 | 11 | 4 | 5 |
| EU Funding & Tenders | 0 | 0 | 22 | 12 |
| LIFE/CINEA | 0 | 0 | 8 | 1 |
| Local innovation contests | 0 | 0 | 0 | 0 |
| MIMIT / Invitalia | 0 | 0 | 0 | 0 |
| PID / Camere di Commercio | 0 | 0 | 0 | 0 |

## Reading The Pattern

- `Opening months` are the actual issue/opening dates when the source exposes them.
- `First-seen months` are when Geo-K's monitor first captured the call; this is useful for sources that do not expose a clean opening date.
- `Date pairs` indicates how much evidence supports the open-window statistics for that source.
- The history improves every day the monitor runs. For older years, we still need source-specific backfill, starting with EU Funding & Tenders and ESA Business Applications.
