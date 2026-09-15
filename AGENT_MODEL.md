# Agent model: decisions, taxes, and limitations

**Decision-tree coverage:** [what participant choices are modeled, and what remains approximate](DECISION_TREE.md).

This model turns the branch-cap and rational-demand discussion into executable scenarios. Read [rational_scenarios.ipynb](rational_scenarios.ipynb) for the executed experiment. The earlier flow notebook is retained as an explicitly imposed-demand comparison.

## What changed

| Earlier flow model | Agent model |
| --- | --- |
| Buying declines with a chosen half-life | Buying requires a positive fee-adjusted expected edge and available cash |
| Assumed daily license demand and external-funding fraction | Individual Charters compare ledger funding, wallet inventory, fresh purchases and not buying |
| Aggregate fractional branch entry/retirement | Integer branches; actual initial Charter distribution; 10-branch and 3/day per-Charter constraints |
| Fixed-cohort global capacity approximation | Live Charter capacity changes when new Charters enter or existing Charters are destroyed |
| Population retirement hazards | Full/partial retirement compared with keeping the remaining earning position |
| ETH Charter auctions disabled | Closed baseline plus explicitly hypothetical later ETH auctions |
| Broad scenario price distributions | Funding decomposition, fees, cash constraints, forecast error and consistency diagnostics |

**Buying has no imposed decay schedule. However, starting cash, beliefs, activity limits and valuation horizons are assumptions. Replacing a buying half-life with a guessed cash budget does not make the peak date empirically identified.**

## Evidence and initialization

All market balances and initial Charters use the September 15, 2026 10:09:19 UTC snapshot, block 63,576,310. The complete initialized-tick liquidity curve and independently reconciled position principal are reused. Later cap verification is identified separately; it is not mixed into the old market balances.

Charters begin with their observed integer branch counts and pending balances. The model treats each Charter as a decision unit even when a real wallet owns more than one. ETH allocations, wallet-token allocation among bankers and speculators, and prospective new-Charter buyer capital are hypothetical. The outside-pool token proxy includes non-pool contract balances and is not a reconstructed wallet inventory census.

A 100,000-token wallet and an observed one-branch Charter nearest the median pending balance are protected from population selling/retirement. Their hypothetical liquidation curves can therefore compare selling dates without double-selling the same position in the crowd. The other bankers act according to their policies. All bankers are assumed to check in, avoiding dormancy penalties.

## Decisions and their objective

Actors maximize forecast discounted net ETH over a finite set of candidate withdrawal horizons, with a default 30-day valuation horizon. This is an approximate receding-horizon decision rule, not a full dynamic program over every future purchase, partial sale, and withdrawal sequence.

The continuation value projects the actor's share of issuance after other branches enter/retire, applies the congestion fee, and quotes the resulting token sale through the known liquidity ranges. An externally funded license must improve continuation value by more than the cash purchase and inventory opportunity costs. Reinvestment compares the extra branch plus reduced ledger balance with keeping the original branch and ledger.

Partial retirement withdraws the proportional balance, removes the chosen branches and preserves the remainder. Before execution, decisions are rechecked after earlier actors have changed pool price and congestion. Execution order is randomized; it is not an MEV or transaction-priority simulation. License allocation orders positive bids by modeled surplus and rechecks costs/eligibility before executing them.

New Charter bids compare the initial branch's forecast value with the ETH ask. The future option to expand is not separately valued, so those bids omit an option that can be valuable. New entrants must fund both their Charter and the configured remaining wallet cash from the prospective-buyer budget. The global daily license quota still applies to them.

Prefunding uses the last observed clearing price or the projected floor, whichever is larger, as its price expectation. It bounds expected access by remaining slots, per-Charter limits and a share of daily license capacity. It compares purchasing tokens now with their forecast later cost. This is a simplified allocation/entry expectation, not a solved auction strategy or a guarantee of floor access.

## Beliefs and financial feasibility

Bankers use a prior daily growth belief plus a bounded, smoothed observed-momentum contribution. Speculative cohorts include momentum followers and mean reverters. Their cash/token allocations differ; the distribution is explicitly assumed. The initial momentum observation comes from the saved swap window, not a newly queried price.

Speculators trade toward fee-adjusted reservation prices subject to available tokens/cash and configured participation limits. A positive signal is not an instruction to spend money that does not exist. Sale proceeds can be reused; that reuse is not recorded as fresh external capital.

Forward prices are capped by the pool price achievable using the modeled available trading ETH plus explicit future capital arrivals. This prevents forecasts that require more cash than the scenario supplies. It is only a feasibility bound: available cash is not proof of willingness to buy. Initial banker/speculator budgets and ongoing external contributions are shown separately.

Default branch-entry, retirement and withdrawal forecasts update from recent simulated activity. They are approximations, not perfectly anticipated future behavior. Known withdrawal buckets expire according to their actual modeled seven-day calendar; uncertain future withdrawals are projected from the recent rate.

## Tax implementation

The official whitepaper was fetched again during this extension; its normalized text matched the saved version. Current tax values and the launch schedule are present in the pinned application snapshot, while the resolution-fee calculation is tested against pinned contract previews.

### Trading taxes and the LP fee

The launch opens at 90% buy/sell hook tax. Excess above the 2% buy and 3% sell floors halves every four minutes; the schedule reaches the floors after one hour. The saved market observation is already beyond that hour. The notebook displays the schedule but does not replay launch in future paths. Manual trading-tax overrides are restricted to 0–10% as hypothetical policy settings.

The pool's 1% LP fee is separate. ETH buys pay hook tax and then LP input fee; sales pay the token-input LP fee, then the ETH-output sell tax. Trading occurs through the exact observed range structure using floating-point curve arithmetic, not integer-exact router execution.

At unchanged marginal price and before price impact:

- An existing wallet sale retains `0.99 × 0.97 = 96.03%` of spot value.
- A wallet cash buy/sell round trip retains `0.98 × 0.99² × 0.97 = 93.1683%`.
- With a 2% resolution fee, branch withdrawal and sale retains `0.98 × 0.99 × 0.97 = 94.1094%` of gross ledger spot value.
- With a 60% resolution fee, branch withdrawal and sale retains `0.40 × 0.99 × 0.97 = 38.412%`.

These are conversion factors, not investment returns. License principal is consumed, so a new branch must generate enough additional earnings to recover it.

### Resolution fee and retirement

The model uses:

`fee = 0.02 + 0.58 × min((W + proposed_gross) / max(D + W, 10,000,000) / 0.10, 1)²`.

Here D is the pre-withdrawal pending balance and W the trailing gross withdrawals. The proposed gross counts in the exit pressure. Moving it from D into W leaves their sum unchanged; it must not be counted twice in the denominator.

Retiring k of n branches releases k/n of that Charter's ledger. Only the net amount is minted. Half the resolution fee is permanently removed from ledger claims; half enters the recycle buffer and is streamed in the next modeled epoch. The retired branches stop receiving subsequent accrual. Retiring all branches destroys the Charter. Partial retirement can reopen capacity in a surviving Charter.

### ETH routing, reserves and protocol execution

Hook taxes and ETH Charter receipts enter a fee buffer. At modeled epoch settlement, 70% enters the active vault, 15% the POL budget and 15% the team account. Positive epoch flow routes the vault allocation to expansion reserves; nonpositive flow routes it to contraction reserves. New Charter ETH is not counted as a swap or as direct token buying.

The issuance policy uses the two completed epochs' flow signal; negative signals cut the multiplier immediately, while increases need consecutive positive signals. Base issuance is capped by the remaining issuance budget. Recycled fees are accounted for separately from newly issued base rewards.

Optional contraction execution respects the smaller of 10% of vault ETH per hour and 0.2% of the estimated protocol pool depth per hour. The active protocol virtual-depth calculation matches the saved vault getter; actual swaps still use the reconstructed real range liquidity. Actual permission/keeper availability and TWAP checks can prevent execution. The execution scenario assumes those operational gates permit the modeled purchases; it is not a claim that they will happen automatically.

Protocol buys use normal hook tax by default because a tax exemption was not established from the docs. `protocol_buy_tax_exempt=True` is an explicit alternative assumption. Any tax paid by a protocol purchase returns to the fee buffer and is not new capital.

Optional POL execution buys tokens with half the available POL ETH and pairs available assets. Future liquidity is placed proportionally across the known ranges as a scenario approximation; actual future deployment ranges are not known. Unmatched assets remain accounted for as idle POL assets. All existing locked LP is retained and treated as safe.

LP fee claims are held in separate ETH/token accounts, outside active principal. They are not harvested in this experiment. The documented burning of protocol token-denominated LP fees occurs on collection; keeping those tokens in an uncollected, non-trading account avoids inventing additional demand or market sales. Physical burn totals therefore exclude that eventual collection burn. Future collection/routing of ETH LP fees is not assumed. No LP removal occurs, so third-party LP removal taxes do not generate flows here.

Expansion reserves are retained at their recorded ETH cost without forecasting gold prices, reserve-asset yield or redemption. They are not treated as a holder redemption claim or as cash available for speculative buying. Team fees are not assumed to be reinvested.

## Accounting and tests

Every modeled period verifies three independent identities:

1. **ETH:** pool principal + all modeled cash/fee/reserve accounts = initial ETH + explicit new capital arrivals.
2. **Physical STANDARD:** pool tokens + wallet tokens + fee/POL token claims = initial physical tokens + net withdrawal mints − actual token burns.
3. **Internal ledger:** pending claims = initial pending + credited base/recycled issuance − gross withdrawals − internal license spending.

Pool ETH changes also reconcile to actual principal inflows, gross swap outflows, and new LP pairing. Tests cover tax decay and override bounds, pinned resolution previews, internal versus external funding, partial/final retirement, cap enforcement, zero-budget rejection, protected positions, speculative fee hurdles and combined Charter/POL/fee accounting.

## Interpreting results

The notebook reports wallet sale timing, protected-branch withdrawal timing, licensing/funding composition, fee costs, and changes in live Charter capacity. It does not assign probabilities across scenarios or assert an unconditional top date.

A separate fixed-point-style iteration compares a trial future price/branch path with the resulting simulation, updating the forecast gradually. Beyond its finite horizon it assumes a flat terminal tail. Failure to converge is reported. A small numerical residual would still not prove a Nash equilibrium because the action set, valuation horizon, execution priority and future-policy expectations are simplified.

The seven-day forecast-error table is equally important: a seemingly rational decision under a bad forecast can have a poor outcome. Capital/quota sensitivity shows which results follow from assumed budgets rather than measured demand. No gas, private information, market manipulation, multi-venue arbitrage, secondary Charter market, or full transaction execution is simulated.

Primary source: [STANDARD official whitepaper](https://www.standardreserve.xyz/whitepaper/). See [DATA.md](DATA.md) for pinned public evidence and collection limits.
