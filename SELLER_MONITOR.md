# Seller polling: entry cohorts, depletion and replacement

**Latest observed: 2026-09-16T02:48:06+00:00, Robinhood chain 4663, block 64162587.**

## Finding

The existing sellers are reducing some inventory, but **replacement sellers dominate new selling**. This does not support a reliable prediction that selling ends at a particular UTC time.

The fixed group tracked at 02:22:37 UTC initially held **2,343,124 STANDARD**. It now holds **2,131,624**, down **211,500**. Its canonical-pool sales were only **127,649 tokens**, partially offset by **21,445** bought. Another **105,297** of net depletion came from transfers, other venues, burns or unresolved routes; that component must not be represented as canonical selling.

Meanwhile, **58 addresses outside that previously tracked group** sold **2,676,245 tokens**, approximately **95.4%** of attributed sales since the baseline. This group is newly active relative to the fixed group; it is not necessarily new to the token or making a first-ever sale.

In the most recent approximate 20-minute window, **33 first-time canonical sellers** contributed **84.8% of attributed sold tokens**. That is direct evidence of seller replacement rather than only a fixed pile gradually clearing.

## Three completed polls

| UTC observation | Fixed 02:22 seller group's tokens | Rolling six-hour sellers' tokens | Newly active outside fixed group |
| --- | ---: | ---: | ---: |
| 2026-09-16T02:46:05+00:00 | 2,094,944 | 2,239,615 | 56 |
| 2026-09-16T02:47:07+00:00 | 2,131,624 | 2,276,822 | 58 |
| 2026-09-16T02:48:06+00:00 | 2,131,624 | 2,276,822 | 58 |

The rolling group changes with time; its balance must not be used as a pure depletion measure. The fixed group also receives tokens. The increase between the final two checks illustrates why an empty-wallet countdown can reverse.

## When and how remaining sellers entered

These are the **first observed token receipts at the current address**, not proof of when the ultimate beneficial owner entered. Launch was September 15, 2026, 01:00:30 UTC. Individual receipt/trade times are interpolated between exact saved headers; polling timestamps themselves are exact block timestamps.

| First observed receipt relative to launch | Addresses in current six-hour seller group | Tokens remaining | Share |
| --- | ---: | ---: | ---: |
| First hour | 281 | 1,446,878 | 63.5% |
| Hours 1–6 | 124 | 730,713 | 32.1% |
| Hours 6–18 | 61 | 10,292 | 0.5% |
| After hour 18 | 82 | 88,938 | 3.9% |

Approximately **95.6%** of remaining inventory belongs to addresses that first received tokens in the first six launch hours. Early receipt does **not** imply a cheap entry: launch taxes were much higher, and transfers may carry another wallet's purchase history.

Current remaining-inventory lineage, using pro-rata accounting:

| Source | Tokens | Share |
| --- | ---: | ---: |
| Direct canonical-pool purchases | 1,579,386 | 69.4% |
| Transferred market-purchased tokens | 272,633 | 12.0% |
| Direct purchases from verified secondary pools | 92,596 | 4.1% |
| Branch withdrawals, direct or transferred | 0 | 0.0% |
| Other custody / unresolved / other origins | 332,207 | 14.6% |

The CSV also includes first canonical purchase time and lifetime pool-side purchase VWAP. **VWAP is not remaining-inventory cost basis or wallet P&L**: it excludes hook taxes, router/gas charges, some secondary purchases and inherited basis. No profitable/unprofitable label is inferred from it.

### Wallets worth watching

| Address | Tokens left | Entry observation | Last-20-minute behavior |
| --- | ---: | --- | --- |
| `0xa65ce1d604fa901c13aa29f2126a57d9032e412b` | 600,000 | 2026-09-15T06:02:49.675126791+00:00 | Sold 0; bought 0 |
| `0xd026f7a62fad79952d2f136ebd598a71b0053da1` | 337,805 | 2026-09-15T01:08:07.117894650+00:00 | Sold 0; bought 0 |
| `0xaae01d26a2100224f724df95fafacd1d07c13593` | 150,000 | 2026-09-15T01:12:38.745393991+00:00 | Sold 0; bought 0 |
| `0x681d22c5e615c7a876026ceba3dc36c6dde5b97d` | 100,125 | 2026-09-15T01:21:36.612134695+00:00 | Sold 91,000; bought 0 |
| `0xf955dab8bdb1158dc0df449997a057ab9eb4f774` | 99,488 | 2026-09-15T01:02:20.439354897+00:00 | Sold 0; bought 0 |

The 600k wallet's remaining inventory traces to direct canonical purchases. The 150k wallet has no attributed direct canonical purchase and its current inventory traces to transferred market purchases. They therefore should not be assigned the same entry-price or sale-motive model.

## Can we estimate when they finish?

Only conditionally. Dividing a fixed group's remaining inventory by its observed net depletion gives a mechanical countdown. Here it moved from roughly 3.3 hours to 4.3 hours within two minutes of observations, as tokens came back into the group. It also mixes sales with non-sale transfers unless decomposed. Applying the whole market's sell rate to this group's balance is worse: most new selling is coming from different addresses.

There is **no finite estimated stop time** for a large wallet that is currently holding rather than selling. An address that transfers to another wallet may have moved its selling capacity instead of exhausting it. Future beliefs, sell thresholds, other holders activating and new purchases remain unobserved.

A useful confirmation rule would look for **all** of the following over several separate windows, not overlapping one-minute polls of the same 20-minute history:

1. Fixed-cohort remaining inventory declines through verified sales, without substantial replenishment or unexplained transfers.
2. First-time/replacement seller token volume also declines.
3. Incoming buying—including actual executed buybacks—can absorb total selling.
4. The largest residual wallets do not introduce a fresh wave of selling.

This is a monitoring heuristic, not a calibrated signal or promise of a bottom. At the latest poll, attributed 20-minute buying was **85.89 ETH** versus **247.70 ETH** of selling. **No buybacks have executed**, and the vault remains **111.72 ETH**. The current evidence does not meet the positive-flow condition.

## Run the poller

```bash
npm ci
python3 -m pip install -r requirements.txt
# One fresh pinned observation and updated analysis:
node poll_sellers.mjs
# Twelve polls, five minutes apart (roughly one hour):
node poll_sellers.mjs --samples 12 --interval 300
# Recompute the latest analysis from saved data, offline:
python3 seller_monitor.py
```

The poller uses the public Robinhood RPC. No keys, signing or transaction submission. It stores each frozen header, exact query/results, token transfers, canonical swaps, verified secondary-pool swaps, branch activity and buyback events under `seller-monitor/<UTC>/`. Failed calls stop the run; missing data is never treated as zero selling. Previous pin hashes and continuity are checked, and token balances replay exactly to current total supply. All remaining source mixtures reconcile within floating-point tolerance.

**Three observations were completed for this publication; no unattended background service or alerts are running.** Future polling runs only while the command/process is active. The script resumes from the latest completed collection and does not auto-publish new snapshots to GitHub.

Latest saved pointer: [seller-monitor/latest.json](seller-monitor/latest.json). Detailed [seller entries and source mixtures](seller-monitor/2026-09-16T02-48-06.000Z/analysis/sellers.csv), [watchlist](seller-monitor/2026-09-16T02-48-06.000Z/analysis/watchlist.csv), and [flow windows](seller-monitor/2026-09-16T02-48-06.000Z/analysis/flow-windows.csv).

## Limits

The latest incremental canonical ETH attribution is **98.40%**; unresolved activity remains disclosed. Secondary-only sellers without an attributed canonical sale are not in this seller definition, although their transfers affect balances and recognized secondary purchases affect provenance. Addresses are not people. First receipts can be transfers rather than purchases. Branch ownership, seller intent and future funding are not inferred from a wallet's timing alone. The recent global liquidity model and buyback trade-cost calculations remain in [BUYBACK_TRADE.md](BUYBACK_TRADE.md).
