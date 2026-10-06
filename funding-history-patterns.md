# Funding History Patterns

Generated: 2026-10-06 13:25

This report uses the accumulated Geo-K monitor history. Opening/deadline statistics are only computed when a source exposes those dates.

## Source Seasonality

| Source | Calls | Current | Date pairs | Median open window | Window range | Opening months | Deadline months | First-seen months | Typical pattern |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| ARPA | 2 | 1 | 0 |  |  |  |  | Sep (1), Oct (1) | rolling/no fixed deadline |
| ASI | 2 | 1 | 0 |  |  |  | Sep (1), Oct (1) | Sep (2) | needs more history |
| ECMWF Copernicus | 6 | 1 | 6 | 65d | 42-91d | Jul (3), Sep (2), Jun (1) | Sep (3), Nov (2), Oct (1) | Sep (6) | medium-window |
| ESA Business Applications | 3 | 3 | 0 |  |  | Dec (1), Mar (1) |  | Sep (3) | rolling/no fixed deadline |
| ESA GSTP | 31 | 0 | 0 |  |  |  | Nov (16), Oct (4) | Sep (31) | needs more history |
| ESA OSIP | 121 | 1 | 0 |  |  |  | Sep (29), Jan (10), Nov (9), Oct (2) | Sep (121) | needs more history |
| ESA-star | 46 | 39 | 32 | 58d | 14-962d | Sep (14), Jul (10), May (3), Dec (2), Oct (1) | Oct (12), Sep (10), Nov (8), Dec (2) | Sep (37), Oct (9) | medium-window |
| EU Funding & Tenders | 27 | 8 | 27 | 154d | 98-231d | Apr (11), May (8), Feb (4), Mar (2), Jul (1) | Sep (19), Nov (5), Oct (1), Dec (1), Jan (1) | Sep (27) | long-window |
| LIFE/CINEA | 9 | 1 | 9 | 154d | 154-317d | Apr (9) | Sep (8), Mar (1) | Sep (9) | long-window |
| Local innovation contests | 1 | 0 | 0 |  |  |  | Sep (1) | Sep (1) | needs more history |
| MIMIT / Invitalia | 2 | 2 | 0 |  |  |  |  | Sep (2) | rolling/no fixed deadline |
| PID / Camere di Commercio | 7 | 5 | 0 |  |  |  |  | Sep (5), Oct (2) | rolling/no fixed deadline |

## Window Buckets

| Source | <=45d | 46-90d | 91-180d | >180d |
| --- | ---: | ---: | ---: | ---: |
| ARPA | 0 | 0 | 0 | 0 |
| ASI | 0 | 0 | 0 | 0 |
| ECMWF Copernicus | 2 | 3 | 1 | 0 |
| ESA Business Applications | 0 | 0 | 0 | 0 |
| ESA GSTP | 0 | 0 | 0 | 0 |
| ESA OSIP | 0 | 0 | 0 | 0 |
| ESA-star | 13 | 10 | 4 | 5 |
| EU Funding & Tenders | 0 | 0 | 15 | 12 |
| LIFE/CINEA | 0 | 0 | 8 | 1 |
| Local innovation contests | 0 | 0 | 0 | 0 |
| MIMIT / Invitalia | 0 | 0 | 0 | 0 |
| PID / Camere di Commercio | 0 | 0 | 0 | 0 |

## Reading The Pattern

- `Opening months` are the actual issue/opening dates when the source exposes them.
- `First-seen months` are when Geo-K's monitor first captured the call; this is useful for sources that do not expose a clean opening date.
- `Date pairs` indicates how much evidence supports the open-window statistics for that source.
- The history improves every day the monitor runs. For older years, we still need source-specific backfill, starting with EU Funding & Tenders and ESA Business Applications.
