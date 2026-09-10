# Funding History Patterns

Generated: 2026-09-10 17:35

This report uses the accumulated Geo-K monitor history. Opening/deadline statistics are only computed when a source exposes those dates.

## Source Seasonality

| Source | Calls | Current | Date pairs | Median open window | Window range | Opening months | Deadline months | First-seen months | Typical pattern |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| ARPA | 9 | 0 | 0 |  |  |  |  | Sep (9) | rolling/no fixed deadline |
| ASI | 42 | 1 | 0 |  |  |  | Oct (2) | Sep (42) | needs more history |
| Aeronautica Militare | 16 | 0 | 0 |  |  |  | Dec (2) | Sep (16) | needs more history |
| ECMWF Copernicus | 8 | 4 | 8 | 76d | 61-91d | Jul (6), Jun (2) | Sep (6), Oct (2) | Sep (8) | medium-window |
| ESA Business Applications | 3 | 3 | 0 |  |  | Dec (1), Mar (1) |  | Sep (3) | rolling/no fixed deadline |
| ESA GSTP | 3 | 3 | 0 |  |  |  |  | Sep (3) | rolling/no fixed deadline |
| ESA OSIP | 13 | 13 | 0 |  |  |  | Sep (8), Nov (1), Jan (1) | Sep (13) | needs more history |
| ESA-star | 144 | 35 | 82 | 73d | 28-1322d | Jul (40), Jun (18), Aug (11), Sep (6), May (5) | Sep (49), Oct (23), Aug (4), Dec (3), Jul (2) | Aug (136), Sep (8) | medium-window |
| EU Funding & Tenders | 40 | 21 | 40 | 153d | 14-231d | Apr (18), May (10), Feb (5), Aug (2), Mar (2) | Sep (28), Nov (7), Oct (2), Dec (2), Jan (1) | Sep (40) | long-window |
| Erasmus+ | 2 | 0 | 2 | 176d | 79-273d | Dec (1), Jun (1) | Sep (2) | Sep (2) | long-window |
| ISPRA | 11 | 0 | 0 |  |  |  |  | Sep (11) | rolling/no fixed deadline |
| LIFE/CINEA | 9 | 9 | 9 | 154d | 135-154d | Apr (9) | Sep (9) | Sep (9) | long-window |
| MIMIT / Invitalia | 6 | 2 | 0 |  |  |  |  | Sep (6) | rolling/no fixed deadline |
| PID / Camere di Commercio | 5 | 4 | 0 |  |  |  |  | Sep (5) | rolling/no fixed deadline |

## Window Buckets

| Source | <=45d | 46-90d | 91-180d | >180d |
| --- | ---: | ---: | ---: | ---: |
| ARPA | 0 | 0 | 0 | 0 |
| ASI | 0 | 0 | 0 | 0 |
| Aeronautica Militare | 0 | 0 | 0 | 0 |
| ECMWF Copernicus | 0 | 6 | 2 | 0 |
| ESA Business Applications | 0 | 0 | 0 | 0 |
| ESA GSTP | 0 | 0 | 0 | 0 |
| ESA OSIP | 0 | 0 | 0 | 0 |
| ESA-star | 13 | 49 | 16 | 4 |
| EU Funding & Tenders | 1 | 2 | 22 | 15 |
| Erasmus+ | 0 | 1 | 0 | 1 |
| ISPRA | 0 | 0 | 0 | 0 |
| LIFE/CINEA | 0 | 0 | 9 | 0 |
| MIMIT / Invitalia | 0 | 0 | 0 | 0 |
| PID / Camere di Commercio | 0 | 0 | 0 | 0 |

## Reading The Pattern

- `Opening months` are the actual issue/opening dates when the source exposes them.
- `First-seen months` are when Geo-K's monitor first captured the call; this is useful for sources that do not expose a clean opening date.
- `Date pairs` indicates how much evidence supports the open-window statistics for that source.
- The history improves every day the monitor runs. For older years, we still need source-specific backfill, starting with EU Funding & Tenders and ESA Business Applications.
