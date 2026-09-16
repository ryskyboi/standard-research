# Can buying ahead of buybacks pay after fees?

**Snapshot: September 16, 2026, 02:22:37 UTC; Robinhood chain 4663, block 64,147,400.**

## Main result

The remaining inventory of attributed six-hour sellers is **2,343,124 STANDARD**. At the snapshot curve, selling all of it with no buying would receive about **218.03 ETH after modeled fees** and lower the spot price **11.47%**. The buyback vault holds **111.72 ETH**, enough to buy approximately **1.023 million STANDARD** on its own—about **44%** of that six-hour inventory. These quantities are price-dependent, not fixed redemption rates.

Buying ahead of this existing vault alone does **not** clear the modeled canonical-pool round-trip fees, even in the favorable zero-other-seller case. It requires additional buyers, extra treasury funding, lower execution costs, or a materially different entry price/liquidity state. Buying against an unexecuted balance also requires the owner actually to act.

## Remaining seller inventory

| Sellers active during trailing window | Addresses | Now empty | Tokens still held |
| --- | ---: | ---: | ---: |
| 20 minutes | 59 | 52 | 257,709 |
| 2 hours | 280 | 228 | 1,111,566 |
| 6 hours | 504 | 404 | 2,343,124 |
| 24 hours | 2,214 | 1,837 | 7,435,130 |

These groups overlap: **do not add their balances**. They are addresses with attributed canonical-pool sales, not identified people or committed future sell orders. The top five six-hour sellers by remaining inventory hold **1.327 million tokens**, 56.6% of that cohort; the top ten hold 1.751 million, 74.7%. Full addresses are in [the six-hour inventory CSV](buyback-seller-results/sellers-6h.csv).

| Address | Remaining STANDARD |
| --- | ---: |
| `0xa65ce1d604fa901c13aa29f2126a57d9032e412b` | 600,000 |
| `0xd026f7a62fad79952d2f136ebd598a71b0053da1` | 337,805 |
| `0xaae01d26a2100224f724df95fafacd1d07c13593` | 150,000 |
| `0x01f3bedb04d4090372f7b1ca0a4f0bb581faaf8f` | 137,653 |
| `0xca8ab66188924815df38cac43165ae8c220f1a4b` | 101,337 |

An address that sold a small portion may intend to keep the remainder or buy more. These balances can also change through transfers and new purchases. All STANDARD transfers since the prior individually reconciled snapshot are replayed in integer units; final total supply and fresh known-custody balances reconcile. New swap attribution covers 99.42% of the intervening canonical ETH volume. Older window attribution retains its previously disclosed coverage limits; unresolved and other-venue-only sellers may be missing.

Holder-side tokens outside identified protocol/pool/routing custody total **64.254 million**. The other **61.911 million** are outside the six-hour seller group, not necessarily inactive or safe from selling. Existing bank balances of **1.395 million** are additional internal liabilities, not yet minted into wallets.

## Buyback execution and start time

Contraction vault: [`0x796e80E8ABcedc30c700A9587F7933d3342B8946`](https://robin.etherscan.io/address/0x796e80E8ABcedc30c700A9587F7933d3342B8946).

At the same pin, the vault has never executed a buyback, `lastTickAt=0`, `paused=false`, and `executionPermissionless=false`. An owner-address read-only simulation succeeds; an ordinary caller reverts `NotExecutor`. The owner can execute under this state now. **There is no verified scheduled start time in this evidence.** The hourly cooldown is not an automatic purchase schedule. No transactions were signed or broadcast.

The first execution is limited to **6.462 ETH**, using `min(10% of vault, 0.2% of protocol pool depth)`, with a 3,600-second cooldown and a spot/TWAP check. Future execution can fail that check or change with parameters. The larger tax-hook balance is discussed in [the full buyback status](BUYBACK_STATUS.md); September 18 01:00:30 UTC is epoch settlement, not an enforced buyback start.

## What buybacks alone could do

These rows assume no opposing sellers, unchanged locked liquidity, successful hourly execution from now, ordinary buy tax, and no replenishment.

| Executions | ETH spent | Tokens bought | Spot-price increase |
| --- | ---: | ---: | ---: |
| First tick | 6.46 | 60,775 | +0.33% |
| Six ticks | 38.93 | 363,156 | +1.99% |
| 24 ticks | 100.65 | 924,534 | +5.19% |
| Entire current vault eventually | 111.72 | 1,023,383 | +5.77% |

The whole-vault row is a price-impact ceiling with respect to the current balance and zero selling, not an immediately executable trade. Protocol tax exemption is unverified; the executable scenarios also test a tax-exempt buyback sensitivity. That does not change the negative round-trip result.

## A 1 ETH entry, followed by buybacks, then an exit

User entry uses the current initialized-tick curve. Modeled fees: **2% buy tax, 3% sell tax, 1% LP fee each way**. Trades are spread hourly; existing seller inventory is finite. The user buys first and exits last, so own price impact is included. These are conditional scenarios, not expected returns or probabilities. A cheaper alternative execution route could change user costs; it has not been quoted here.

| Six-hour sellers' remaining inventory sold over 24h | Spot change before user exit | User's net round-trip return |
| --- | ---: | ---: |
| None | +5.24% | **−2.00%** |
| 25%: 585,781 tokens | +2.00% | **−5.02%** |
| 50%: 1,171,562 tokens | −1.10% | **−7.90%** |
| 100%: 2,343,124 tokens | −6.89% | **−13.29%** |

With no sellers, the six-hour round trip still loses **4.98%**. Extending to 48 hourly ticks reduces that to **1.50%**; assuming the buyback itself is tax-exempt improves it to a **1.39% loss**, before gas. The 48h case deliberately excludes possible epoch replenishment even though it crosses settlement. It isolates the current vault.

## Additional outside buying needed just to break even

For the illustrative 1 ETH entry, **on top of the modeled owner-executed buybacks**, with ordinary canonical-pool costs:

| Fraction of six-hour seller stock sold | Additional buying over 6h | Additional buying over 24h |
| --- | ---: | ---: |
| None | 102 ETH | 41 ETH |
| 25% | 165 ETH | 105 ETH |
| 50% | 228 ETH | 169 ETH |
| All | 353 ETH | 297 ETH |

Gas, router-specific fees, unmodeled venue arbitrage, additional bank exits and new sellers raise or otherwise change the hurdle. Existing ordinary buyers can supply this flow; it need not all be new investor capital. The table is a required-flow calculation, not an assumption that buying arrives.

## Decision

The current buyback reserve alone is insufficient evidence for a profitable entry through the modeled route. A stronger setup would require observed executions, declining replacement selling, and enough continuing outside buying to exceed the relevant break-even hurdle. The top remaining wallets are useful to monitor, but their inventory is not a promise to sell.

Reproduce offline with `python buyback_sellers.py`. Raw pinned requests and full tick liquidity: [buyback-seller-evidence](buyback-seller-evidence/). Scenario outputs: [buyback-seller-results](buyback-seller-results/). The locked-liquidity assumption is retained; protocol-owned reserves are not holder redemption rights.
