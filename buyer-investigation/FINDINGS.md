# Who supplied the latest buying, and what capital remains?

**Snapshot: September 16, 2026, 09:23:06 UTC**, Robinhood chain 4663, block **64,398,120**, hash `0x21686108317bf6c12a0630611549b61f04b45781c1e0abf763388037831fe459`.

Scope: the three largest token recipients in the 20-minute buying window ending **09:11:08 UTC**, which accounted for **90.8%** of canonical buying volume. This is a focused follow-up to the [entry assessment](../decision-evidence/2026-09-16T0908/FINDINGS.md), not a new ranking of all buyers at 09:23.

## Findings

**These addresses currently hold only 2.4414 native ETH combined, no balances in the verified WETH and USDG contracts, and 1,323,678 STANDARD.** All three retained their recent acquisitions through the snapshot. No direct team-control relationship is established. One is a Charter owner; owning a Charter establishes participation in the game, not protocol administration.

| Token recipient | STANDARD held | Native ETH | WETH | USDG | Observed role |
|---|---:|---:|---:|---:|---|
| [`0x47d579fe2962cca1f2936b30be1981eae391b1fe`](https://robinhoodchain.blockscout.com/address/0x47d579fe2962cca1f2936b30be1981eae391b1fe) | **704,874** | **1.9399** | 0 | 0 | Recent accumulator; no Charter |
| [`0x456408c79e4bed7c58d04098438971255bfa98f0`](https://robinhoodchain.blockscout.com/address/0x456408c79e4bed7c58d04098438971255bfa98f0) | **543,165** | **0.5015** | 0 | 0 | Charter #738 owner, one branch |
| [`0x451e9a00df8d6863a9aa9b1bb2eb6e1202ef76d6`](https://robinhoodchain.blockscout.com/address/0x451e9a00df8d6863a9aa9b1bb2eb6e1202ef76d6) | **75,639** | **0** | 0 | 0 | Recipient of a relayed, USDG-funded purchase |

The ETH column measures cash in these exact addresses on Robinhood Chain. It excludes other assets, other chains, exchange balances, private wallets and future funding. It is not an estimate of their owners' total wealth or a committed buying budget. The relayed purchase below is direct evidence that token recipients' ETH balances can understate the capital supporting their purchases.

## What each address did

### 1. `0x47d579…b1fe`: buys held in the wallet

The address submitted **five successful purchase transactions with 79.9 ETH of total transaction value** between the prior 06:16 tape snapshot and 09:11. It acquired **704,874 STANDARD** and retained all of it. No outgoing STANDARD transfer appears in the complete collected history through 09:23, and its balance was zero at 05:40. It owns no Charter. No bank deposit or branch funding from these purchased tokens is observed.

At 09:23 it had no deployed code and transaction nonce 5. The observed transactions account for those five outgoing transactions. Its **1.94 ETH** remaining cash is small relative to the recent 79.9 ETH submitted. The source of its earlier native ETH funding is unresolved; a fresh account is not itself evidence of team control.

### 2. `0x456408…98f0`: an existing participant adding inventory

It already held **452,278 STANDARD at 05:40**. It then submitted **11 successful purchases totaling 10.5 ETH of transaction value**—ten 1 ETH inputs and one 0.5 ETH input—and added **90,887 STANDARD**. It retained the resulting **543,165 STANDARD**. No outgoing STANDARD transfer appears in the collected token history.

Fresh calls establish that it owns **Charter #738**, which has **one branch** and approximately **844 pending STANDARD**. It also had one branch at the previous full snapshot. No expansion from the recent purchase burst is observed. Its token holdings remain available in the wallet; owning a Charter does not make all its token purchases utility spending.

Remaining cash in the checked assets: **0.5015 ETH**, no WETH or USDG. Native funding ancestry was not established.

### 3. `0x451e9a…76d6`: buying funded outside the recipient's ETH balance

The address held **4,067 STANDARD at 05:40** and received another **71,572 STANDARD** in [this purchase](https://robinhoodchain.blockscout.com/tx/0x04b8205099213c78d5d238ef9960e08fe07a268ec38bc8693e222e3f0669f756). It retained the new tokens through 09:23. Its older history includes a **32,209 STANDARD routed outflow**; that does not negate retention of this new purchase.

The successful receipt shows:

1. Transaction sender: `0xf9d33da08b05e3a78b878ebbedc50485d6e49374`, with zero native ETH transaction value.
2. Execution contract: `0x5399d94d2cab7c252a6034042e1917a0e5e17a18`.
3. That contract transfers **19,999.935843 USDG** into the execution route.
4. The route obtains and unwraps approximately **8.3546 WETH**, then buys STANDARD through the canonical pool.
5. **71,571.517734 STANDARD** is delivered to `0x451e9a…76d6`.

The receipt proves a USDG-funded routed acquisition. It does not establish the recipient's beneficial claim on the execution contract's remaining funds. A bounded USDG history also shows the submitting address replenishing that routing contract with **76,335.502126 USDG** in a separate transaction and numerous trading-related inflows from a shared route. Those amounts are **not** added to this investor's available buying budget.

The recipient's code at the snapshot is an EIP-7702 delegation indicator pointing to `0x000000009b1d0af20d8c6d0a44e162d11f9b8f00`. This establishes delegated execution capability; it does not identify an owner or prove the purchase used that delegation. The indicator format is defined by [EIP-7702](https://eips.ethereum.org/EIPS/eip-7702).

## Are they tied to the protocol?

**No direct team-control relationship is established by the checked evidence.** Specifically:

- None matches the known STANDARD protocol contracts or the current owner returned by nine successful protocol `owner()` getters: `0x5c19f925e1e0d54e34681a6cb70d55c90b12a68c`.
- None is a nonzero pending owner in the successful getter checks.
- Complete collected STANDARD histories for these addresses contain no direct transfers to or from those known protocol contracts or the current owner. Canonical pool market purchases are treated as trading, not privileged protocol funding.
- The first two buyers submit their own transactions. The third uses another submitting address and a routing contract. Shared routing does not prove common ownership or protocol affiliation.
- Charter #738 ownership is an economic participation link, not an administrative-control link.

**We cannot exclude a funding or off-chain relationship.** The public explorer's address-history endpoints returned HTTP 403; `trace_filter` and `debug_traceTransaction` are unavailable on the public RPC. Therefore native ETH funding ancestry and full internal execution could not be established. Those failures are archived and are not evidence that funding links do not exist. No personal identity is inferred.

## What this means for the flow model

The recent burst has largely converted the measured wallets' available ETH into token inventory. These three addresses' **2.44 ETH of current direct cash** is small beside the prior modeled **131 ETH of additional buying required** for a new 1 ETH entry to break even without sellers. That hurdle belongs to the 09:11 liquidity snapshot and is not a fresh 09:23 execution quote.

The right adjustment is to avoid projecting their last 20 minutes of buying forward as a constant rate. Further material buying needs replenishment, routed capital, other assets or other participants. **It is not valid to infer that these buyers are permanently exhausted:** the third purchase already demonstrates funding that did not come from the recipient's native balance. Their **1.324 million STANDARD** is now liquid inventory, but holdings alone do not establish an intention to sell.

## Evidence and reproduction

- [Pinned balances, code and protocol-owner getters](snapshot.json).
- [Per-wallet summary](wallet-summary.csv) and [analysis summary](summary.json).
- [17 successful transaction envelopes and receipts](transactions.json), with [purchase table](purchase-transactions.csv).
- [Complete collected target token transfers](target-token-history.csv) and [routed purchase's asset legs](routed-purchase-token-legs.csv).
- [Raw RPC calls and responses](raw.json), [funding checks](funding-raw.json), [explorer limitations](explorer-discovery.json), and [trace limitation](trace.json).
- [Bounded incoming USDG transfers to the routing contract](router-usdg-incoming.json). These are routing-contract flows, not a customer balance ledger.

Run `python analyze_buyers.py` from the repository root. All three token histories reconcile exactly against freshly read integer balances, all 17 purchase receipts have successful status and matching transaction/block hashes, and asset decimals are checked. The collectors use only public endpoints and do not sign or broadcast transactions. The report does not claim a comprehensive authority audit, full capital inventory or definitive identity attribution.
