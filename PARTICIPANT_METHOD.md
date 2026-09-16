# Participant research: evidence, assumptions and reproduction

## Frozen observations

| Observation | UTC time | Robinhood block | Purpose |
|---|---|---:|---|
| Participant snapshot | 2026-09-16 00:44:57 | 64,089,150 | Token/ETH balances, all Charters, policy, liquidity |
| First auction checkpoint | 2026-09-16 01:09:32 | 64,103,832 | Actual first 50 license purchases and market response |
| Later auction checkpoint | 2026-09-16 01:14:41 | 64,106,912 | Actual 51 purchases, deposits, inventory funding and renewed selling |

All forecasts/stress paths retain elapsed hours/days and UTC. Later observations are not silently merged into an earlier calibration. Pair-contract identity calls in `routes.json` have their own archived later header; token and Charter balances remain at the main snapshot.

## Read-only collection

The public collectors use `https://rpc.mainnet.chain.robinhood.com`. No credential, environment file, wallet configuration, private key, signing code or transaction submission is needed or included. The notebook runs offline. A private Ethereum-mainnet RPC cannot query Robinhood-chain contracts.

- `strategy-evidence/`: complete STANDARD Transfer replay through the earlier block 64,018,215, including integer supply reconciliation. Historical account-state reads failed because this RPC pruned that state; those failed reads remain evidence, not fabricated balances.
- `strategy-current/`: incremental transfers, fresh pinned token/native-ETH reads, all 1,000 Charter IDs, full initialized ticks, policy getters, ownership history, selected transaction/header checks, route receipts, verified secondary-pool swaps and two auction observations.
- `empirical-evidence/`: full canonical-pool/economic event history through block 64,018,215 and block-header time anchors. The current participant analysis uses these raw records; it does not use the earlier experimental aggregate-flow bootstrap.
- `participant-results/manifest.json`: SHA-256 hashes of evidence and model sources. `verify_artifacts.py` checks these with the older research bundles.

Collectors use public read-only RPC. To collect a *new* snapshot, preserve or rename the old evidence directories first and change the collector output directory; the scripts are research collection scripts, not a continuously operating service. The published notebook reproduces these frozen observations rather than implicitly fetching live markets.

## Attribution and provenance

1. Replay every ERC-20 Transfer with integer token units. Check mint minus burn equals total supply, no negative address balances, and every collected `balanceOf` equals replay.
2. Group canonical swaps and transfers by transaction. Follow net token sources and terminal recipients instead of assigning the router/transaction bundler as the investor.
3. Resolve a split route when the unique token-owning source/recipient and exact canonical token leg reconcile. Count only the canonical leg's ETH. Multi-owner or multi-direction ambiguity remains unresolved; transactions without a token Transfer still count in total market activity.
4. Exclude known protocol custody, PoolManager, POL manager, two verified STANDARD pairs and one conservatively excluded repeated routing counterparty from investor cohorts. The third counterparty's precise contract role remains unresolved. Secondary-pool membership is supported by archived token0/token1 calls and receipts; matched Swap events identify acquisition legs.
5. Maintain a pro-rata acquisition mixture for each address: own/received canonical purchases, own/received secondary purchases, branch mints, genesis allocation, and other-custody/unresolved. A transfer preserves upstream economic origin but does not prove ownership linkage. Fungible tokens have no unique lot identity; another accounting convention could change an individual sale's mix.
6. ETH numbers describe canonical-pool legs. They are not full wallet cash flow or complete P&L: launch taxes, router fees, other venues, gas and external transfers can differ. Wallet acquisition through a shared custody contract is not automatically a market purchase unless matched to supporting swap evidence.
7. Exact block IDs and transaction hashes are retained. Selected timestamps have exact headers; other trade times interpolate between headers. Windows are approximate at their boundaries. Initial launch interpolation is less dense than later 15-minute anchors.

The top-seller cost example uses an address whose attributed purchases preceded the four observed disposals and whose inventory reconciles without other acquisition sources. It is a weighted **pool-side** cost comparison, not an accounting/tax-lot realized-P&L report.

## Cohorts and finite resources

Cohorts use six hours of canonical activity. Charter ownership takes precedence; non-owners are two-way traders if both buys/sells are at least 30% of the larger side, otherwise net buyers/sellers. Other addresses are inactive/unattributed. These are descriptive labels, not identified intentions, beneficial owners, team allocations or coordinated groups. Empty historical addresses remain in the count, with zero token inventory.

All live Charter owners and positive-token holders have pinned native ETH/token reads. Some earlier fully exited addresses were not in the balance collection and retain missing ETH. Native ETH is only a funding subset: wrapped ETH, stablecoins, borrowing and future inflows are not comprehensively measured. We do not infer lack of wealth or future buying ability from native-ETH absence.

The auction feasibility allocator respects ten branches per Charter, three licenses per Charter/day, 100 global licenses/day and shared inventory across a wallet's Charters. It provides a *feasible* funding allocation, not a proof of minimum cost, Nash equilibrium, optimal owner allocation or a prediction that those owners participate. Falling-price examples assume licenses remain unsold and no intervening entries when accruing hypothetical balances.

## Rational payoff calculations

A wallet holder compares executable ETH now against discounted expected executable ETH later. The joint expectation matters: `E[future quantity × future price]` generally cannot be separated into two expectations. An existing cost basis is sunk for this marginal choice.

For a Charter, future pending tokens include its issuance share, dilution and any separately assumed entry rate. Retiring branches realizes a fraction of the internal balance, pays the resolution fee, destroys the retired earning capacity, and may then incur market fees/slippage. An owner can rationally sell wallet tokens while retaining branches. Paying someone else's Charter does not create an automatic on-chain claim for the payer.

The one-day table compares full exit now versus full exit tomorrow, using actual initial pending balance and branches, the measured liquidity curve, 100 added branches/day, current 700,000-token/day issuance, and either quiet pressure or an additional one-million-token gross withdrawal pressure. This is a unilateral sensitivity; other owners' exits are not simultaneously solved. Own exit fee and slippage are included.

The 14-day stopping table compares hourly full-exit times under explicit price trajectories. It omits partial-retirement combinations, future license options, continuing-branch salvage beyond day 14 and future policy changes. Endpoint maxima are censored. The issuance/dilution assumptions are held constant for this sensitivity; actual future epochs can change them. The new-license incremental valuation also uses immediate executable wallet-inventory opportunity cost, so it is especially incomplete when waiting with those tokens has greater expected value. **Do not use it as a complete rational-allocation model or infer zero auction demand from negative values.** The actual 51 purchases are evidence that some owners value branches beyond these restrictions.

## Conditional path construction

The six-hour paths are inventory-conditioned stress tests, not a fitted predictive model:

- Recent sellers sell `remaining × past_sold/(past_sold + remaining)` over six equal hourly steps. This is a visible survival approximation, not a calibrated sale probability.
- Replacement sellers supply the last six hours' first-sale volume, with scenarios at zero, one or two times that volume. Their tokens are capped by measured inactive/unattributed inventory. This does not estimate every inactive owner's intent or include all possible recent-buyer strategy changes.
- New-address buying capacity uses measured first-buy flows per hour over the last six or two hours. Sustaining that arrival rate is a scenario condition, not committed capital.
- Returning-address capacity is the sum of the lesser of observed native ETH and prior six-hour buying expenditure. Missing balances add no assumed spending capacity. Unmeasured ERC-20 funding makes this incomplete.
- Purchases face an explicit reservation-price gate based on the median recent all-in canonical acquisition price. That is an assumed lower-bound point for beliefs, not identification of expected resale prices from transactions.
- Sells precede buys each hour. The curve crosses initialized ticks and charges current protocol/LP fees. Different ordering can change execution because fees and concentrated liquidity matter. ETH and token conservation are checked at each step.
- No automatic vault buys, bank exits, license-specific purchases or LP removal are inserted. These omitted flows are assessed separately. These paths **do not incorporate the later auction observations**, do not supply probabilities and have no out-of-sample validation.

Thus the model identifies sensitivities and resource constraints, not a unique rational equilibrium, most-likely top or optimal personal exit. Historical aggregate-flow bootstrapping is not used as a substitute for this participant analysis.

## Actual auction funding

The later checkpoint starts from pinned wallet inventories. Sequential transfer replay tracks old inventory, post-snapshot canonical-pool acquisitions and other custody acquisitions into actual deposit burns. The branch ledger then starts from each actual pending balance, accrues issuance, adds deposits and subtracts license costs. Each source is allocated pro rata.

Per-action timestamps are interpolated for issuance allocation. Total elapsed issuance uses exact endpoint times; total pending, issuance, deposits, license costs and final branches reconcile to pinned state. Source composition is approximate and convention-dependent; it is not proof of which individual token funded a specific branch. The table distinguishes deposit funding from tokens actually spent on licenses. These observations are a later check, never represented as evidence the earlier paths correctly predicted the auction.

Actual license sale prices match `floor + (open-floor) × 2^(-elapsed/4h)`. The whitepaper's displayed formula differs; archived sales at +34 and +220 seconds select the gap-half-life implementation exactly. Opening/day-floor assumptions follow the pinned getters. ETH Charters remained disabled at the participant snapshot.

## Reproduce

```bash
python -m pip install -r requirements.txt
python run_notebook.py participant_analysis.ipynb
python -m unittest discover -s . -p 'test_*.py' -v
python verify_artifacts.py
```

To regenerate the notebook structure, edit `build_participant_notebook.py` and run it; this overwrites manual notebook-cell edits. Normal readers should edit and execute the notebook itself. Source modules and raw evidence remain separate from generated figures, CSVs and findings.
