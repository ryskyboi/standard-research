# STANDARD: fees and the twenty-minute decline

**Observed window: September 15, 2026, 13:20:38–13:40:38 UTC (20 minutes).** This is a new observation, separate from the notebooks' frozen 10:09:19 UTC inputs. No model was refitted.

## What happened

STANDARD/ETH fell **7.25%**, from 0.0001609792 to 0.0001493103 ETH per token.

| Pool swap measure | Previous 20 minutes: 13:00:38–13:20:38 UTC | Latest 20 minutes: 13:20:38–13:40:38 UTC |
| --- | ---: | ---: |
| ETH paid into buy swaps | 14.95 | 6.79 |
| ETH taken out by sell swaps | 244.06 | 157.39 |
| Net swap ETH | −229.11 | −150.60 |
| Buy / sell swap counts | 41 / 191 | 88 / 705 |
| Price change against ETH | −10.27% | −7.25% |
| Branch withdrawals | 0 | 0 |
| Licenses opened | 0 | 0 |
| Trading-tax change events | 0 | 0 |

Amounts are PoolManager Swap event deltas: buy ETH is after the hook buy tax and includes the input LP fee; sale ETH is before output sell tax. They are not wallet totals or USD volume. Swap count is not unique participant count. Starting prices use the last pool Swap at or before each verified boundary block.

Selling outweighed buying by about **23 to 1 in ETH volume** in the latest window. Buy volume was about **55% lower** than the preceding 20 minutes. Sell volume also declined, but remained much larger than buying. This is sufficient to explain the direction of the price movement through the pool.

The four largest individual sell swaps accounted for **56.73 ETH, approximately 36% of sell volume**. Two transaction senders submitted those four trades; this does not identify their beneficial owners or motives. The largest two were at **13:27:13 UTC** and **13:28:28 UTC**:

- [100,000 STANDARD sell swap, 15.48 ETH gross pool output](https://robinhoodchain.blockscout.com/tx/0xc3be987595c9beb13c4b7406ee8c090c3e701f998c91fa3e44bef86fcb5147ed)
- [120,661.65 STANDARD sell swap, 18.50 ETH gross pool output](https://robinhoodchain.blockscout.com/tx/0x2ede3a8053464803637a3f1f8cfa341ef6b3c6be8208cebef09309097b280c60)

No branch withdrawal, revocation or epoch-settlement event occurred in the latest window. No branch licenses opened. These observations do not support a new branch-reward cash-out wave as the cause of this particular decline. They do not identify how sellers originally acquired their circulating tokens.

LP changes also occurred. Range arithmetic estimates only **0.036 ETH of removed principal**, versus roughly **0.376 ETH added**, a net addition near **0.340 ETH**. A larger STANDARD-only removal was outside the active range. Uncollected LP fees are excluded from these principal estimates. The observed principal removals do not explain the approximately 150.6 ETH net swap outflow. Locked protocol LP continues to be treated as safe; this focused observation is not a new custody audit.

The latest approximately five minutes (**13:35:39–13:40:38 UTC**, 299 seconds) were down only **0.30%**, with 1.66 ETH of buys versus 7.49 ETH of sells. That is a weaker decline inside this window, not a prediction of a recovery.

## How fees are determined

At block **63,700,425**, the getters showed:

| Fee | Current setting | Determination |
| --- | --- | --- |
| Buy hook tax | 2% | Current protocol setting; launch decay already finished |
| Sell hook tax | 3% | Current protocol setting; no tax override active |
| Pool LP fee | 1% of swap input | Pool fee, separate from hook tax |
| Branch resolution fee | About 2.0099% for a 1,000-token gross withdrawal | Computed from the trailing withdrawal window and the proposed withdrawal |

The [official whitepaper](https://www.standardreserve.xyz/whitepaper/) describes the automatic 2–60% resolution curve and the admin's ability to change trading-tax settings up to the 10% manual cap. The current cap and fee-window length are independently read in `state.json`. A falling token price does not itself increase this resolution fee.

For pre-withdrawal pending claims D, prior withdrawals W, and proposed gross withdrawal G:

`pressure = (W + G) / max(D + W, 10,000,000)`

`fee = 0.02 + 0.58 × min(pressure / 0.10, 1)²`.

The current fee window is seven days. Approximate fees are 2% at negligible pressure, 7.22% at 3% pressure, 16.5% at 5%, and 60% at or above 10%. The proposed withdrawal counts, so a sufficiently large exit can pay a much higher fee than a small exit in the same state. Half the resolution fee is removed permanently; half is recycled to remaining branches. LP fees and hook taxes are separate from that fee.

## Evidence and limits

- Chain 4663, STANDARD `0x88ad8DdF1E3898412146a534538d418c6F8A9062`.
- Pool `0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9`.
- Latest L2 pin at block 63,700,425; full header and raw requests retained, and the pin hash rechecked after collection. No L1-finality claim.
- **The RPC returned `blockTimestamp: 0x0` in logs. Those timestamps were rejected.** Actual block headers determine the windows; largest-sale receipts and block hashes were checked. The five-minute start header is one second later than the ideal cutoff, hence 299 seconds.
- Scope is the canonical STANDARD/ETH pool and the identified bank/hook contracts. ETH/USD changes, other markets, private information and seller motives are not established.
- Pool flow is observed. The reason participants chose to sell or reduced buying is not proven by these events.

See [machine-readable summary](summary.json), [liquidity estimates](liquidity-change-estimates.json), raw RPC files, and the hashes in `manifest.json`.
