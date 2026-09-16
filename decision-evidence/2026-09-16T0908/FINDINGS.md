# Spot-entry decision — September 16, 2026, 09:11:08 UTC

**Assessment: stay flat rather than chase this bounce through the modeled canonical route.** Current flow is bullish; the evidence does not establish enough future buying to overcome entry/exit fees with a favorable expected return. This is an assessment under stated assumptions, not a calibrated probability or a claim that price must decline. Leverage, funding and liquidation have not been modeled.

## New observations

- Spot: **0.0001136864 ETH/STANDARD**, up **6.49%** from 06:16:07 UTC.
- Since 06:16: **169.99 ETH buys / 49.31 ETH sells** on the canonical pool.
- Last 20 minutes: **40.78 ETH buys / 0.98 ETH sells**. The three largest token recipient addresses account for **90.8%** of buying volume. Recipients are not necessarily independent beneficial investors.
- The large synchronized seller `0x5638484ba2d2f1d1d35020572b0aa439a9869192` still holds **764,635 STANDARD**. Another large watched seller `0x8224c04a8f66557df682fd0581eb3724bd2bee07` holds **862,798**. These are freshly read balances; neither balance is a commitment to sell.
- Buyback vault: **111.72 ETH**, `lastTickAt=0`. Today's license quota: **100 sold, zero remaining**. Buying to position for future game activity remains possible, but immediate license purchases do not compel fresh demand.
- Freshly checked fees: 2% buy hook tax, 3% sell hook tax, 1% canonical LP fee per side.

## Fee-adjusted payoff

For a small spot trade, before gas, extra router fees and slippage:

`net return = (1 − 0.02) × (1 − 0.01)^2 × (1 − 0.03) × (1 + spot return) − 1`

| Subsequent spot move | Approximate net return |
|---|---:|
| −10% | −16.15% |
| Unchanged | −6.83% |
| +5% | −2.17% |
| +10% | +2.49% |
| +20% | +11.80% |

Price must rise **7.33%** to clear this fee hurdle. Existing holders' hold/sell decisions have a different cost basis: the table describes a new entry and later exit. Alternative venue costs could differ; no alternative executable quote is claimed.

## Current liquidity: buying required to break even

Illustrative **1 ETH entry**, other sellers act, other buyers arrive, investor exits. Current initialized tick liquidity is rebuilt from the saved 05:40 profile and all intervening canonical liquidity events. Active liquidity reconciles with the final Swap event. Locked liquidity is retained in future cases; the pool is not treated as a single constant-product curve.

| Additional tokens sold | Additional buyer ETH needed just to break even |
|---|---:|
| None | **130.84 ETH** |
| 250,000 STANDARD | **159.63 ETH** |
| 750,000 STANDARD | **215.92 ETH** |

Amounts above are modeled outside-wallet input ETH including the ordinary buy tax. Observed flow totals are canonical pool-side ETH, so their exact numeric bases differ. All amounts are future requirements after the illustrative entry, not money already spent on the rebound. They are not forecasts. Execution order, sizes, other venues and liquidity changes can alter the result.

Even assuming **24 successful hourly buybacks**, zero other sellers and unchanged liquidity, the 1 ETH entrant returns approximately **−1.56%** after modeled fees. That spends 101.06 ETH of the current vault; execution has not begun. This isolates the present vault and excludes replenishment or other buyers.

## What would change the assessment

Continued material buying from a broader set of independently funded actors, absorption of actual large-holder sales without losing the recovery, or observed buyback execution with sufficient additional buying/funding would strengthen the case. Waiting for confirmation can mean paying a higher price; a higher price also requires recalculating the entry hurdle. The present facts support a momentum possibility, not a verified positive-expectation long.

## Reproduce and audit

Run `python analyze_decision_check.py` from the repository root. See [summary](summary.json), [conditional scenarios](entry-scenarios.csv), [flow windows](flow-windows.csv), [trades](trades.csv.gz), [raw pinned RPC packet](tape.json), and [rebuilt liquidity](liquidity-replayed.json).

Snapshot block **64,390,990**, hash `0x824c504f8747ac6f6e1e7de4b8c3bf2908c1791446e9238b5337f054b7831239`, Robinhood chain 4663. STANDARD `0x88ad8DdF1E3898412146a534538d418c6F8A9062`. All 18 watched token balances reconcile against transfer replay. This is a focused refresh, not a full holder/branch-state refresh. Window times are interpolated between archived headers. The collector and analysis are read-only; no trading was performed.
