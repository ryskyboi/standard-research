# Updated assessment: an earlier top and a recovery can coexist

**Evidence cutoff: September 15, 2026, 22:45:58 UTC.** This updates the research with observed selling and current liquidity. [Open the executed notebook](recovery_update.ipynb).

## Assessment

**I lean toward the earlier highs holding over the next 24–48 hours, while a relief rally remains plausible.** This is an evidence-informed judgment, not a calibrated probability or a claim to have identified the ultimate top. A token can recover 10–20% and still remain substantially below its earlier price.

The observed evidence is adverse net flow, no active buyback tick and exhausted immediate license capacity. Selling has slowed across the sampled windows, which supports an exhaustion/bounce possibility. But buying remains weak, and the latest five minutes show very little activity on either side. Lower selling alone is not proof of renewed demand.

We do not have a complete all-time price series or identified seller inventories. The 10:09 and 13:40 prices below are verified earlier reference levels, not asserted all-time highs. The original agent-model peak dates are not validated by the subsequent decline.

## What changed in the projections

The new notebook starts from block **64,018,215**, using the entire current bitmap scan: **77 initialized liquidity ticks**, approximately **2,424.76 ETH of actual pool principal**, and a price of **0.000114464744 ETH per STANDARD**. The active virtual ETH reserve is about **3,522.82 ETH** and is not treated as withdrawable principal. Both previously identified protocol positions were checked unchanged; locked liquidity remains safe by assumption.

The latest two adjacent twenty-minute windows imply approximately **35.13 ETH/hour of buyer spending before hook tax** and **1.559 million STANDARD/hour sold**. These are gross turnover rates, not independently measured new capital or total remaining seller inventory. The notebook never double-counts the overlapping five-minute window.

| September 15 UTC | Pool buy input ETH | Pool sell output ETH | STANDARD/ETH change |
|---|---:|---:|---:|
| 22:05:58–22:25:58 | 10.38 | 80.12 | −3.82% |
| 22:25:58–22:45:58 | 12.57 | 40.71 | −1.59% |

Fees remain 2% buy tax, 3% sell tax and 1% pool LP fee. There are no branch withdrawals in these windows. The contraction vault holds 111.72 ETH and `lastTickAt` remains zero. [Raw observations and verified timestamps](live-observations/2026-09-15T22-45-57.336Z/summary.json), [support state](live-observations/2026-09-15T22-45-57.336Z/support-state.json).

## A bounce requires less buying than a full recovery

| Target from the new snapshot | Required gain | Buy-only wallet expenditure |
|---|---:|---:|
| 10% bounce | +10% | 178 ETH |
| 25% bounce | +25% | 427 ETH |
| Regain September 15, 13:40 price | +30.4% | 512 ETH |
| Regain September 15, 10:09 price | +61.6% | 971 ETH |

These are **lower bounds with no intervening sales**, including buy tax and LP fee. Ongoing selling can require much more buying. They assume the observed liquidity remains in place and concern ETH prices, not USD. [Full threshold calculations](recovery-results/recovery-thresholds.csv).

![Buying required for recovery](recovery-results/recovery-costs.png)

## Conditional projections, not odds

The following comparisons keep speculative buying at its measured starting rate, except where stated. They vary how quickly token selling falls. A half-life is an assumption about future behavior; it has not been estimated reliably from the brief sample.

| Assumption | Price change at +24h | Price change at +48h |
|---|---:|---:|
| Buying and token selling both persist | −67.4% | −77.1% |
| Selling halves every 6h; buying persists | −18.4% | +24.1% |
| Selling halves every 2h; buying persists | +20.7% | +78.1% |
| Buying and selling both halve every 6h | −41.7% | −43.2% |
| Buying triples; selling halves every 6h | +64.5% | +272.6% |

**Do not average these or count winning cases as probabilities.** The persistent-flow case is a stress test, not a default prediction of a 67% decline. Sustained spending, rapid seller exhaustion and tripled buying are all uncertain. The large upside case likewise demonstrates sensitivity to assumed demand, not an expected return.

The +24h timestamp is **September 16, 2026, 22:45:58 UTC**; +48h is **September 17, 2026, 22:45:58 UTC**. At unchanged buying, the 2h-exhaustion case rebounds within the first day but still does not regain the 13:40 reference by +24h. The 6h case bottoms later and recovers more slowly. Those trough times come from the assumed decay schedules, not a discovered optimal entry time.

[All scenario assumptions](recovery-results/scenario-assumptions.csv), [results and UTC crossing times](recovery-results/scenario-summary.csv), [full paths and hypothetical 100,000-token exit quotes](recovery-results/scenario-paths.csv).

## What buying would make a recovery credible?

If selling halves every six hours, finishing +24h at:

- **10% above the new snapshot** requires about **62 ETH/hour** of sustained buying, versus the observed 35 ETH/hour.
- **The 13:40 reference** requires about **79 ETH/hour**, or **2.25 times** the observed rate.
- **The 10:09 reference** requires about **103 ETH/hour**, or **2.94 times** the observed rate.

If selling persists without decay, those requirements rise to about **205, 245 and 305 ETH/hour**, respectively. If sellers exhaust much faster, they fall considerably. These are conditional gross spending requirements; sale proceeds can recirculate, so they must not be labeled unique external capital. [Solved expenditure requirements](recovery-results/required-buying.csv).

## The next concrete catalyst: licenses

The next daily reset is **September 16, 2026, 01:04:04 UTC**, about **+2.30 hours** after the snapshot. The quota remains 100 licenses/day, with three per Charter/day; new ETH Charter issuance remains disabled at the pin.

A reset can create buying, but an allocation is not an ETH commitment. Existing owners can use accrued ledger earnings. The notebook compares 20% and 100% fresh funding, and illustrates average clearing prices at the issuance-based floor, last observed sale and implied opening price. It does not assume the whole quota clears at a single actual auction price or that all owners have the same balances. Internal spending is bounded by the available aggregate ledger.

With selling halving every six hours, adding 100 fully fresh-funded licenses per day at the illustrative last-sale price improves the +24h result from −18.4% to approximately **−14.6%**. The 20%-fresh-funded case has a smaller effect. Utility demand helps; it does not necessarily dominate speculative outflows. [License demand budgets](recovery-results/license-demand-budget.csv).

## Buybacks and rewards

The enabled-buyback scenario assumes execution gates permit hourly purchases and applies the observed caps. The current 111.72 ETH vault is finite, receives no assumed refill and cannot be treated as a permanent defense. In the 6h-selling-decay case, it improves the +24h result to about **−14.4%**, without independently restoring the earlier reference prices. This is hypothetical activation; no execution was observed at the pin.

Unwithdrawn earnings do not automatically sell. A separate stress retires half the branches at +6h, applies the congestion fee and sells the net minted tokens. The larger near-term influence remains what existing holders and buyers do. This does not rule out a later rewards-exit wave.

The current epoch ends **September 18, 2026, 01:00:30 UTC**, after the 48h horizon. The code rejects projections reaching that unsettled boundary rather than silently assuming future policy. Fees recycled into the next epoch, future vault allocations and future POL deployment are not included.

## What would change the assessment

Evidence favoring recovery would be sustained net buying across multiple non-overlapping windows, continuing declines in token sell volume, material fresh-funded license purchases, or actual buyback transactions. A brief green candle or internally funded auction sellout alone is insufficient.

Evidence favoring the earlier highs holding would be repeated larger sales, weak buying after the license reset, or a new branch-withdrawal wave that adds to existing inventory sales.

This overlay is deliberately distinct from the older agent simulation: it conditions on measured turnover and then varies explicit future assumptions. It does not claim a solved multiplayer equilibrium, seller cost-basis reconstruction, cross-venue arbitrage model, gas-inclusive trade recommendation or calibrated posterior. The source notebook is editable and every path has UTC timestamps.

## Reproduce and verify

```bash
python -m unittest discover -s . -p 'test_*.py' -v
python run_notebook.py recovery_update.ipynb
python verify_artifacts.py
```

The notebook runs offline. `collect_live_flow.mjs`, `analyze_live_flow.mjs` and `collect_recovery_state.mjs` collect public read-only evidence when a new snapshot is needed. The RPC stopped serving the preceding pin's historical state, so this update uses one fresh consistent pin rather than mixing old liquidity with a new price. The saved raw queries make offline reproduction independent of continued RPC archival access.
