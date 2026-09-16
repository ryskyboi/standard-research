# Action framework: wallet tokens, existing branches and new licenses

**Decision objective:** risk-adjusted future ETH, without assuming indefinite fresh entrants, token-price appreciation or a redeemable treasury floor. This is a conditional judgment, not a proved optimum, personalized allocation or trade instruction.

**Live check:** September 16, 2026 **01:30:53 UTC**, Robinhood block **64,116,566**. [Raw pinned RPC evidence](action-evidence/2026-09-16T01-30-53.json). The earlier participant snapshot and auction-funding observations remain unchanged.

## Preferred posture

**Reduce liquid token exposure; retain existing branches with small accrued balances; wait on expensive new licenses; evaluate harvesting large bank balances.** This deliberately treats different claims differently. The strongest quantitative case is for waiting on new licenses, conditional on availability. The token-direction judgment is less certain because future capital and participant beliefs are unobserved.

| Position | Default under this objective | Reason and reversal condition |
|---|---|---|
| Tokens in a wallet | Prioritize reducing speculative exposure; size execution to liquidity | No automatic branch yield. Recent sell pressure was mostly market-acquired inventory, while much expansion was prefunded. Hold more only with a specific thesis for sustained net buying that covers remaining seller inventory. |
| Existing branch, small pending balance | Keep earning without topping up merely because price is down | The extra daily claim is large relative to what immediate retirement realizes. Retirement permanently destroys earning capacity. A severe expected price fall, policy/issuance change or higher future exit fee can reverse this choice. |
| Existing bank, large pending/prefunded balance | Consider realizing part/all of the claim | Daily issuance adds little percentage growth to a large balance. With several branches, partial retirement can reduce exposure while retaining a Charter. With one branch, full retirement also destroys the Charter, so include that lost option. |
| Buy new licenses now | Wait for a materially better price unless scarcity risk justifies the premium | Current price is expensive relative to initial issuance, and the Dutch decline is much larger than near-term foregone rewards. Waiting can lose today's quota. |
| Add wallet tokens to a Charter | Deposit only for a deliberately chosen purchase/action | A bank deposit alone does not add a branch or increase its issuance share. It converts liquid tokens into an internal claim whose withdrawal requires branch retirement and resolution fees. |
| Fund another person's Charter | No standalone investment case without enforceable payout rights | Funding does not give the sender branch ownership or an automatic revenue claim. A private agreement adds counterparty risk; it is not the native on-chain payoff. |

## Why new expansion can wait

At the live check, **52 licenses had sold and 48 remained**. Price was **22,100 STANDARD**, with **1,151 total branches** and **608.2 tokens/day per branch initially**. Gross constant-share payback is **36.3 days**, before dilution, fees and price changes. This is a token-count comparison, not a forecast of ETH profit.

Under unchanged auction settings and available quota, at **05:30:53 UTC** (+4 hours, +0.1667 days) the price would be approximately **11,687 tokens**. Waiting saves **10,413 tokens** and forgoes about **101 tokens** of initial branch issuance. Earlier purchase buys certainty of obtaining a slot and earlier participation, not enough four-hour issuance to cover that price premium.

At 100 added branches/day, a single new branch would earn only approximately **8,979 tokens over 30 days**, assuming 700,000/day issuance continues and ignoring future exits. The continuing branch can still have value beyond that horizon; the calculation is not a complete lifetime valuation. With fewer additions, dilution is lower. Policy can also reduce issuance.

Waiting is not risk-free: the remaining quota can sell out. A rational early buyer must value guaranteed capacity and future options enough to justify the premium. Observed sales do not prove that premium is attractive for a new buyer with an ETH-preservation objective.

## Existing branches are a different decision

For a simplified one-day comparison with unchanged fees and negligible impact, let B be current pending tokens and Y tomorrow's additional issuance. Waiting beats full retirement today when:

`expected future price / current price > B / (B + Y)`.

This compares cashing the whole branch now versus later. It is not an optimal policy proof, and it must be adjusted for dilution, resolution-fee changes, slippage, uncertainty and any further continuation value.

- B = 650 and Y = 600: waiting can offset about a **48%** one-day price fall.
- B = 25,000 and Y = 600: it offsets only about **2.3%**.
- B = 75,000 and Y = 600: it offsets only about **0.8%**.

Those are illustrative balances close to observed categories, not refreshed individual quotes. The full pinned owner-level table is [branch-hold-thresholds.csv](participant-results/branch-hold-thresholds.csv). Current bank balances and a holder's own position size determine the actual comparison. Rewards do not arrive as spendable tokens without retirement.

The high relative growth of a small existing branch claim does not justify paying a large premium to acquire an additional branch. Sunk acquisition cost does not enter the marginal keep/retire decision, but the option being destroyed does.

## What the flows say

The [participant findings](PARTICIPANTS.md) show 322 ETH bought versus 644 ETH sold in the six hours before 00:44:57 UTC. Many sellers were depleted, so perpetual extrapolation is wrong; substantial inactive inventory can supply replacement sellers.

By 01:14:41 UTC, approximately 90% of the tokens used for 51 new licenses came from earlier bank balances or prefunded wallets. License-buying addresses accounted for 23.4 ETH of 229.9 ETH in canonical buys. Expansion was real, but its token burn overstated its immediate fresh ETH bid. The initial +6.4% rebound weakened to +1.2%; the current check shows price approximately 0.000114915 ETH, so short-term bounces remain possible. No new branch withdrawals were observed between the last auction checkpoint and this live check.

A more bullish allocation needs persistent net ETH buying after the opening burst, fresh funding rather than repeatedly consuming prefunded inventory, and absorption of new selling addresses' supply. There is no calibrated probability of a new high in this research.

## Avoid paying trading costs repeatedly

At current 2% buy tax, 3% sell tax and 1% LP fee each way, a small buy-and-sell round trip needs approximately **7.33% price appreciation** to break even before slippage, gas and optional router charges. Selling and rebuying requires a sufficient decline to restore the same token quantity. Execution size and actual quotes matter; the model's protocol-only fee calculation is not a live router quote.

**General course:** preserve liquid optionality, keep cheap existing earning capacity when its continuation value justifies it, and require a much better marginal entry price for new expansion. Exact sale amounts, retirement counts and timing require the actual wallet quantity, Charter pending balances, branch counts and holding horizon.
