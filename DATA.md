# Evidence and reproduction

## Data layout

- `notebook-evidence/`: current pinned public observation. Derived tables and raw RPC request/response files are included. `home.json` is the saved official application snapshot used to identify contracts and the pin; contract reads independently check the identity and state.
- `evidence/`: a smaller, older frozen observation at block 63,559,829, retained only for regression tests. It is not mixed into the current notebook's market state.
- `notebook-results/`: generated CSVs, figures, timing summary, and machine-readable inputs/results.
- `evidence-manifest.json`: SHA-256 hashes of published evidence files, with the chain and snapshot identity.

The public bundle includes on-chain addresses, calldata, bytecode and transaction logs. Long hexadecimal strings in those files are public chain data. It contains no wallet export, environment configuration, seed phrase, or private signing key. Saved external website HTML/application bundles are omitted; ABI definitions required by the collectors are included.

The application advertises contracts commit `6da54e7956cb9adf8c49804937aa1fcd0fefb74d`. This is provenance, not proof that every deployed byte corresponds to that commit. All decoded state and event observations use the exact target and saved ABI. Failed historical reads are preserved as evidence of coverage limits, not token findings.

## Offline numerical reproduction

Follow the environment commands in [README.md](README.md). `run_notebook.py` executes every cell with a local Jupyter kernel. It makes no network requests. The published default uses:

- Seed: `20260915`, with common random seeds across scenarios.
- 200 paths per headline market scenario; 80 per branch comparison and additional wallet-size case.
- 14 days, hourly observations.
- Sensitivity heatmap: 20 paths per cell, seven-day horizon.
- Monte Carlo bootstrap: 200 resamples per scenario.

`notebook-results/notebook-results.json` records the configuration, state, scenario priors, and evidence hashes. Editing assumptions intentionally changes results. Floating-point/platform differences can change a tie between adjacent maximizing hours. Exact input evidence stays frozen.

`verify_artifacts.py` checks evidence hashes, target/pin consistency, notebook execution, saved tables, and curve/position principal reconciliation. The test suite independently covers meaningful economic and liquidity cases, including replay of five observed swaps. It is not a prediction-performance backtest or full smart-contract audit.

## Re-reading the same on-chain pin (optional)

Node 20+ and the declared `viem` dependency are only needed for the collectors:

```bash
npm ci --ignore-scripts
node collect.mjs ./notebook-evidence/
node collect_liquidity.mjs
```

These scripts use public read methods at `https://rpc.mainnet.chain.robinhood.com`, including non-persistent `eth_call`. They do not construct signers or submit transactions. The collector reuses successful cached responses, records raw requests, checks chain ID and block hash, and rejects the wrong target. Archive availability/rate limits can prevent a repeat read even when the saved observations remain usable.

Collector runs can update collection timestamps and raw evidence. Keep a copy of the published data before recollecting. The published evidence manifest will detect those byte changes. To research a new date, create a separate observation directory from a fresh official application snapshot, copy the ABI definitions, and update the liquidity collector's directory deliberately; do not silently mix pins or call the old forecast current.

## Primary sources

- [STANDARD official whitepaper](https://www.standardreserve.xyz/whitepaper/)
- [Uniswap v4 StateView implementation](https://github.com/Uniswap/v4-periphery/blob/main/src/lens/StateView.sol)
- [Uniswap concentrated liquidity](https://developers.uniswap.org/docs/get-started/concepts/liquidity-providers/concentrated-liquidity)
- [Uniswap fee concepts](https://developers.uniswap.org/docs/get-started/concepts/fees)

The behavioral scenarios and forecasts are this repository's experiments, not statements by those projects.
