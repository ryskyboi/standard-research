"""Build a public, offline notebook and companion findings from frozen evidence."""
from pathlib import Path
import json
import pandas as pd
import nbformat as nb
from participant_flows import ROOT,read

def table(df,formats=None):
    x=df.copy()
    for name,f in (formats or {}).items():x[name]=x[name].map(f)
    return '| '+' | '.join(x.columns)+' |\n| '+' | '.join(['---']*len(x.columns))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in x.itertuples(index=False,name=None))

def run(root=ROOT):
    out=root/'reentry-results';m=read(out/'summary.json');fund=read(out/'funding/followup-summary.json')
    hurdles=pd.read_csv(out/'price-hurdles.csv');cases=pd.read_csv(out/'six-hour-cases.csv');capital=pd.read_csv(out/'capital-by-cohort.csv')
    paid_old=fund['license_paid_from_prior_bank_balance']+fund['license_paid_from_prefunded_wallet_tokens']
    fraction=paid_old/fund['license_cost_tokens']
    lic=pd.read_csv(out/'funding/followup-licenses.csv');charters=pd.read_csv(out/'participants/charters.csv').set_index('charter_id')
    license_owners=charters.loc[lic.charter_id,'owner'].nunique()
    report=f'''# Re-entry, buybacks and remaining demand

**Pinned observation: {m['snapshot_utc']}; Robinhood chain 4663, block {m['block']}.**
STANDARD `0x88ad8DdF1E3898412146a534538d418c6F8A9062`.
This supplements earlier research; it does not turn an earlier forecast into a successful prediction.

## Decision from cash

The observed regime favors **waiting for evidence of renewed buying** over automatically buying back after a fall. A rebound is quite possible: most recent selling addresses have emptied, and a relatively small number of large buyers can move this pool. But neither new branches nor the existing buyback reserve guarantees enough buying for a sustained recovery. There is no statistically defensible probability of recovery, or validated optimal re-entry time, from this short launch history.

The useful result is a set of capital requirements and observable decision rules. Since the wallet tokens have already been sold, the previous sale price is not an input to whether the next purchase has positive expected value. Existing Charter ownership, if any, is a separate decision.

## 1. Immediate and delayed support

| Source | Observed ETH | What can actually support STANDARD |
| --- | ---: | --- |
| Contraction/buyback vault | {m['current_buyback_ETH']:,.2f} | Privileged execution currently required. No `BuybackExecuted` events anywhere through the pin; `lastTickAt=0`. |
| POL manager idle native balance | {m['pol_idle_ETH']:,.2f} | Documented mechanism swaps half to STANDARD and pairs the rest. A 167.58 ETH swap is a conditional illustration, not a verified executable quote. |
| Tax hook | {m['hook_balance_ETH']:,.2f} | Awaiting routing; not available inside the buyback vault now. Destination depends on the epoch signal. |
| Expansion vault | {m['expansion_vault_ETH']:,.2f} | Intended reserve-asset purchases, not a STANDARD buyback commitment. |
| Fee splitter | 0.00 | No extra cash to add to the totals. |

Read-only execution tests at the pin: an ordinary synthetic caller reverted `NotExecutor`; an owner-address counterfactual `eth_call` succeeded. No transaction was signed or broadcast. Success does not establish that the owner will execute. `executionPermissionless=false`, `paused=false`, cooldown 3,600 seconds. The observed spot/TWAP check permitted the owner simulation at this block; future checks can fail.

The first buyback is bounded by `min(10% of vault, 0.2% of protocol pool depth)` = **{m['current_tick_ETH']:.3f} ETH**. Protocol depth is {m['protocol_buyback_depth_ETH']:,.2f} ETH; this is different from both actual pool ETH and total active virtual ETH.

With no competing sellers, no replenishment, unchanged settings and successful hourly execution:

| Execution | Approximate ETH spent | Price effect |
| --- | ---: | ---: |
| First tick | 6.59 | +0.32% to +0.33% |
| First six ticks | 39.72 | +1.95% to +1.99% |
| First 24 ticks | 100.82 | +5.11% to +5.23% |
| Entire current balance, eventually | 111.72 | about +5.7% to +5.9% |

Ranges bracket ordinary buy tax versus a tax-exempt protocol purchase; protocol exemption is not established here. Future protocol depth is approximated as proportional to square-root price. TWAP interruptions are ignored in these support cases, so they are execution upper cases, not scheduled buying forecasts. Tick counts cover half-open hourly intervals beginning at the snapshot.

The hook balance reconciles exactly in wei: **2,343.03805097 ETH of trade taxes + 1.20454546 ETH of LP taxes − 0 forwarded = 2,344.24259643 ETH**. The event collection covers trading launch through the pin, with 50,433 trade-tax events and 139 LP-tax events. This is observed fee money, not merely an unexplained native balance.

### The much larger delayed treasury branch

The documented/current fee shares are 70% active vault, 15% POL and 15% team. If the hook's existing {m['hook_balance_ETH']:,.2f} ETH is forwarded and routed at those shares, that is **1,640.97 ETH to a vault**, **351.64 ETH to POL**, and **351.64 ETH to the team**. These are alternative destinations of the same money, not additive buyback balances.

The first epoch ends **{m['epoch_end_utc']}**. Its current cumulative net flow is **+{m['epoch_net_flow_ETH']:,.2f} ETH**, despite the recent sell-off. If it ends positive under the documented rule, the 70% goes to **expansion/reserve assets**, not contraction buybacks. At zero or negative flow it goes to the contraction vault. Crossing the boundary requires at least another {m['epoch_net_flow_ETH']:,.2f} ETH of net negative measured flow; it is not a price threshold and the starting value changes with trades. Epoch settlement/execution must also occur.

Even a funded contraction vault remains rate-limited: at today's protocol depth the pool-side limit is roughly **158 ETH per 24 ticks**, assuming a flat price and a sufficiently funded vault. A large balance is therefore a longer reserve of buying power, not an instantaneous wall. POL deployment may help through its swap and later depth; the exact deployment path and permissions were not simulated, so its full balance is excluded from the six-hour scenario bids. Existing locked liquidity is assumed to stay locked throughout.

## 2. What participants are actually doing

| Window ending 2026-09-16 01:47:19 UTC | Pool buys | Pool sells | Net |
| --- | ---: | ---: | ---: |
| Last 20 minutes | 1.91 ETH | 141.74 ETH | −139.83 ETH |
| Last 2 hours | 311.88 ETH | 644.49 ETH | −332.60 ETH |
| Last 6 hours | 575.23 ETH | 909.44 ETH | −334.21 ETH |

Window membership uses interpolated block times; exact transaction and block IDs are retained. These are canonical-pool amounts, after the buy hook accounting and before the sell output tax, not full wallet cash flows. Six-hour attribution covers 98.81% of buys and 97.63% of sells; the latest 20-minute sell attribution is lower, 85.97%, so no unsupported identity is assigned to the remainder.

Of **{m['recent_seller_addresses']}** addresses that sold in six hours, **{m['recent_sellers_empty']}** are now empty. Their combined remaining inventory is **{m['recent_seller_inventory']/1e6:.3f} million tokens**. That supports a seller-exhaustion rebound if buyers return. But inactive/unattributed addresses still hold **{m['inactive_inventory']/1e6:.3f} million tokens**: a new group can replace those sellers. This is why counting empty wallets alone is insufficient.

About **88.15% of attributed six-hour sold tokens** trace to direct or transferred purchases from the canonical or two verified secondary pools. **Zero** trace to branch withdrawals in that window; 11.85% remains other-custody/unresolved under the pro-rata convention. Charter owners did sell 86.60 ETH of tokens, but being an owner does not make those tokens branch rewards. The largest attributed seller, `0x14b33822c8bc5689e4130b0d3fca676674fb6718`, has now emptied its wallet after 114.51 ETH of six-hour pool sales. Detailed addresses and source mixtures are in the participant CSVs.

Freshly measured capital, grouped by observed strategy:

{table(capital[['cohort','tokens','native_ETH','WETH','USDG']],{c:lambda x:f'{x:,.0f}' for c in ['tokens','native_ETH','WETH','USDG']})}

These balances are **capacity, not willingness**. Native ETH, WETH and USDG are distinct assets; USDG is not converted into ETH using an invented exchange rate. Known protocol and repeated routing custody is excluded. Some inactive empty historical addresses lack cash reads; totals are observed lower bounds, not a complete inventory of all capital. Addresses are not people and may share an owner. External new money has no fixed observable cap.

129 addresses first bought through the canonical pool during the last six hours. Their mean total pool purchase was 1.38 ETH, but the median was only 0.0913 ETH. One whale can replace hundreds of small addresses; a price target cannot honestly be translated into a required number of people without specifying ticket size.

## 3. Branches: counts, mandatory buying and waiting incentives

- **999 live Charters, 941 owner addresses, 1,151 branches.** One Charter and one branch have dissolved/retired in the collected lifetime. Only one withdrawal: 12,072.04 gross tokens, 11,829.58 net. There were no additional withdrawals in the new observation interval.
- Today's license quota: **52 bought, 48 remaining**. Those 52 licenses were bought by **{license_owners} owner addresses**, consuming **1,231,228.93 internal tokens**.
- Approximately **{fraction:.1%}** of their actual license payments came from bank balances or wallet inventory already present at 00:44:57 UTC. **99,404 tokens (8.1%)** trace to newly acquired canonical-pool tokens; the rest is new issuance or other custody. This is pro-rata source accounting, not a statement about intent.
- License-buying addresses themselves bought only **23.43 ETH** and sold **2.99 ETH** through the canonical pool during the interval. Do not attribute the entire auction-time rebound to them.
- At the pin, **14 Charters** could independently fund one license from their ledger; **101** could fund one from ledger plus their owner's tokens. Shared wallet balances cannot be counted repeatedly.
- A constructive allocation fills **all 48 remaining licenses with zero fresh market buying**: about 513,053 ledger tokens plus 501,393 wallet tokens. It respects the 3-per-Charter daily limit, already-used slots, the 10-branch maximum, and shared owner inventories.
- Capacity alone permits 48 licenses to be bought by as few as **7 current owner addresses**, spread across eligible Charters. At most 48 distinct purchasers are needed if each buys one; **zero new entrants are required**. These are capacity bounds, not a prediction of who will buy or a claim those seven can use the zero-cash allocation.
- If every remaining license were funded entirely through fresh purchases immediately, it would require **1.014 million tokens / 115.28 ETH**, lifting price about **5.95%** with no sellers. This is an extreme all-fresh funding case; the observed funding mix is much less supportive.

The daily auction resets at **{m['next_license_reset_utc']}**, not UTC midnight. ETH Charter issuance remains disabled (0/day). With the current Charters, eventual capacity is 9,990 branches, but the 100/day quota governs expansion speed. Existing owners can fill it; 8,839 unused branch slots do not imply 8,839 new investors.

### Why a rational owner may stop buying now

The current license costs **21,134 tokens** and adds about **608 tokens/day initially**. Four hours of waiting reduces its quoted price to roughly **11,204 tokens**, while foregoing only **101 tokens of issuance**, if stock remains and policy is unchanged. The rational reason to pay early is fear of sell-out or a sufficiently valuable longer-lived branch, not the next four hours of rewards. A nearly exhausted quota changes that trade-off; it does not remove it.

Gross token payback at a constant issuance rate is about **35 days with no further expansion**, **81 days with 50 new branches/day**, and **174 days with 100/day until the current Charter capacity fills**. These already exclude fees and token depreciation. Falling token price, future issuance cuts and resolution fees worsen payback. A favorable branch purchase therefore needs a belief about future executable ETH proceeds, not just a high displayed token yield. Internal reinvestment has an opportunity cost too: those ledger tokens could otherwise be harvested by retiring branches.

Funding someone else's Charter confers no automatic ownership or withdrawal entitlement in the modeled contracts. It is a transfer to that owner's position unless a separate enforceable agreement or contract exists; no such agreement is assumed.

## 4. How much buying is needed for recovery?

Price is **{m['price_ETH']:.9f} ETH/STANDARD**. The initialized-tick curve contains about **{m['actual_pool_ETH']:,.2f} ETH of principal**, versus {m['active_virtual_ETH']:,.2f} active virtual ETH. All calculations cross actual initialized liquidity ranges; no constant-liquidity approximation is substituted.

| Target from snapshot | No further sells | After 1m tokens sell | After 3m tokens sell |
| --- | ---: | ---: | ---: |
| +5% | 99 ETH | 205 ETH | 402 ETH |
| +10% | 184 ETH | 290 ETH | 487 ETH |
| +25% | 428 ETH | 535 ETH | 732 ETH |
| +50% | 795 ETH | 902 ETH | 1,099 ETH |
| Previous observed post-tax peak (+79.1%) | 1,187 ETH | 1,294 ETH | 1,491 ETH |

Amounts are gross buyer ETH including modeled 2% buy tax and 1% LP fee, excluding gas/router-specific fees. Sale-first order is explicit; interleaved trades differ. A +25% no-sell move is equivalent to 429 one-ETH buyers or 43 ten-ETH buyers, but one sufficiently large address can fund it. Dollar returns also depend on ETH/USD.

## 5. Conditional paths, not invented probabilities

All following paths run **six hours to 2026-09-16 07:47:19 UTC**. They use finite observed inventories, not infinite repeated sales by wallets that have already emptied. Buys and sells are spread over 15-minute steps; license-related trades are included in ordinary buying and never added a second time. No new bank withdrawals, liquidity changes or post-buy reselling is assumed in this short horizon. Stock sold and buyer participation are explicit assumptions.

| Case | Ordinary buying | Wallet tokens sold | Buybacks | Modeled price change |
| --- | ---: | ---: | ---: | ---: |
| Last-20-minute buying pace; sellers replenished | 35 ETH | 4.22m | 0 | −18.2% |
| Six-hour buying pace returns; same sellers | 587 ETH | 4.22m | 0 | +5.9% |
| Buying returns; seller exhaustion dominates | 587 ETH | 1.10m | 0 | +26.5% |
| Buyers return at 1.5× pace; owner executes buybacks | 880 ETH | 2.21m | 42.8 ETH | +39.0% |
| Inactive holders join the exit | 587 ETH | 9.18m | 38.1 ETH | −14.2% |

The weak case sells 75% of recent sellers' remaining tokens plus 5% of inactive inventory. The exhaustion case uses 25% and 1%; the strong-buyer case 50% and 2%; the exit-wave case 90% and 15%. These are sensitivity cases, not estimated behavioral probabilities. The latest observed window is closer to the weak-demand starting condition, while the earlier auction burst proves that renewed buying is possible. It does not justify assigning a percentage probability to a recovery.

## 6. Future bank selling is smaller than wallet inventory today

The bank owes **1.378 million internal tokens**, compared with **65.033 million observed non-protocol wallet tokens**. New base issuance is 700,000/day, but it is not minted into wallets until an owner retires branches. Accrual is not a forced unlock or sale.

At today's curve, a sequential exit of the entire current ledger would mint roughly **930,576 tokens** after rising crowd-exit fees. Selling them with no buys produces about **−4.8%** price impact. One giant withdrawal could incur a different fee; the notebook integrates many sequential small withdrawals and labels that convention. This isolates the bank's liability and does not liquidate existing wallet inventories again.

The notebook includes 10%, 25%, 50% and 100% bank-exit cases now, one day and two days ahead. Future rows assume unchanged issuance, no intervening reinvestment and accrual before exits; they are upper liability cases, not retirement predictions. Retirement reduces future branches and can destroy future utility demand. Crowded exit fees suppress immediate selling but also worsen the capital allocator's expected return.

## 7. A conditional re-entry policy

1. **Do not buy merely because the vault has ETH.** Look for actual `BuybackExecuted` events and compare realized hourly buying with selling. The first tick is only about 6.6 ETH.
2. **Separate a bounce from a durable recovery.** A bounce needs buying to exceed the currently active sellers. A durable recovery needs enough ongoing new/returning capital to absorb replacement sellers and eventual branch withdrawals.
3. **Watch the auction after its initial burst.** Does positive flow survive once the 48 remaining licenses sell, or while rational owners wait for a cheaper price? Are payments funded by new buys or by old inventories?
4. **Watch seller replacement.** The constructive signal is declining new seller inventory while fresh buying persists—not merely 340 empty seller addresses.
5. **Require room beyond trading friction.** At unchanged taxes/LP fees, a very small round trip needs roughly 7.33% spot appreciation just to break even before gas, router fees and slippage. A hypothetical +5.9% pool bounce does not establish a profitable buy-and-sell trade.
6. **Treat epoch routing as a later catalyst.** Track cumulative epoch flow and actual settlement near September 18 01:00:30 UTC. Do not count the same hook ETH as both expansion assets and buybacks.

For an owner with a low-accrual branch, preserving future issuance can be rational; a large accrued ledger has much more capital at risk and a different harvest decision. From cash without a Charter, token speculation is the available direct exposure while ETH Charter issuance is disabled. Opening an expensive branch or depositing into another owner's Charter is not an automatic safer alternative.

The strongest defensible conclusion is **wait for changed flows before assuming a new sustained uptrend**. Neither “the top is certainly in” nor “buybacks guarantee recovery” follows from the evidence. The notebook gives editable buy/sell budgets so the conclusion can change when the observations change.

## Evidence, reproducibility and limits

- Fresh state, public RPC requests/results, all 8,392 measured address balances, initialized ticks, registry permissions, vault history and read-only execution probes: [`reentry-evidence/`](reentry-evidence/).
- Reconciled participant histories and wallet capital: [`reentry-results/`](reentry-results/). Total token supply and every collected wallet token balance reconcile exactly in integer units. Branch counts and total pending reconcile. Provenance is approximate pro-rata accounting, not proof of beneficial owner, motivation or cost basis.
- Executed notebook: [`reentry_analysis.ipynb`](reentry_analysis.ipynb). Model: [`reentry_model.py`](reentry_model.py). Prior snapshots remain unchanged.
- Official mechanism description: [STANDARD whitepaper](https://standardreserve.xyz/whitepaper). Its static page/frontend informed ABI discovery and documented routing; deployed-state reads and events support observations. POL execution and exact future fee-routing settlement were not counterfactually simulated.
- Locked liquidity is assumed safe from removal as requested. It can still lose ETH through sales. Models omit gas, MEV, unobserved venues/funding, parameter changes, and unknown future participant preferences. No guaranteed floor or treasury redemption right is assumed.
'''
    (root/'REENTRY_FINDINGS.md').write_text(report)
    cells=[nb.v4.new_markdown_cell('# STANDARD: buybacks, branch demand and re-entry\n\n'+report.split('## 1.')[0].split('\n',1)[1]),nb.v4.new_code_cell("from pathlib import Path\nimport json, copy\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nfrom liquidity import ConcentratedPool\nfrom reentry_model import price_buy_cost\nROOT = Path.cwd()\nOUT = ROOT / 'reentry-results'\nm = json.loads((OUT/'summary.json').read_text())\nprofile = json.loads((ROOT/'reentry-evidence/liquidity.json').read_text())\npool = ConcentratedPool(profile)\npd.Series({k:v for k,v in m.items() if k!='withdrawals'})"),nb.v4.new_markdown_cell('## Fresh observations\nAll dates below are UTC. Buy/sell windows use interpolated block times; their exact underlying transaction IDs remain available. Cash is observed capacity, not a committed bid.'),nb.v4.new_code_cell("display(pd.read_csv(OUT/'participants/windows.csv'))\ndisplay(pd.read_csv(OUT/'capital-by-cohort.csv'))\ndisplay(pd.read_csv(OUT/'funding/followup-license-funding.csv').sum(numeric_only=True))"),nb.v4.new_markdown_cell('## Buybacks and treasury\nThe owner counterfactual call succeeds; an ordinary caller fails NotExecutor. No past buybacks. These cases assume successful hourly execution, unchanged parameters, no replenishment and no opposing sellers. The hook balance can route to expansion or contraction at epoch settlement; it is not added to current buybacks.'),nb.v4.new_code_cell("display(pd.read_csv(OUT/'buyback-cases.csv'))\ndisplay(pd.Series(json.loads((OUT/'fee-reconciliation.json').read_text())))\ndisplay(pd.read_csv(OUT/'isolated-support-cases.csv'))\nchecks=json.loads((ROOT/'reentry-evidence/buyback-execution.json').read_text())\n[(c['label'],c.get('decoded'),c['result']) for c in checks['checks']]"),nb.v4.new_markdown_cell('## Branch allocation and waiting\nZero fresh buying is constructively feasible, not a prediction that every owner will participate. Internal ledgers and owner inventories are consumed once; daily per-Charter limits include earlier purchases. Future waiting cases assume licenses remain available.'),nb.v4.new_code_cell("display(pd.read_csv(OUT/'remaining-license-allocation.csv'))\ndisplay(pd.read_csv(OUT/'license-waiting.csv'))\ndisplay(pd.read_csv(OUT/'branch-payback.csv'))"),nb.v4.new_markdown_cell('## Recovery requirements\nThese ETH budgets include modeled buy tax and LP fee. Sale-first ordering is explicit. The grid uses the archived full initialized-tick curve and fixed locked liquidity.'),nb.v4.new_code_cell("h=pd.read_csv(OUT/'price-hurdles.csv')\ndisplay(h)\nfig,ax=plt.subplots(figsize=(9,5))\nfor sold,g in h.groupby('sold_tokens_first'):\n    ax.plot(g.target_return*100,g.fresh_wallet_ETH,marker='o',label=f'{sold/1e6:g}m tokens sell first')\nax.set(xlabel='Target price increase (%)',ylabel='Fresh buyer ETH required',title='Capital required to recover from the pinned price')\nax.legend();ax.grid(alpha=.25);plt.tight_layout();plt.show()"),nb.v4.new_markdown_cell('## Six-hour scenario tree\nThese are explicit sensitivity cases, with no fitted probabilities. Seller inventory is finite; future inactive-holder activation and incoming capital remain assumptions. The latest weak buying window does not establish how long weakness persists.'),nb.v4.new_code_cell("display(pd.read_csv(OUT/'six-hour-cases.csv'))\np=pd.read_csv(OUT/'six-hour-paths.csv')\nfig,ax=plt.subplots(figsize=(10,5))\nfor name,g in p.groupby('case'):\n    ax.plot(pd.to_datetime(g.timestamp_utc),g.price_return*100,label=name.replace('_',' '))\nax.axhline(0,color='black',lw=.8);ax.set(xlabel='UTC timestamp, 2026-09-16',ylabel='Price change (%)')\nax.legend(fontsize=8);ax.grid(alpha=.25);fig.autofmt_xdate();plt.tight_layout();plt.show()"),nb.v4.new_markdown_cell('## Edit a scenario\nChange the gross ETH budget, existing wallet tokens sold, and target below. This is a conditional pool calculation, not an investment recommendation or a transaction quote. Independent pool copies prevent previous notebook cells from changing the starting state.'),nb.v4.new_code_cell("ordinary_buyer_ETH = 200.0\nwallet_tokens_sold = 3_000_000.0\ntarget_appreciation = 0.25\np = ConcentratedPool(profile)\nsale_ETH, sell_tax_ETH, filled = p.sell(wallet_tokens_sold)\np.buy(ordinary_buyer_ETH)\nprint(f'Final price change: {p.price/pool.price-1:+.2%}')\nprint(f'Further ETH to reach target: {price_buy_cost(p,pool.price*(1+target_appreciation)):,.2f}')\nprint(f'Sale proceeds after modeled fees: {sale_ETH:,.2f} ETH')"),nb.v4.new_markdown_cell('## Optional future bank withdrawals\nAccrual remains internal until branches retire. The sequential fee calculation models the increasing crowd-exit fee. One- and two-day cases hold issuance fixed, allow accrual before retirement, and omit reinvestment. They are liability sensitivities, not scheduled unlocks.'),nb.v4.new_code_cell("display(pd.read_csv(OUT/'optional-bank-exits.csv'))\ndisplay(pd.read_csv(OUT/'issuance-absorption.csv'))"),nb.v4.new_markdown_cell(report[report.index('## 7.'):])]
    book=nb.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}})
    nb.write(book,root/'reentry_analysis.ipynb')

if __name__=='__main__':run()
