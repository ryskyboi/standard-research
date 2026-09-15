# STANDARD decline: fresh observation at 2026-09-15 22:34:29 UTC

## What the evidence supports

Persistent net selling in the canonical STANDARD/ETH pool explains the observed decline mechanically. The latest window does not show a new branch-withdrawal wave or trading-tax change. Seller motives and a specific external catalyst remain unverified.

Chain 4663; token `0x88ad8DdF1E3898412146a534538d418c6F8A9062`; pool `0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9`. Pinned block **64,011,375**, hash `0xf40d5dca53e7144ff92901878026e6274854012b8996eb9fe2b048c5205bfc44`. This is a rechecked latest L2 observation, not a claim of L1 finality.

| Window, September 15 UTC | Buy input ETH | Sell output ETH | Net pool ETH from swaps | STANDARD/ETH change |
|---|---:|---:|---:|---:|
| 21:54:29–22:14:29 | 2.848 | 66.311 | -63.463 | -3.424% |
| 22:14:29–22:34:29 | 17.093 | 56.067 | -38.974 | -2.169% |
| 22:29:29–22:34:29 | 7.280 | 4.139 | +3.142 | +0.173% |

The five-minute window overlaps the last twenty-minute window; do not sum them. Prices and flows are against ETH, not USD. Buy inputs are after hook tax and include pool input fees; sell outputs are before hook output tax. These are pool swap amounts, not wallet receipts.

The price at this pin is 0.000116199912 ETH per STANDARD, approximately **22.18% below** the earlier observation at 2026-09-15 13:40:38 UTC. The last five minutes recovered slightly; this observation does not demonstrate an accelerating collapse.

Two largest sales, at 22:23:16 and 22:24:13 UTC, total 25.009 ETH and have the same transaction sender, `0xfb0d8b94027c5109ae89c5f08b025cc598cf6f49`. They account for **44.6%** of the latest twenty-minute sell output. Successful receipts and actual block headers are saved. This does not establish the sender's identity or beneficial ownership.

## Fees, branch exits and liquidity

- Current buy tax 2%, sell tax 3%, pool LP fee 1%; manual tax override false.
- No branch withdrawals, branch openings, deposits or tax changes in either twenty-minute window. Cumulative recorded gross withdrawals remain 12,072.042428 STANDARD, unchanged from the earlier observation.
- Thus the observed selling uses already transferable tokens; it is not contemporaneous minting from new branch withdrawals. Acquisition history of those tokens was not traced.
- All nonzero liquidity modifications in these forty minutes add liquidity. No negative liquidity modifications were observed in this pool. Locked protocol liquidity remains an assumption of safety, as requested. Locked liquidity does not guarantee a price: swaps can still exchange the pool's ETH for sellers' tokens.

## Why utility does not guarantee buying: economic interpretation

The daily license allowance is exhausted (`remainingToday = 0`) and total branches remain 1,099. This limits immediate new branch purchases, but buyers can still buy ahead of a future auction. It is not proof that every potential buyer has disappeared. Existing Charter owners can also fund licenses from internal earnings, so branch expansion need not produce a corresponding market purchase.

Branch earnings accrue in STANDARD. More units of STANDARD do not independently create ETH demand. A rational participant values future net proceeds after dilution, retirement costs, taxes and price impact. If expected token prices fall, buying a branch or holding speculative inventory can become less attractive; anticipated future selling can affect prices before any new rewards are withdrawn. This is a plausible incentive mechanism, not an observed statement of sellers' motives.

## Buyback support is not operating as an immediate floor

At the same pinned block:

- Contraction vault balance: **111.718994 ETH**; expansion vault: **111.718994 ETH**.
- Contraction vault `paused = false`, but `lastTickAt = 0`, indicating no successful recorded buyback tick. The contraction balance is unchanged from the earlier frozen snapshot.
- Configured tick cooldown is 3,600 seconds; vault-spend parameter 10%; effective pool-depth parameter 0.2%. These parameters do not establish that a tick is currently executable; authorization and other conditions were not simulated.
- Epoch 1 remains unsettled. Its scheduled end is **2026-09-18 01:00:30 UTC**.
- Hook epoch net flow remains **+2,538.383760 ETH**, despite the recent decline. Cumulative epoch flow and a twenty-minute price move measure different things; a falling price alone is not evidence that epoch policy has switched to contraction.

The saved `support-state.json` includes exact RPC requests and responses. No transaction was sent.

## Interpretation and limitations

The immediate explanation is existing-token selling exceeding incoming ETH demand, with concentrated larger sales and no executed buyback tick recorded. Utility demand is constrained and partly internally funded. These facts make the decline economically understandable without requiring a fresh tax shock or rewards-unlock event.

This is not proof of an exploit, proof that no exploit exists, or a forecast of the next price move. Other pools, off-chain news, holder acquisition history and seller motives are outside this focused observation. Earlier notebook peak dates are conditional scenarios, not validated forecasts; this decline does not retroactively calibrate their assumed demand paths.

## Reproduction

Use the repository's `collect_live_flow.mjs`, then `analyze_live_flow.mjs` against the resulting directory. The RPC's log timestamp fields were zero; the analyzer uses verified block headers for window boundaries and receipt times. `summary.json` contains the derived figures; `pool-events.json`, `economic-events.json`, `rpc-*.json`, `window-headers.json` and `largest-sale-receipts.json` preserve the evidence. `SHA256SUMS` hashes all other files in this directory.
