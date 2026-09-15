# Branch caps and rational demand

**The existing notebook assumes speculative buying decays. It does not estimate the probability of that decay or solve a rational-actor equilibrium. Its early top is conditional, not evidence that the flywheel must fail within 48 hours.**

This note derives the constraints that a better demand model must respect. Arithmetic is reproduced by `python rational_demand.py`; outputs are in `rational-demand-results.json`.

## 1. The limits are real, but the total ceiling is not imminent

The original application snapshot reports:

| Constraint | Setting |
| --- | ---: |
| Maximum branches per Charter | 10 |
| New branches per Charter per auction day | 3 |
| New branches system-wide per auction day | 100 |
| New Charters sold for ETH per day | 0 — disabled |

These getters were independently re-read at **block 63,604,176, September 15, 2026 at 10:56:26 UTC**, hash `0x6893f2d2042da61f4c8e860d11465479cc3ffa126396e9f3cb0d9fc2692f9495`. They match the relevant saved settings. The later read is separate from the notebook's older market snapshot. The public RPC could no longer serve the older state for these additional getter calls; no fresh market balances were substituted into the analysis. Raw calls are in [branch-cap-evidence.json](branch-cap-evidence.json).

At the notebook snapshot, 999 active Charters held 1,099 branches. For that fixed cohort, with no retirements or new Charters, capacity is `999 × 10 = 9,990`, leaving **8,891 slots**. Filling them at 100/day requires **89 additional auction days**, even with sufficient demand. The total ceiling does not imply a 48-hour cliff.

This is not a permanent global or lifetime license cap. New Charter auctions can be enabled. Partial branch retirement can reopen slots in a surviving Charter; retiring its final branch destroys that Charter's capacity. Daily quotas are policy settings. The model must track individual eligibility and Charter survival rather than treat 9,990 as an immutable global ceiling.

## 2. Daily consumption is much smaller than headline trading flow

At the snapshot's 700,000 tokens/day issuance and 1,099 branches, gross income is **636.94 tokens per branch per day**. An illustrative next-day floor of two days' output is **1,273.89 tokens** per license. The actual already-open auction had its floor frozen earlier at 1,400; the next-day example is not a current executable offer.

At 100 licenses/day, this illustrative floor consumes **127,388.54 tokens/day**, or **18.2%** of base issuance. If all were funded by newly purchasing tokens, that is approximately **24.28 ETH/day** at the snapshot marginal price after buy fees, or 24.41 ETH if executed in one purchase with impact. If 25% is funded externally and the rest from ledger earnings, the marginal fresh-buy requirement is about **6.07 ETH/day**.

Observed pool buys ran at approximately **272 ETH/hour** across the two-hour window. Floor-priced immediate branch consumption alone cannot explain that buying rate. This is a scale comparison, not a claim that observed gross trading volume equals net fresh investment or that we know each buyer's motive.

The 100/day cap does **not** cap pool purchases at 24 ETH/day:

- Auction premiums can make each license much more expensive.
- Owners can buy inventory now for future auctions.
- Speculators can buy without owning any Charter.
- Trading can recycle capital into repeated gross purchases.
- New Charter or license-supply policy can change future demand.

However, tokens purchased in advance reduce the need to purchase them again later. Ledger-funded expansion consumes internal claims without bringing the same fresh ETH into the market. Consumption, gross trading volume and net new capital must be modeled separately.

As an illustration, filling the entire remaining fixed-cohort capacity at each day's two-day-output floor, with constant issuance and no retirements/new Charters/recycling, costs approximately **3.15 million tokens over 89 days**. That is about 582 ETH marked at the snapshot spot price, not an executable multi-month cash quote. It is not a maximum spending bound: auction premiums can increase it, while reinvestment reduces the externally funded portion.

## 3. More branches divide the same income

For fixed system issuance I, an owner with n branches among N earns `I × n/N`.

Opening one extra branch changes that income by:

`I × [(n+1)/(N+1) − n/N] = I × (N−n)/(N(N+1))`.

That marginal income includes dilution of the owner's original branches. Later purchases by everyone else dilute it further.

Consider an illustrative 1,000 equal owners. With one branch each and 700,000/day issuance, each receives 700/day. If all expand to ten branches, each still receives 700/day, but everyone has paid for nine licenses. Expanding early can improve one owner's share; matching everyone's expansion does not increase collective issuance. Competition can spend much of the value owners are trying to capture.

This does not make every branch purchase irrational. It makes the relevant question **what incremental cash the branch will generate after everyone else's response**. Refusing to expand can also be costly if others acquire most of the earning share cheaply.

## 4. A rational buyer values cash, not the displayed token yield

Let V denote the best expected discounted net ETH obtainable from a position, accounting for future purchases, dilution, retirement, fees, pool impact and other actors' behavior.

An externally funded license is attractive only if:

`incremental V from buying the branch ≥ ETH cost of acquiring its license tokens`.

Internal reinvestment has a different comparison:

`V(n+1 branches, balance−license cost) ≥ V(n branches, balance)`.

Ledger earnings are not free capital: they have a withdrawal opportunity cost. The internal option may avoid a buy tax but still sacrifices an existing claim.

The next implied opening price is **23,776.68 tokens**, or **37.3 days of today's gross one-branch output**. A rational buyer must allow for later dilution, retirement fees, market-sale impact and price changes. The auction can still sell at that price if buyers expect enough future value or fear losing scarce allocation; rationality alone does not establish whether that expectation is right.

If willingness to pay is below the auction price, rational buyers wait or do not buy. A falling auction price improves prospective returns and can restore demand. This is an endogenous adjustment that a fixed demand-decay curve does not capture.

A higher token price also raises the ETH value of both branch earnings and a license priced in tokens. It does not automatically improve the return on a new license. Improved expected future/current price, cheaper license pricing, better future issuance share, or a different opportunity cost is needed.

## 5. Why delaying ETH Charter auctions can be sensible

Keeping them disabled protects existing owners from the new Charters' initial branches and subsequent expansion. It preserves scarce access and avoids introducing another participation sale immediately.

There are costs: only existing Charter owners can buy licenses, so the direct branch-buyer population remains constrained. Anyone else can trade the token, but has no native branch-income access. The protocol also forgoes Charter-auction ETH while the auction is closed.

Opening the auction later would bring in ETH and recruit future license buyers, while diluting incumbents. The new Charter's initial branch is obtained through the ETH auction rather than a STANDARD purchase. Auction ETH enters the protocol fee engine; it is not all an immediate STANDARD market buy. Reserve accumulation, liquidity additions, team allocation and buybacks have different effects.

Delaying entry can therefore protect incumbent economics. It is not unambiguously optimal for the token price or proof of a durable feedback loop. A rational prospective Charter buyer must also price dilution from future Charters and branch expansion into their ETH bid.

## 6. What can rationality actually establish?

A self-supporting participation loop needs enough **external demand or willingness to hold existing claims** to absorb the desired cash exits. Burning tokens or internal ledger claims changes who owns the remaining claims; it does not independently manufacture ETH. Existing pool ETH can fund some exits without new buyers, but extracting it changes the pool price. Locked liquidity is still assumed safe and remains subject to ordinary swaps.

The useful stress condition is:

`fresh speculative + externally funded branch buying + executed protocol buying < desired token sales`.

Both sides depend on price, expectations, auction terms, balances and future actions. Prices can clear by making licenses cheaper, discouraging sellers, inducing reinvestment, or changing expectations. Aggregate investors cannot all extract more ETH than the initial accessible ETH plus later net contributions, after leakage such as team fees and gas; individual actors can still rationally compete for those finite proceeds.

The rational-actor analysis supports **limited direct branch-consumption demand and competition for a shared issuance stream**. It does not identify a unique equilibrium or an inevitable top date. A better simulation must make license bids, funding source, speculation, and retirement decisions respond to expected incremental value and test whether those expectations are consistent with the resulting flows.

Primary mechanism description: [official whitepaper](https://www.standardreserve.xyz/whitepaper/). Economic deductions and hypothetical cases above are our analysis, not project claims.
