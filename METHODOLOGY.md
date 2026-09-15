# Mechanism, assumptions, and interpretation

## The economic game

STANDARD wallet balances earn no passive yield. Charters have branches; branches divide issuance, which accumulates in an internal earnings ledger. A withdrawal retires branches and mints the ledger balance after a resolution fee. Selling those newly received tokens adds supply to the pool. New license purchases increase the branch count and dilute existing branches. Depositing tokens without buying a license adds no earning share.

This creates four distinct flows:

| Action | Immediate pool effect | Later effect |
| --- | --- | --- |
| Buy tokens to speculate | ETH enters; token price rises | Buyer may sell later |
| Buy tokens to fund licenses | ETH enters; purchased tokens leave tradable circulation when consumed | Extra branches divide future issuance |
| Reinvest ledger earnings | No necessary ETH market purchase | More branches; fewer ledger earnings available for withdrawal |
| Withdraw and sell | Net tokens enter pool; ETH leaves; price falls | Retired branches leave survivors a larger issuance share |

A withdrawal without a sale has no immediate AMM price effect. Issuance and policy changes affect potential future flows, not price mechanically. There is no common fixed vesting date in the modeled branch system. The 48-hour withdrawal wave is a stress assumption, not a discovered unlock schedule.

The model follows the official mechanism as described and checked against pinned getters and selected call behavior. It is not a complete deployed-source verification. Official description: [STANDARD whitepaper](https://www.standardreserve.xyz/whitepaper/).

## Correct comparison for waiting

For initial quantity Q and random future quantity multiplier G, holding beats selling at spot only if `E[Q × G × P_future] > Q × P_now`. In general `E[G × P]` cannot be replaced by `E[G] × E[P]`: rewards and price may be correlated. For actual positions, compare final **net ETH** after resolution fees, LP fees, hook taxes, and the position's own price impact.

The notebook's optimization is a **precommitted full-exit time**: choose the hour whose average net ETH across paths is largest. It does not choose each path's best hour with hindsight and average those profits. Pathwise price maxima are reported separately as timing distributions.

This is a population model, not a solved multiplayer equilibrium. It does not optimize partial harvesting, staggered sales, relocking policies, reactive stopping rules, or individual wallet strategies. A later optimal branch harvest than token-price peak can be rational because branch income keeps accruing. Extreme late survivor gains can also expose an unrealistic assumption that competitors exit while you alone retain your share.

## Liquidity reconstruction

Pin: Robinhood chain **4663**, block **63,576,310**, **2026-09-15 10:09:19 UTC**.

- STANDARD: `0x88ad8DdF1E3898412146a534538d418c6F8A9062`
- Pool ID: `0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9`
- PoolManager: `0x8366a39CC670B4001A1121B8F6A443A643e40951`
- StateView: `0xf3334192d15450cdd385c8b70e03f9a6bd9e673b`
- Hook: `0xF1eE073811B14359D850825E48d200483200eDcd`
- Block hash: `0xaa4a216e415c3fe6a7d2bdfdd661bdf8d1486d9f183b96422db098a8468d6a6b`

All bitmap words for spacing 200 were queried, yielding 66 initialized ticks. Liquidity-change events were replayed from block 63,123,899, yielding 54 positive positions. Each was verified against the position getter at the pin. Replayed positions reconstruct every tick's liquidity net. Their asset principals reconcile to the aggregate tick curve. The pin was checked before and after collection. This is a latest-L2 observation, not a claim of L1 finality.

Actual swap principal is **3,352.8791 ETH + 23,460,570.3013 STANDARD**. Of this, **3,340.9838 ETH** is in protocol-owned positions (99.6452% of ETH principal). The active virtual ETH reserve is **4,370.4644 ETH**; the protocol depth getter is **4,329.5758 ETH**. Neither is substituted for actual principal.

**User-specified assumption: protocol-owned locked liquidity is permanently safe and remains in the pool.** The remaining observed liquidity also stays in place in the baseline. There is no LP-removal event or custody-loss probability in the simulations. This assumption does not freeze price: ordinary sales remove ETH through swaps.

ETH is currency0; STANDARD is currency1. Write `s = sqrt(STANDARD / ETH)` and `P = 1/s²`. Inside a range with liquidity L:

- Token sale: `Δtoken = L × (s_after − s_before)` and `ETH_out = L × (1/s_before − 1/s_after)`.
- ETH purchase: the same equations run in reverse.
- At an initialized tick, the active L changes by liquidity net. Empty gaps and finite boundaries are traversed explicitly.

Fees accrue outside principal in this v4 model: 1% LP input fee, 2% buy ETH tax, and 3% sell ETH tax at the snapshot. Buying and selling are simulated sequentially; price is not computed with one global constant-k shortcut. Floating-point arithmetic approximates the contract's integer rounding. Five final observed swaps reproduce recorded output and ending price within numerical tolerance. These are scenario estimates, not wallet-specific router quotes.

Primary implementation references: [StateView](https://github.com/Uniswap/v4-periphery/blob/main/src/lens/StateView.sol), [concentrated liquidity](https://developers.uniswap.org/docs/get-started/concepts/liquidity-providers/concentrated-liquidity), [fees](https://developers.uniswap.org/docs/get-started/concepts/fees).

## What is observed and what is assumed?

**Observed at the pin:** pool/ranges, current fees, supply, all issued Charter balances and owners, branch count, ledger pending balances, issuance multiplier, auction state, reserve balances, and approximately two hours of pool swaps. Current branches and ledger balances reconcile across Charters.

**Derived proxies:** initial buying rate; token-sale turnover relative to total supply outside the pool; current income per branch; illustrative next license floor/opening. Outside-pool supply includes non-pool contract balances. Swap history cannot identify buyer intent, unique participants, or durable demand.

**Assumed:** demand half-lives of 6/24/72 hours; how initial recent buying persists; branch retirement hazards and drawdown responses; license uptake; 25% of population licenses funded externally; 90% of returned tokens sold; and independent lognormal parameter variation plus correlated buying noise. The 30/50/20 scenario weights are subjective judgments. They are not fitted probabilities. The stress wave has zero weight in the headline mixture.

Returns are modeled jointly with the market: issuance changes pending balances, licenses consume balances or market-bought tokens, retirement produces sellable tokens, and sales move the same pool curve. Population retirements remove the same proportion of unprotected branches and ledger balances. This is a simplifying assumption about the distribution of earnings and behavior.

The default disables automatic buybacks: a funded vault is not assumed to execute. An optional defense scenario supports modeled buybacks and proportional future LP additions. Its future LP deployment is illustrative; the default uses only known liquidity. Fee recycling and the documented epoch multiplier response are included. Policy settings are held fixed except for that modeled response.

## Position definitions

| Position | Objective | Main tradeoff |
| --- | --- | --- |
| 100,000 wallet tokens | Maximize full-sale net ETH | No income while waiting; direct exposure to flow reversal |
| Existing one-branch Charter | Maximize final withdrawal-and-sale ETH | Income versus falling price and congestion fees |
| Existing ten-branch Charter | Same, including own exit size | More income and larger fee/price impact |
| Extra branch funded externally | Incremental terminal ETH versus keeping the original branch, minus entry cost | Purchase price, availability, dilution, and time needed to recover capital |
| Reinvest earnings into one branch | Total terminal ETH versus original branch | Foregone withdrawal; more future earning share |
| Fund another owner's branch | Hypothetical payout share minus full funding cost | Native contract offers no independent non-owner withdrawal; requires separately specified agreement |

Representative initial balance is the observed median one-branch pending balance, not a supplied personal wallet. Ten-branch balance is ten times that median. The user's modeled branches and wallet tokens are excluded from the crowd's sell/retire hazard until their hypothetical exit.

External branch purchases occur once eligible at the next daily auction boundary. The opening and floor cases hold an illustrative license price fixed for comparison. Floor supply is not guaranteed. Internal reinvestment waits for sufficient earnings. Population license uptake is fractional expected participation, not an exact discrete auction/order simulation.

For third-party funding, the worksheet assumes the owner pays an agreed share of incremental terminal proceeds attributable to the added branch. Payment-probability sensitivity is an agreement assumption, not locked-LP risk. It assumes no delay and no separate wrapper fees. A real arrangement may have different fee aggregation, timing and control. Native non-owner `deposit`, `buyLicenses`, and `withdraw` probes all reverted `NotCharterOwner()`; the raw evidence is saved.

## Reading the results

- Simulation quantiles are conditional on the chosen distributions, not calibrated confidence intervals.
- A path maximum at hour zero means the future simulation never exceeds the snapshot. It does not establish a historical all-time high.
- Unequal-width histogram buckets have unequal opportunity to collect probability mass. The notebook also reports a fixed six-hour-bin mode.
- The peak of the average price, median of individual peak times, and optimal average sale time are different statistics.
- A maximum at the 14-day boundary is unresolved, not proof that day 14 is optimal.
- A withdrawal fee depends on the proposed gross withdrawal and recent system withdrawals. Larger holders cannot assume the small-holder fee.
- Gas defaults to zero and is editable. ETH/USD returns, operational failures, governance changes, future new demand catalysts and future liquidity additions are not predicted.
- Monte Carlo bootstrap checks sampling variation only. More simulation paths cannot identify unknown future behavior.
