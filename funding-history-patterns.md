# Funding History Patterns

Generated: 2026-09-13 11:10

This report uses the accumulated Geo-K monitor history. Opening/deadline statistics are only computed when a source exposes those dates.

## Source Seasonality

| Source | Calls | Current | Date pairs | Median open window | Window range | Opening months | Deadline months | First-seen months | Typical pattern |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| ASI | 1 | 1 | 0 |  |  |  | Oct (1) | Sep (1) | needs more history |
| ECMWF Copernicus | 4 | 4 | 4 | 76d | 61-91d | Jul (3), Jun (1) | Sep (3), Oct (1) | Sep (4) | medium-window |
| ESA Business Applications | 3 | 3 | 0 |  |  | Dec (1), Mar (1) |  | Sep (3) | rolling/no fixed deadline |
| ESA GSTP | 10 | 4 | 0 |  |  |  | Nov (6) | Sep (10) | needs more history |
| ESA OSIP | 36 | 12 | 0 |  |  |  | Sep (12), Nov (3), Jan (3) | Sep (36) | needs more history |
| ESA-star | 28 | 28 | 18 | 66d | 28-126d | Jul (10), Sep (6), May (2) | Oct (10), Sep (8) | Sep (28) | medium-window |
| EU Funding & Tenders | 24 | 24 | 24 | 168d | 134-231d | Apr (9), May (8), Feb (4), Mar (2), Sep (1) | Sep (17), Nov (5), Dec (1), Jan (1) | Sep (24) | long-window |
| LIFE/CINEA | 9 | 9 | 9 | 154d | 154-317d | Apr (9) | Sep (8), Mar (1) | Sep (9) | long-window |
| MIMIT / Invitalia | 2 | 2 | 0 |  |  |  |  | Sep (2) | rolling/no fixed deadline |
| PID / Camere di Commercio | 4 | 4 | 0 |  |  |  |  | Sep (4) | rolling/no fixed deadline |

## Window Buckets

| Source | <=45d | 46-90d | 91-180d | >180d |
| --- | ---: | ---: | ---: | ---: |
| ASI | 0 | 0 | 0 | 0 |
| ECMWF Copernicus | 0 | 3 | 1 | 0 |
| ESA Business Applications | 0 | 0 | 0 | 0 |
| ESA GSTP | 0 | 0 | 0 | 0 |
| ESA OSIP | 0 | 0 | 0 | 0 |
| ESA-star | 5 | 9 | 4 | 0 |
| EU Funding & Tenders | 0 | 0 | 12 | 12 |
| LIFE/CINEA | 0 | 0 | 8 | 1 |
| MIMIT / Invitalia | 0 | 0 | 0 | 0 |
| PID / Camere di Commercio | 0 | 0 | 0 | 0 |

## Reading The Pattern

- `Opening months` are the actual issue/opening dates when the source exposes them.
- `First-seen months` are when Geo-K's monitor first captured the call; this is useful for sources that do not expose a clean opening date.
- `Date pairs` indicates how much evidence supports the open-window statistics for that source.
- The history improves every day the monitor runs. For older years, we still need source-specific backfill, starting with EU Funding & Tenders and ESA Business Applications.
