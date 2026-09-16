# Market update — September 16, 2026, 10:08:30 UTC

**The recovery is continuing, supported by buying into other recipient addresses while the previous major buyers and watched sellers retain their tokens.** This strengthens the case for near-term continuation relative to the prior concentrated burst. It does not establish how long buying persists or identify beneficial owners.

| Observation | Updated value |
|---|---:|
| STANDARD spot | **0.0001177752 ETH** |
| Change from 09:11:08 UTC | **+3.60%** |
| Buying since 09:11 | **76.46 ETH** |
| Selling since 09:11 | **13.71 ETH** |
| Last 20 minutes buying / selling | **50.30 / 1.86 ETH** |
| Last 5 minutes buying / selling | **18.32 / 0.37 ETH** |
| Buyback vault | **111.72 ETH; no execution (`lastTickAt=0`)** |
| Total branches / remaining daily licenses | **1,199 / zero** |

Amounts are canonical pool-side ETH, not wallet expenditure including all hook taxes/router charges. Window cutoffs use interpolated block times.

## The wallets we were watching

The three buyers investigated at 09:23 have **identical token and ETH balances** at this snapshot, with no intervening STANDARD transfers:

| Address | STANDARD | ETH |
|---|---:|---:|
| `0x47d579fe2962cca1f2936b30be1981eae391b1fe` | 704,874 | 1.9399 |
| `0x456408c79e4bed7c58d04098438971255bfa98f0` | 543,165 | 0.5015 |
| `0x451e9a00df8d6863a9aa9b1bb2eb6e1202ef76d6` | 75,639 | 0 |

Their checked WETH/USDG balances also remain zero. They have not provided the subsequent bid or sold into it. The buying has moved to other addresses; these need not be new investors or newly introduced capital.

The large watched sellers `0x5638484ba2d2f1d1d35020572b0aa439a9869192` and `0x8224c04a8f66557df682fd0581eb3724bd2bee07` still hold **764,635** and **862,798 STANDARD** respectively, unchanged from 09:11. All 18 previously watched seller/rebound addresses have unchanged ending token balances. This is a selected watchlist, not a statement that nobody is selling.

## Where the current flow is concentrated

In the last 20 minutes, the largest attributed token recipient is `0x27d25ebe6637e4b173ec7d0546cd54d1b74828e0`, accounting for **20.26 ETH** of canonical buying. The three largest identified recipients together account for **36.32 ETH**, or **72.2%** of the 50.30 ETH total. Recipient attribution covers **92.9%** of buying volume. This is less concentrated than the earlier 90.8% top-three window, but remains concentrated and cannot establish independent ownership.

The largest attributed seller in the last hour is `0xefa988eabbb2b768ab95ce5a194a910b0050f377`, with **11.24 ETH** of canonical selling. Most of the last-hour selling predates the latest 20-minute buying burst. See the [transaction table](trades.csv.gz) for amounts, order and approximate UTC times.

## Decision implications

The previous three buyers' small cash balances did not stop the market: replacement buying arrived. Their retention plus the pause by watched large sellers improves the observed flow balance. Buybacks and currently available daily licenses do not explain this update: buybacks remain inactive and the quota remains full.

The new-entry fee hurdle remains substantial. Current fees are **2% buy tax, 3% sell tax and 1% LP fee each way**, requiring approximately **7.33%** subsequent gross price appreciation for a very small canonical round trip before gas/slippage. Rebuilt current tick liquidity implies about **134.85 ETH of additional wallet buying** for an illustrative **1 ETH entry to break even**, assuming no other sellers, unchanged liquidity/taxes and no gas/router costs. This is a conditional requirement, not expected buying or an executable quote. Locked liquidity remains in place in that case.

**Assessment: more constructive on near-term continuation; no demonstrated calibrated edge for a new entry.** Neither a guaranteed top nor a guaranteed recovery is inferred. The scenario is sensitive to whether replacement demand persists and retained inventories remain off the market.

## Evidence and checks

Robinhood chain 4663; STANDARD `0x88ad8DdF1E3898412146a534538d418c6F8A9062`; block **64,425,180**; hash `0x332a21b8894a926b3fc97bcb79eccd12139f75dce6beb9a83c241f5612a22e43`.

All **21 watched token balances** reconcile against Transfer replay. Canonical buy/sell totals reconcile with saved Swap logs. Liquidity changes are replayed from the prior verified curve; active integer liquidity matches the final Swap event. No full holder census, comprehensive capital survey or branch-withdrawal-source attribution was rerun.

Reproduce offline with `python analyze_market_check.py market-checks/2026-09-16T1008`. [Summary](summary.json), [raw pinned calls and logs](tape.json), [flow windows](windows.csv), [watched wallets](watched-wallets.csv), [replayed liquidity](liquidity.json). Earlier [buyer investigation](../../buyer-investigation/FINDINGS.md) and [entry assessment](../../decision-evidence/2026-09-16T0908/FINDINGS.md) retain their own timestamps.
