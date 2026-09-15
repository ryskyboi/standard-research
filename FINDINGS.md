# Findings from the frozen September 15 snapshot

**Later evidence:** see the [22:45 UTC recovery update](RECOVERY_FINDINGS.md) and [executed notebook](recovery_update.ipynb). The experiments on this page retain their original frozen snapshot.

[UTC timestamp reference](TIME_REFERENCE.md): elapsed hours/days are retained; calendar times are UTC.

**Earlier imposed-flow experiment.** For the model with profit-seeking demand, taxes, finite cash and Charter-entry scenarios, see [the new findings](AGENT_FINDINGS.md) and [agent notebook](rational_scenarios.ipynb). Timing below is conditional on the older buying-decay assumptions.

**Read first:** these dates are conditional on imposed buying-decay assumptions. They are not calibrated forecasts of when buyers stop. [The rational-demand analysis](RATIONAL_DEMAND.md) explains the branch caps, dilution, funding sources and disabled ETH Charter auction.

## 1. A top estimate requires a view on how long buying continues

The central scenario puts the price top and best 100,000-token sale at **+19 hours / 0.79 days (2026-09-16 05:09:19 UTC)**. The distribution of individual path peaks has a 10–90% range of **+8 to +32 hours (2026-09-15 18:09:19 UTC to 2026-09-16 18:09:19 UTC)**. The mean sale-proceeds curve stays within 1% of its maximum from **+16 to +22 hours (2026-09-16 02:09:19 UTC to 2026-09-16 08:09:19 UTC)**; the exact maximizing hour should not be overinterpreted.

A six-hour demand half-life moves the best sale to +4 hours (2026-09-15 14:09:19 UTC). A 72-hour buying half-life moves it to +35 hours (2026-09-16 21:09:19 UTC). The observed two-hour average buying rate was approximately **272 ETH/hour**, versus **448 ETH/hour** over the latest hour. The central initial rate blends those two observations; it does not assume the latest burst lasts indefinitely.

Under the editable 30/50/20 weights, the most populated six-hour peak bin is **0–6 hours (2026-09-15 10:09:19 UTC to 2026-09-15 16:09:19 UTC)** (18.8%); a further **5.7%** of weighted paths have their maximum at the snapshot. The mixture's maximum-mean-ETH selling time is **+23 hours / 0.96 days (2026-09-16 09:09:19 UTC)**. This distinction matters: a likely early top and a later expected-value optimum can coexist when bullish paths offer larger payoffs.

These percentages describe assumed scenarios. They are not estimated real-world probabilities, and the empirical history does not establish an unconditional “most likely top.”

## 2. Locked liquidity improves available exit depth without fixing price

Actual pool principal: **3,352.8791 ETH**, with **3,340.9838 ETH** in protocol-owned positions. Those positions are treated as permanently safe and retained. All 66 initialized ticks and 54 positions were reconstructed and reconciled. The 4,370.4644 ETH active virtual reserve overstates actual pool ETH; the simulation uses the range curve instead.

At the snapshot, approximate net proceeds after 1% LP and 3% sell fees are:

| Tokens sold | Net ETH |
| ---: | ---: |
| 1,000 | 0.1776 |
| 100,000 | 17.6856 |
| 1,000,000 | 170.4557 |
| 10,000,000 | 1,251.6617 |

These quotes include price impact across observed ranges. They exclude gas and integer-exact router behavior. Locked LP can still exchange its ETH for tokens through normal trading.

## 3. Existing branches and new branches have different economics

Central-case results, measured from the snapshot:

| Position | Best modeled exit | Mean ETH | Interpretation |
| --- | ---: | ---: | --- |
| Existing one branch | +44 h (2026-09-17 06:09:19 UTC) | 0.3379 | Total withdrawal-and-sale proceeds |
| Existing ten branches | +44 h (2026-09-17 06:09:19 UTC) | 3.3703 | Total proceeds; own exit fees and impact included |
| Extra branch at implied next opening | +56 h (2026-09-17 18:09:19 UTC) | −8.2726 | Incremental net ETH after funding, versus keeping the original branch |
| Extra branch at illustrative floor | +56 h (2026-09-17 18:09:19 UTC) | −0.2505 | Incremental net ETH; floor availability is hypothetical |
| Internal reinvestment policy | +38 h (2026-09-17 00:09:19 UTC) | 0.3356 | Total proceeds; includes exiting before sufficient earnings accrue to reinvest |

Current gross income is **636.94 tokens per branch per day**. The illustrative floor is **1,273.89 tokens**, roughly two days' output. The implied next opening is **23,776.68 tokens**, roughly 37.3 days' current output. An entry price stated in “days of rewards” still needs the future token price, dilution and fees to work out.

The high opening-price branch purchase loses money in every modeled scenario. The floor purchase is negative in the central case and positive in the continued-rebound case, where average incremental proceeds are about **0.1996 ETH** and the simulated 10th percentile is negative. Early speculative buying does not automatically make buying a branch attractive at the later auction time.

In the fast-fade scenario, surviving branches recover later as competitors retire. Their best value is at the final 14-day boundary (2026-09-29 10:09:19 UTC). **The optimal date is unresolved** in that case; the result depends on continued competitor retirement and is not a reason to declare day 14 optimal.

## 4. Funding someone else's branch adds a separate participation problem

The native `deposit`, `buyLicenses`, and `withdraw` probes reject a non-owner. The worksheet therefore models a hypothetical owner agreement, not an available native position.

For the illustrative floor-funded branch:

- **Central case:** even receiving 100% of modeled incremental proceeds loses about **0.2505 ETH** on average. Receiving 80% increases that loss to about **0.2911 ETH**.
- **Continued rebound:** receiving 100% makes about **0.1996 ETH** on average; receiving 80% makes about **−0.0139 ETH**. At that modeled optimum, the funder needs roughly **81.3%** of proceeds just to break even in expectation.
- Assuming only an 80% chance of receiving the promised 80% share makes the continued-rebound result about **−0.1847 ETH**.

Those payment probabilities are illustrative agreement assumptions. They do not apply to locked pool liquidity. Actual ownership, payout timing, the full Charter's withdrawal fee, and a funder's ability to force an exit would need a specified agreement or wrapper.

## 5. What should move the price up or down?

**Upward flows:** fresh speculative ETH buying; fresh token purchases to fund licenses; executed buybacks; additional useful liquidity can reduce impact but does not alone guarantee a higher price.

**Downward flows:** speculative holders selling; withdrawals followed by token sales; weakening fresh buying while issuance-related sales continue. More issuance adds potential future sell inventory. Reinvesting ledger earnings does not create the same immediate ETH inflow as a fresh market purchase.

Watch demand persistence, net ETH flow, withdrawal congestion, and actual license uptake. The forecast changes materially if those assumptions change. There is no empirically established sharp unlock date in this model and no guaranteed calendar top.

Full assumptions, limitations, and primary references are in [METHODOLOGY.md](METHODOLOGY.md). Exact output tables are in [notebook-results](notebook-results/).
