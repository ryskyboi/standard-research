# Time reference: UTC and elapsed time

All displayed calendar timestamps use **UTC**. Elapsed hours and days remain available alongside them. The frozen market snapshot is **2026-09-15 10:09:19 UTC**; these dates do not become a live forecast when the notebook is rerun.

`UTC timestamp = snapshot timestamp + elapsed model time`.

Charts retain elapsed hours/days below and add UTC dates above. Tables and CSVs include corresponding UTC columns. Exact table timestamps preserve the snapshot's 19-second offset; chart labels are shortened to minutes for readability. Native block timestamps and raw evidence remain unchanged.

| Elapsed hours | Elapsed days | UTC timestamp |
| ---: | ---: | --- |
| +0 | 0.0000 | 2026-09-15 10:09:19 UTC |
| +4 | 0.1667 | 2026-09-15 14:09:19 UTC |
| +8 | 0.3333 | 2026-09-15 18:09:19 UTC |
| +16 | 0.6667 | 2026-09-16 02:09:19 UTC |
| +19 | 0.7917 | 2026-09-16 05:09:19 UTC |
| +22 | 0.9167 | 2026-09-16 08:09:19 UTC |
| +23 | 0.9583 | 2026-09-16 09:09:19 UTC |
| +31 | 1.2917 | 2026-09-16 17:09:19 UTC |
| +32 | 1.3333 | 2026-09-16 18:09:19 UTC |
| +35 | 1.4583 | 2026-09-16 21:09:19 UTC |
| +38 | 1.5833 | 2026-09-17 00:09:19 UTC |
| +44 | 1.8333 | 2026-09-17 06:09:19 UTC |
| +48 | 2.0000 | 2026-09-17 10:09:19 UTC |
| +56 | 2.3333 | 2026-09-17 18:09:19 UTC |
| +85 | 3.5417 | 2026-09-18 23:09:19 UTC |
| +92 | 3.8333 | 2026-09-19 06:09:19 UTC |
| +114 | 4.7500 | 2026-09-20 04:09:19 UTC |
| +130 | 5.4167 | 2026-09-20 20:09:19 UTC |
| +168 | 7.0000 | 2026-09-22 10:09:19 UTC |
| +207 | 8.6250 | 2026-09-24 01:09:19 UTC |
| +233 | 9.7083 | 2026-09-25 03:09:19 UTC |
| +237 | 9.8750 | 2026-09-25 07:09:19 UTC |
| +327 | 13.6250 | 2026-09-29 01:09:19 UTC |
| +336 | 14.0000 | 2026-09-29 10:09:19 UTC |

Calendar conversions apply to events measured from the snapshot. A buying half-life, valuation horizon, seven-day rolling fee window, dormancy period or number of future auction days is a **duration**, not necessarily an event occurring that many days after the snapshot. Those quantities retain their original units.
