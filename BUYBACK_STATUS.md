# Liquid supply and buyback status

Observed **2026-09-16T02:22:37.000Z**, Robinhood chain 4663, block **64147400**.

## Liquid STANDARD

| Category | Tokens |
| --- | ---: |
| Outside identified protocol, pool and routing custody | 64,253,903.59 |
| Canonical PoolManager balance | 31,957,501.48 |
| Other identified custody | 680,978.38 |
| Total minted supply | 96,892,383.45 |
| Additional internal bank ledger, not yet minted | 1,395,027.42 |

Holder-side inventory is an estimate of immediately available market supply, not a claim that every address is an unlocked personal wallet or intends to sell. Unidentified contracts may have restrictions. The accounting excludes the same known custody set as the previous participant analysis. Pool balances can be bought; they are not additional tokens already held by potential sellers. Internal ledger tokens require a branch withdrawal and incur resolution fees before reaching wallets.

## Buyback address

**Contraction vault:** [`0x796e80E8ABcedc30c700A9587F7933d3342B8946`](https://robin.etherscan.io/address/0x796e80E8ABcedc30c700A9587F7933d3342B8946)

Owner/executor address tested: [`0x5c19F925E1e0D54E34681A6CB70d55c90b12A68c`](https://robin.etherscan.io/address/0x5c19F925E1e0D54E34681A6CB70d55c90b12A68c).

- Vault balance: **111.71899 ETH**.
- `paused=false`, `lastTickAt=0`, `executionPermissionless=false`.
- No buyback events in the full prior history or the increment through this block.
- Ordinary synthetic caller: read-only `eth_call` reverts `NotExecutor`.
- Owner-address counterfactual: read-only `eth_call` succeeds at this block. No transactions signed or broadcast.
- Current spend bound: `min(10% of vault, 0.2% of protocol depth)` = **6.46168 ETH**.
- Cooldown: **3,600 seconds** between executions. Price/TWAP bound also applies; later calls may fail it.

**The owner can execute under the observed state now. There is no verified scheduled start time in this evidence.** Successful simulation is not a promise of execution. The hourly cooldown is a rate limit, not an automated hourly purchase schedule. Buying burns the acquired STANDARD under the documented mechanism.

## Other ETH and future replenishment

| Location | Native ETH | Role |
| --- | ---: | --- |
| Tax hook | 2,348.49477 | Awaiting fee routing; not currently in buyback vault |
| POL manager | 335.15698 | Separate liquidity mechanism; documented half-swap/half-pair |
| Expansion vault | 111.71899 | Reserve-asset purchases, not direct STANDARD buyback commitment |
| Fee splitter | 0 | No additional balance |

The first epoch ends **2026-09-18 01:00:30 UTC**. This is **not** an enforced buyback start date. Current epoch net flow remains **+2,314.08 ETH**.

Under the documented current 70%/15%/15% split, the hook balance would route about **1,643.95 ETH** to the active vault, and **352.27 ETH each** to POL and the team. If the epoch ends positive, the 70% goes to expansion; if non-positive, contraction. These are alternatives for the same money. Settlement must occur, parameters can change, and the balance will change before then. The existing 111.72 ETH does not need to await this replenishment to be executable.

Fresh raw public requests, responses and exact header: [snapshot](buyback-updates/2026-09-16T02-22-37.000Z.json). Prior full vault history and fee-ledger reconciliation: [re-entry findings](REENTRY_FINDINGS.md). The prior 2,344.24 ETH fee balance was reconciled exactly; this fresh balance is a state read, not a replay of the additional fee events.
