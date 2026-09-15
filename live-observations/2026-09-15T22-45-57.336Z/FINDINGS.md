# Recovery update observation

Pinned at **2026-09-15 22:45:58 UTC**, block **64,018,215**. See the [updated research assessment](../../RECOVERY_FINDINGS.md) and [executed notebook](../../recovery_update.ipynb).

`summary.json` contains flow windows derived from verified block headers. `recovery-liquidity.json` contains all 77 initialized ticks; `recovery-protocol-positions.json` rechecks the two known protocol positions. `support-state.json` and `recovery-auctions.json` record the same-block support and auction settings. Their raw calls are in `recovery-rpc-*.json`. All observations are public and read-only. This is a rechecked L2 pin, not an L1-finality claim.
