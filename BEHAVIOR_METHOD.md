# Behavior model: evidence, decisions and accounting

This supplements the earlier notebooks without changing their pinned evidence. See [the findings and full flow map](BEHAVIOR_MAP.md), [executed notebook](participant_behavior.ipynb), [source](behavior_model.py) and [test regressions](test_behavior.py).

## 1. Three different kinds of input

| Kind | Included | Interpretation |
| --- | --- | --- |
| Pinned observations | Token balances, native ETH, owners, bank claims, branches, auction state, initialized liquidity ticks, treasury balances and execution calls | Observed at block 64,168,224; exact token balance replay reconciles. Public balances are capacity, not committed spending. |
| Historical descriptions | Canonical buys/sells, token acquisition lineage, recent event counts, sale fractions, first-sale observations and actual license funding | Addresses are not people. Association is not motive. Fungible lineage is allocated pro-rata. Unresolved routes remain unresolved. |
| Future assumptions | Private price beliefs, mean reversion, momentum, seller activation, new buyers, expected dilution/withdrawals, owner review, prefunding and buyback execution | Editable scenario inputs. Neither on-chain facts nor calibrated probabilities. |

The [official whitepaper](https://www.standardreserve.xyz/whitepaper/) provides context; saved ABI, calls and logs establish the pinned observations. Earlier [mechanics](AGENT_MODEL.md), [evidence notes](DATA.md), [buyback execution checks](BUYBACK_STATUS.md) and [decision coverage](DECISION_TREE.md) retain their own timestamps. The current primary packet is [behavior-evidence/target.json](behavior-evidence/target.json), with the block hash/header and public RPC requests preserved alongside it.

Canonical historical attribution covers approximately 97.74% of buy ETH and 98.40% of sell ETH over the complete history. Other transactions stay in the unresolved table. Relevant verified secondary routes contribute acquisition provenance; future execution uses only the canonical market. Timestamps between archived headers are interpolated, so short gaps and window boundaries are approximate. Exact transaction and block identifiers remain available.

The measured balance set has 8,575 addresses. The historical population includes additional exited addresses without a fresh native balance; those cash values remain flagged as unobserved. They receive no spending budget in this simulation. WETH/USDG are measured in the evidence but not automatically converted into native ETH. Exchange accounts, bridge inflows, outside wealth and future LP deposits are not inferred.

## 2. State and conservation

Each wallet has one token balance and one native-ETH budget. Each Charter has its own branches, ledger and owner reference. Multiple Charters share their owner's wallet exactly once. The model starts from the observed 999 live Charters, 941 owners and 1,153 branches.

At every step:

- ETH in pool principal, wallets, vaults, tax hook, POL, team allocation and uncollected LP fees equals initial ETH plus explicitly added outside capital.
- Physical STANDARD in pool principal, wallets, uncollected LP fees and other fixed custody equals initial supply plus retirement mints minus deposits/license conversions and buyback burns.
- Bank claims equal initial pending balance plus modeled issuance and deposits, minus license payments and gross withdrawals.

Claims are not counted as physical tokens before minting. A sale transfers existing ETH from the pool to a wallet; it does not create new capital. Taxes move ETH to the hook. Every trade executes through the reconstructed initialized-tick curve. Pool fees accrue separately from principal. This is floating-point scenario arithmetic, not an integer-exact router quote.

Assertions also check nonnegative balances, daily quota, per-Charter purchase limit and branch cap. Locked LP stays in the pool as requested. No liquidity removal, future liquidity addition, fee harvesting or POL execution is assumed. Safe custody of liquidity does not make its ETH reserve constant.

## 3. Wallet decisions and cadence

For an observed wallet, each side has an activity rate initialized from its last six-hour event count divided by six. For a time step Δh, the probability of a review on that side is:

`Pr(review) = 1 − exp(−λ × Δh × scenario activity multiplier)`.

Rates are capped at four reviews per hour because the base simulation uses 15-minute steps and does not replay launch microbursts. This deliberately loses sub-step timing. Zero-history sellers receive a separate activation proxy: first-observed sellers in the last two hours divided by twice the number of positive-inventory inactive holders. At this pin it is approximately 0.01565 per hour. Applying it to other zero-sale-history wallets is an assumption; it is not a fitted survival law.

An activity clock triggers reconsideration, not a forced trade:

- Sell the wallet's observed median partial-sale fraction when its discounted expected later price is below current price. New/unknown sale sizes default to 95%; selected fractions are floored at 1%. This compares marginal prices; it is not a fully optimized multi-period execution schedule for a large holder.
- Buy up to its observed mean recent ticket, limited by cash, only when the expected executable future sale clears the current cash cost and fees.
- Sale proceeds remain available for later re-entry. Inactive holders can become sellers and then use the observed recent-seller repeat rate.

New entrants arrive under a Poisson assumption at the observed first-buyer-address rate, multiplied by the scenario factor. Their budgets are bootstrapped from those addresses' first-window spending. This extrapolates past spending into future available capital; it does **not** trace proven external ETH funding. Entrants still decide whether to buy. They use a one-per-hour review assumption, explicitly distinct from existing-wallet cadence.

The model uses heterogeneous log-price-growth beliefs, a clipped recent momentum signal and a mean-reversion preference. Subjective prices are capped at prices supportable by all modeled wallet cash plus assumed capital arriving within the simulation horizon and the enabled buyback vault. This is an internal budget bound, not a ceiling on the real market. Long-horizon branch valuations inherit this restrictive finite-capital assumption.

Historical first-sale survival includes unsold wallets as right-censored observations in 15-minute bins. Current strategy labels condition on later observed behavior, and within-bin censoring is approximate. Consequently it is descriptive only and is not used as a validated predictive hazard. A Charter owner may also speculate; classifications do not assert private motives.

## 4. Branch value and allocation

Internal issuance follows the pinned base rate, multiplier and recycle rate. A branch owns a share of a fixed aggregate issuance stream, not a fixed independently compounding APY. If the modeled branch count is N and an owner has n branches, current accrual is `issuance × n/N`. New branches dilute that share.

At each owner review the model evaluates holding against partial and full retirement, and expansion against keeping the original position. It compares discounted **executable** ETH values on a candidate grid of 1 hour, 3 hours, 6 hours, 12 hours, 1, 2, 4, 7, 14, 30 and 60 days. Current retirement is a separate available action. A terminal-grid maximum is right-censored, not a proven optimum at day 60.

Prospective dilution is an explicit expected branch-arrival rate, bounded by current live-Charter capacity. Continuation values use the current issuance regime, expected crowd withdrawals and current liquidity structure. They do not solve future auctions, issuance regimes or all opponents' strategies self-consistently.

For gross retirement G, current pending claims D and seven-day gross withdrawals W, the modeled fee is:

`fee = 0.02 + 0.58 × min(((W + G) / max(D + W, 10,000,000)) / 0.10, 1)²`.

Retiring k of n branches releases `k/n` of the Charter ledger before the fee, mints the net claim and destroys k branches. Half the fee enters the recycle buffer; the other half ceases to be a claim. It is not an ETH transaction. The owner can sell the minted tokens or hold them if their discounted liquid value is higher. Actual saved withdrawal buckets expire by bank day; hypothetical additional withdrawals in valuation use an approximate rolling seven-day expectation.

The daily license quota is 100, with at most three purchases per Charter per day and ten branches per Charter. The model tracks purchases already made today. Current-day ask decays toward its floor with the observed four-hour gap half-life. Day rollover updates the floor using issuance/branch count and the opening ask using the last sale. Rollover is evaluated on the simulation grid, within 15 minutes in the base case.

For an expansion:

1. Spend available internal ledger first.
2. Use the owner's existing wallet tokens for the remaining gap.
3. Buy tokens only for the residual shortfall, within that shared wallet's cash budget.
4. Recheck value after earlier actors' trades and update all balances and auction caps.

The waiting option compares four-hour ask savings against foregone rewards and an assumed probability that the remaining quota sells out. Its crowd arrival rate is a belief, not an auction forecast. This is a finite-action heuristic rather than a complete optimal stopping solution.

Prospective prefunding considers one next-day license per eligible Charter, capped at one global daily quota per review. It buys only if current purchase seems cheaper than buying at the owner's expected later price and the continuation value supports the cost. It creates no reservation or guaranteed allocation. Later price changes or a missed quota can turn prefunded inventory back into speculative sale inventory. A separate sensitivity disables this route.

All owners are assumed attentive enough to maintain the applicable participation requirements. The model does not estimate dormancy, gas, transaction failure, front-running, personal liquidity needs or risk aversion. Action selection is sequential and greedy; candidate retirement choices are rechecked after other actors, but rejected candidates do not trigger a global reoptimization. Shared-wallet funding chooses an affordable allocation, not a globally optimal funding mix across every Charter and future period.

ETH Charter auctions are disabled in the pinned state, and the model refuses states where they are enabled. Third-party sponsorship is mapped but is not an independent native yield position: no enforceable external-funder payout or withdrawal right has been established. A negotiated agreement would need separate cash flows, control and default assumptions. This model assigns no such promised yield.

## 5. Taxes, buybacks and treasury

The snapshot uses 2% buy hook tax, 3% sell hook tax and a 1% canonical LP fee. Ignoring size, the approximate gross price increase required to offset one buy and one sell is:

`1 / [(1 − .02) × (1 − .01)² × (1 − .03)] − 1 = 7.33%`.

Slippage and gas raise the required move. A spot recovery alone is therefore insufficient evidence of a profitable re-entry.

The contraction vault is `0x796e80E8ABcedc30c700A9587F7933d3342B8946`. At the current pin `lastTickAt` is zero. Public execution is disabled; the owner counterfactual call succeeds. [Saved calls](behavior-evidence/buyback-execution.json) and [vault events](behavior-evidence/vault-events.json) distinguish execution capability from execution history. There is no verified start schedule.

Only an explicit scenario switch makes it execute. Each assumed successful hourly tick spends the smaller of 10% of remaining vault ETH and 0.2% of protocol depth. The first depth is observed; later depth scales with the square root of price under unchanged ranges. TWAP success is assumed, not simulated. Buyback tax exemption is a separate configuration flag and defaults off. There is no invented requirement that current flow must be negative to spend the existing vault.

Epoch-end allocation sends the configured vault share toward expansion for positive epoch flow and contraction otherwise, plus team/POL shares. The issuance multiplier depends on the current-plus-previous epoch signal and positive streak. The 24-hour primary scenarios finish before the pinned September 18, 01:00:30 UTC epoch end, so the much larger hook balance is **not** spent as if already in the buyback vault. POL remains idle, and neither treasury balance is an enforceable holder redemption claim.

## 6. Why this is not an equilibrium or a calibrated forecast

An expected reward comparison is `sell value now` versus `E[quantity later × executable price later, after costs]`. Generally `E[quantity × price]` does not equal `E[quantity] × E[price]`. Rewards, dilution, congestion and price are linked. The model preserves these links along individual paths, but assigns no empirical probability distribution over alternative future beliefs.

Likewise, a constant-product no-fee price identity does not justify ignoring trade order, fees or concentrated liquidity here. Trades change actual tick positions, wallet budgets and subsequent decisions; LP fees leave principal and hook taxes are separately routed.

Participants are locally profit-seeking under their own beliefs. They are not assumed clairvoyant, mutually consistent or in Nash equilibrium. Four random seeds per case measure only a small amount of model variation. Scenario medians and ranges are **not** market confidence intervals. Changed scenarios consume random draws differently, so the same seed does not guarantee perfectly matched future shocks.

Sensitivity cases change action ordering, step size, game prefunding and valuation horizon. Their material differences are evidence against using the generated peak times as precise signals. Time-step refinement here changes both random clocks and feedback; it is not a deterministic convergence proof. The saved prior-hour persistence holdout is a deliberately simple stability diagnostic, not an out-of-sample success claim for the new model.

The marginal exit worksheet quotes small orders on saved paths without removing an actual wallet from the crowd or resimulating responses. It supports comparisons of precommitted times, not a claim that a large investor can achieve the hindsight best price. An actionable larger-position counterfactual would need protected inventory, market impact, other actors' responses and independently justified scenario weights.

## 7. Validation and reproducibility

The code tests exact evidence identity/reconciliation, conservation through trades and buybacks, owner budget sharing, internal-only license funding, full retirement when waiting has no value, limits, previously inactive seller activation, expiry of historical withdrawal pressure and deterministic seed reproduction. Every simulated step also checks conservation and capacity constraints.

`verify_behavior.py` checks the frozen artifact hashes, all 32 primary paths, sensitivity outputs, finite prices, end timestamps and executed notebook cells. Accounting correctness does not establish economic forecasting accuracy. The manifest is a reproducibility boundary, not a security audit of the full protocol.
