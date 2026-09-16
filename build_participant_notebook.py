from pathlib import Path
import nbformat as nbf
p=Path(__file__).resolve().parent
md=nbf.v4.new_markdown_cell;code=nbf.v4.new_code_cell
cells=[
md('''# STANDARD: participants, acquisition history and branch decisions

**UTC throughout.** The participant snapshot is **2026-09-16 00:44:57 UTC**, block **64,089,150**. A separate observed auction follow-up ends **01:14:41 UTC**, block **64,106,912**. These are frozen observations, not live prices.

This notebook answers: who bought/sold, what inventory sellers used, how Charter owners funded actual new branches, and which participant choices could sustain or reverse selling. Addresses are not identified people. Scenarios are conditional; they do not establish calibrated probabilities or a uniquely optimal selling time.

[Findings](PARTICIPANTS.md) · [Method and reproduction](PARTICIPANT_METHOD.md) · [Raw evidence](strategy-current/)'''),
code('''from pathlib import Path
import io, contextlib, json
import numpy as np
import pandas as pd
from IPython.display import display, Markdown, Image
from participant_flows import analyze, ROOT, read
from participant_decisions import run
from participant_followup import run as followup
from participant_publication import build
# Everything below runs offline from public pinned data.
with contextlib.redirect_stdout(io.StringIO()):
    attribution = analyze()
    decisions = run()
    latest = followup()
report = build()
out = ROOT / 'participant-results'
display(pd.Series({k: attribution[k] for k in ['snapshot_utc','block','transfer_logs','canonical_swaps','integer_supply_reconciled','all_collected_wallet_balances_reconciled']}))'''),
md('''## 1. Actual buys and sells, and attribution coverage

Pool ETH is the canonical leg of a trade, before sell-hook deductions / after buy-hook accounting. Routed noncanonical legs are excluded. We reconstruct token-owning endpoints rather than label a router or transaction bundler as the investor. Ambiguous transactions remain in the denominator and are exported separately. Window boundaries use interpolated timestamps between pinned headers; exact blocks and hashes are retained.'''),
code('''windows = pd.read_csv(out/'windows.csv')
display(windows[['window_hours','from_utc_approx','to_utc','side','all_pool_eth','attributed_pool_eth','attribution_fraction','addresses','new_to_canonical_pool_buy_eth']])
cohorts = pd.read_csv(out/'cohorts.csv')
display(cohorts)'''),
md('''## 2. Sellers' acquisition histories and remaining inventory

Sale provenance uses pro-rata inventory accounting. A transfer preserves upstream acquisition lineage but does not establish that the two addresses share an owner. Canonical and two verified secondary-pool purchases are distinguished from branch mints, genesis allocations and unresolved custody outflows. Unknown cost basis is not treated as zero.

The largest seller's four exits each sold 25% of its then-remaining balance. Its inventory came from previous market purchases. See full trade hashes and precise timestamp flags in `participant-results/trades.csv.gz`.'''),
code('''wallets = pd.read_csv(out/'wallets.csv.gz')
cols = ['address','cohort','charter_count','wallet_tokens','native_eth','buy_pool_eth_6h','sell_pool_eth_6h']
display(wallets.nlargest(12,'sell_pool_eth_6h')[cols])
display(pd.read_csv(out/'sell-provenance.csv').query('window_hours == 6'))
display(pd.Series({k: decisions[k] for k in ['recent_selling_addresses','recent_sellers_zero_balance','recent_seller_remaining_tokens','inactive_inventory_tokens']}))'''),
md('''## 3. Buyers and operators are distinct groups

A Charter owner may speculate with wallet tokens while leaving its branch running. “Net buyer”, “net seller” and “two-way trader” describe the last six hours, not permanent motives. Zero or missing native ETH does not prove inability to buy: wrapped assets, stablecoins and external inflows are not fully measured. Owner inventory is shared across its Charters, never duplicated.'''),
code('''display(wallets.nlargest(10,'buy_pool_eth_6h')[cols])
deposits = pd.read_csv(out/'bank-deposits.csv')
display(deposits.groupby('owner_deposit').agg(events=('tx','count'),tokens=('tokens','sum')))
funding = pd.read_csv(out/'license-funding.csv')
display(funding.query('hours_after_reset <= 8'))'''),
md('''## 4. The branches actually sold: later evidence

This section is **post-snapshot observation**, not a forecasting backtest. Bank deposits are token burns into an internal ledger; licenses then spend that ledger. Depositing old inventory and spending internal rewards do not force a contemporaneous pool purchase.

The first checkpoint at 01:09:32 UTC recorded 50 licenses and a 6.4% token rebound. The next checkpoint at 01:14:41 recorded 51 licenses, renewed selling and only a 1.2% gain from the original snapshot. The ownership and funding tables below show how much demand actually came from the expanding operators.'''),
code('''display(pd.Series(latest))
display(pd.read_csv(out/'followup-license-funding.csv').head(12))
display(pd.read_csv(out/'followup-trades.csv').groupby(['side','bought_license_in_window']).canonical_ETH.sum())
display(Image(filename=str(out/'branch-funding-and-incentives.png')))'''),
md('''## 5. Rational choices depend on the participant's balance

Compare executable ETH proceeds today with expected executable proceeds later, including issuance, dilution, resolution fees, market taxes and slippage. In general **E[quantity × price] is not E[quantity] × E[price]**; price and issuance can move together.

The one-day threshold table uses each actual Charter. A small earned balance can grow rapidly relative to its size; a large prefunded balance cannot. Quiet versus heavy future withdrawal pressure changes the fee tradeoff.

The separate 14-day optimal-full-retirement grid is a horizon sensitivity, **not a complete optimal policy**. Partial exits, a branch's value beyond the horizon, future auctions and policy changes are omitted. An endpoint maximum is censored. Actual license purchases show why a short horizon with no continuing branch value cannot explain every owner's choice. Do not infer zero demand or irrationality from that restriction.'''),
code('''thresholds = pd.read_csv(out/'branch-hold-thresholds.csv')
display(thresholds.groupby('future_exit_pressure').one_day_max_price_fall.describe())
display(thresholds.query("future_exit_pressure == 'quiet'").nsmallest(12,'one_day_max_price_fall'))
stopping = pd.read_csv(out/'branch-decisions.csv')
display(stopping.groupby('assumed_daily_price_fall').agg(median_full_exit_day=('optimal_full_exit_day_within_14d','median'),horizon_censored=('exit_horizon_censored','sum')))
display(pd.read_csv(out/'recovery-hurdles.csv'))'''),
md('''## 6. Which flows produce recovery or further decline?

These are **six-hour stress paths from the earlier snapshot**, ending 06:44:57 UTC, not updated predictions conditional on the observed auction. Seller continuation is bounded by remaining tokens. Replacement-selling volume and new-entry capacity come from observed participants; persisting them is still an assumption. Buyers have finite measured native-ETH budgets and a visible reservation-price gate.

`observed_replacement` maintains first-sale volume; `seller_exhaustion` removes replacement sellers; `renewed_entry` sustains the stronger last-two-hour arrival rate; `broader_holder_exit` doubles replacement volume. Licenses and bank exits are assessed in the actual-follow-up and owner-decision sections, rather than added as unverified automatic flows. No likelihood weights are assigned. The later burst of buying and its reversal demonstrate why these paths must not be marketed as exact top predictions.'''),
code('''display(pd.read_csv(out/'conditional-scenarios.csv'))
display(Image(filename=str(out/'participant-flows-and-paths.png')))
paths = pd.read_csv(out/'conditional-paths.csv')
display(paths.groupby('scenario')[['ETH_error','token_error']].max())'''),
md('''## 7. What to monitor next

- New selling addresses and the inventory they control; do not extrapolate depleted sellers forever.
- Canonical net ETH buying after the license-opening burst.
- Whether remaining licenses are funded with new acquisitions, existing wallet tokens or bank balances.
- Charter owners retiring branches versus merely selling separately held tokens.
- The remaining license quota, falling auction price, dilution and resolution-fee pressure.
- Noncanonical route activity and unmeasured capital; one wallet address is not necessarily one person.

Locked protocol liquidity stays in the model, but selling removes ETH from it. A burn can reduce future sale inventory without adding a new market bid. The evidence supports an observed fragile rebound; it does not uniquely identify the next price path or the final top.''')]
nb=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}})
nbf.write(nb,p/'participant_analysis.ipynb')
print('Built participant_analysis.ipynb')
