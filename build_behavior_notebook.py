"""Build the public behavior map, figures and editable notebook from saved results."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/standard-research-mpl')
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import nbformat as nbf
from participant_flows import ROOT,read

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v) for v in r)+' |' for r in rows])

def run(root=ROOT):
    d=root/'behavior-results';s=read(d/'analysis-summary.json');f=read(d/'funding/followup-summary.json');o=read(d/'observation-metadata.json')
    runs=pd.read_csv(d/'scenario-runs.csv');paths=pd.read_csv(d/'scenario-paths.csv.gz');windows=pd.read_csv(d/'flow-windows.csv');sensitivity=pd.read_csv(d/'assumption-sensitivity.csv')
    pin=pd.Timestamp(s['snapshot_utc']);base=mdates.date2num(pin.to_pydatetime());plt.rcParams.update({'figure.dpi':140,'axes.grid':True,'grid.alpha':.18,'font.size':9})
    def clock_axis(ax):
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))
        ax.set_xlabel('UTC timestamp (2026)')
        top=ax.secondary_xaxis('top',functions=(lambda x:(x-base)*24,lambda h:base+h/24));top.set_xlabel('Elapsed hours from snapshot (24 hours = 1 day)')
    def save(fig,name):
        fig.savefig(d/(name+'.png'),bbox_inches='tight');fig.savefig(d/(name+'.svg'),bbox_inches='tight');plt.close(fig)
        svg=d/(name+'.svg');svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    fig,axes=plt.subplots(4,2,figsize=(13,14),sharey=True)
    for ax,(name,g) in zip(axes.flat,paths.groupby('case',sort=False)):
        for seed,h in g.groupby('seed'):
            ax.plot(pd.to_datetime(h.timestamp_utc,utc=True),h.price_return*100,alpha=.65,lw=1,label=f'Run {seed+1}')
        ax.axhline(0,color='black',lw=.7);ax.set_title(name,pad=42);ax.set_ylabel('Spot change (%)');clock_axis(ax)
    fig.suptitle('Conditional paths: four runs per assumption set; no scenario probabilities',y=1.01,fontsize=14);fig.tight_layout(h_pad=3);save(fig,'conditional-paths')
    fig,axes=plt.subplots(3,1,figsize=(12,10))
    x=pd.to_datetime(windows.to_utc,utc=True);axes[0].bar(x,windows.buy_ETH,width=.011,label='Attributed buys',color='#298c64');axes[0].bar(x,-windows.sell_ETH,width=.011,label='Attributed sells',color='#bc5353');axes[0].set_ylabel('Pool ETH / 20 minutes');axes[0].legend();clock_axis(axes[0])
    axes[1].bar(x,windows.new_seller_tokens/1e6,width=.011,label='First observed sale in this window',color='#b55450');axes[1].bar(x,(windows.sold_tokens-windows.new_seller_tokens)/1e6,bottom=windows.new_seller_tokens/1e6,width=.011,label='Earlier observed sellers',color='#8598ab');axes[1].set_ylabel('STANDARD sold (millions)');axes[1].legend();clock_axis(axes[1])
    survival=pd.read_csv(d/'first-sale-survival.csv')
    for name,g in survival.groupby('strategy',sort=False):
        g=g[g.at_risk>=10];axes[2].step(g.hours_since_first_receipt,g.descriptive_survival,where='post',label=name)
    axes[2].set_ylabel('No first sale yet (descriptive)');axes[2].set_xlabel('Hours since first observed receipt (24 hours = 1 day)');axes[2].legend(ncol=3);axes[2].set_ylim(0,1)
    axes[2].set_title('Right-censored and grouped using snapshot behavior; not a forward survival forecast')
    fig.tight_layout(h_pad=3);save(fig,'observed-behavior')
    flows=pd.read_csv(d/'scenario-flows.csv').groupby('case',sort=False).median(numeric_only=True)
    fig,ax=plt.subplots(figsize=(12,6));y=np.arange(len(flows));pos=np.zeros(len(flows));neg=np.zeros(len(flows))
    for label,cols,sgn,color in [('Market buying',['spec_buy_ETH','owner_spec_buy_ETH'],1,'#4676a8'),('Fresh license funding',['license_fresh_buy_ETH'],1,'#359c7d'),('Prospective game prefunding',['game_prefund_ETH'],1,'#83c3a8'),('Buybacks',['buyback_ETH'],1,'#c6aa43'),('Wallet selling',['spec_sell_ETH','owner_spec_sell_ETH'],-1,'#b95758'),('Branch exits sold',['branch_withdraw_sell_ETH'],-1,'#793345')]:
        values=flows.reindex(columns=cols,fill_value=0).sum(axis=1).to_numpy()*sgn;left=pos if sgn>0 else neg;ax.barh(y,values,left=left,label=label,color=color);left+=values
    ax.set_yticks(y,flows.index);ax.invert_yaxis();ax.axvline(0,color='black',lw=.7);ax.set_xlabel('24-hour wallet ETH spent (+) / received (−); taxes differ by side');ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,-.13));ax.set_title('Component medians across four paths; they need not sum to a median path');save(fig,'conditional-flows')
    cases=[]
    for name,g in runs.groupby('case',sort=False):
        cases.append([name,f'{g.ending_price_return.median():+.1%}',f'{g.ending_price_return.min():+.1%} to {g.ending_price_return.max():+.1%}',f'{g.license_fresh_ETH.median():,.1f}',f'{g.game_prefund_ETH.median():,.1f}',f'{g.retired.median():g}'])
    case_table=table(['Assumption set','24h median','Four-run range','Fresh license ETH','Prefunding ETH','Branches retired'],cases)
    doc=f'''# Participant behavior and flow map

**Snapshot: September 16, 2026, 02:57:33 UTC · Robinhood chain 4663 · block {s['block']:,}.**

Token: `0x88ad8DdF1E3898412146a534538d418c6F8A9062`. This is a dated snapshot, not a live quote.

**[Open the executed notebook](participant_behavior.ipynb)** · [Model rules](BEHAVIOR_METHOD.md) · [Raw scenario results](behavior-results/scenario-runs.csv) · [Decision model](behavior_model.py).

## Main findings

1. **Remaining sellers are not a closed group.** The latest 20-minute attributed window contains {windows.iloc[-1].new_seller_tokens/windows.iloc[-1].sold_tokens:.1%} of sold tokens from addresses making their first observed canonical sale in that window. Existing sellers can empty while other holders take their place. There is no defensible depletion countdown without modeling that replacement.
2. **Branch sales create much less immediate market demand than their token cost suggests.** Between 00:44:57 and 02:57:33 UTC, {f['new_licenses']} licenses cost {f['license_cost_tokens']:,.0f} STANDARD. Only {f['license_paid_from_new_canonical_tokens']:,.0f} tokens ({f['license_paid_from_new_canonical_tokens']/f['license_cost_tokens']:.1%}) are allocated to new canonical purchases under pro-rata funding attribution. Prior bank balances, newly accrued rewards and prefunded wallet inventory supplied most of the rest. Net canonical flow was {f['canonical_net_ETH']:,.1f} ETH and spot fell {abs(f['price_change_since_snapshot']):.1%}. No branch withdrawals occurred in this follow-up interval.
3. **All {s['remaining_daily_licenses']} remaining licenses can feasibly be funded without another market purchase.** A shared-wallet allocation proves this possibility; it does not predict who wins. Buying every license entirely fresh at the current ask would cost about {s['remaining_licenses_all_fresh_ETH']:,.1f} ETH. Neither number is compulsory demand. Waiting changes the ask; the quota resets at **September 17, 01:04:04 UTC**.
4. **Buybacks help, but are neither scheduled nor sufficient by themselves for a profitable canonical re-entry in the tested case.** The vault holds {s['buyback_vault_ETH']:,.2f} ETH and has never ticked at this pin. The current first-tick limit is {s['first_tick_ETH']:,.2f} ETH. A 1 ETH entry followed by 24 successful hourly buybacks and no sellers produces roughly +5.45% spot movement but a **−1.81% net round trip**, before gas. Pool fees and hook taxes impose approximately a **{s['small_trade_round_trip_spot_hurdle']:.2%} small-trade price hurdle**; larger trades need more.
5. **Rational behavior alone does not select a most likely price path.** Participants can rationally hold different beliefs. The same observed inventories produce declines, stabilization or recovery under different explicit beliefs and new-capital assumptions. A simple prior-hour flow extrapolation also fails badly in the saved holdout windows. This model is useful for testing conditions, not assigning an unsupported probability that the top is in.

## What people can do

```mermaid
flowchart TD
    A[Capital or existing tokens] --> S[Market participant]
    S --> W[Wait in cash]
    S --> B[Buy if expected executable exit beats cash]
    B --> H[Hold liquid tokens]
    H --> X[Partial sale or full exit]
    X --> W
    W --> B
    H --> G[Existing Charter owner]
    G --> I[Wait for lower ask or more accrued rewards]
    G --> F[Buy a license within daily and Charter caps]
    F --> L[Use internal bank ledger first]
    F --> T[Use existing wallet tokens next]
    F --> M[Buy only the remaining shortfall]
    G --> P[Prefund a prospective license if waiting seems costly]
    M --> AMM[Canonical market buying]
    P --> AMM
    L --> N[Additional branch share of fixed issuance]
    T --> N
    M --> N
    N --> R[Internal ledger accrual and dilution]
    R --> G
    G --> D[Retire some or all branches]
    D --> C[Congestion fee then mint remaining claim]
    C --> H
    X --> SELL[Canonical market selling]
    AMM --> TAX[Hook taxes]
    SELL --> TAX
    TAX --> E[Epoch settlement]
    E --> V[Expansion or contraction allocation]
    E --> POL[POL and team allocation]
    V --> BUY[Owner execution and TWAP gate]
    BUY --> AMM
    A --> OTHER[Fund another owner's Charter]
    OTHER --> RIGHT[No native payout right established; separate agreement required]
```

Each Charter has its own bank ledger. Charters belonging to the same wallet share that wallet's tokens and cash. Depositing burns wallet tokens into an internal claim; retirement releases a net minted claim and destroys the retired branches. Internal issuance is **not** an automatic sell and is **not** ETH revenue. An owner can retire and keep the minted tokens instead of immediately selling.

ETH Charter auctions are disabled at the snapshot. The new simulation therefore permits expansion only through the existing owners. It does not invent a right for outsiders to open or withdraw another owner's branches. Funding another person is an additional agreement and counterparty exposure, not a native branch return.

## Observed inventory, cadence and provenance

There are **{s['non_protocol_wallet_tokens']/1e6:,.3f} million wallet tokens** outside identified protocol custody, plus **{s['bank_pending']/1e6:,.3f} million pending bank claims**. Do not add pool inventory to the wallet sell overhang. The {s['six_hour_seller_addresses']} six-hour sellers retain **{s['six_hour_seller_remaining_tokens']/1e6:,.3f} million tokens**; {s['six_hour_sellers_empty']} are already empty at the pin. Future selling can come from other holders and minted withdrawals too.

The pool curve contains **{s['pool_principal_ETH']:,.2f} ETH** of principal and **{s['pool_principal_tokens']/1e6:,.3f} million STANDARD**. Locked liquidity is assumed to remain available throughout. That protects against removal in this experiment; it does not prevent sales from drawing ETH out of the pool.

![Observed flow, seller replacement and first-sale timing](behavior-results/observed-behavior.png)

[Per-wallet population](behavior-results/population.csv.gz), [classified trades with transaction IDs](behavior-results/classified-trades.csv.gz), [acquisition records](behavior-results/participants/acquisitions.csv.gz), [sale provenance](behavior-results/participants/sell-provenance.csv), [cadence](behavior-results/cadence.csv) and [funding attribution](behavior-results/funding/followup-license-funding.csv) are included. These are address-level observations, not identified people. Trade timestamps between archived headers are interpolated; minute-level gaps and window membership are approximate.

Recent sellers' median measured sale fraction is about 95%; Charter owners' is about 60%. These are transaction fractions, not promises to liquidate that share again. Repeat-trade gaps are conditional on repeating and often reflect launch bursts. The simulation uses recent per-wallet event counts and partial-sale fractions rather than extrapolating sub-minute launch gaps all day. Snapshot-conditioned strategy labels and first-sale survival curves are descriptive, not causal predictors.

## Conditional 24-hour paths

All paths start **September 16, 02:57:33 UTC** and end **September 17, 02:57:33 UTC** (+24 hours / +1 day). Four seeded runs per case expose some model dispersion; they are too few and too assumption-dependent to estimate market probabilities. The range below is only the minimum and maximum of those four runs.

{case_table}

“Observed clocks” means activity timings are initialized from history. Its future price beliefs, participant attention, prospective purchases and capital arrivals are still assumptions. Future new-buyer budgets are resampled from the last two hours' first-buyer spending, approximately {o['new_buyer_native_ETH_hour_last2h']:,.1f} ETH/hour before any multiplier. This is **not proof that this much outside ETH will arrive**. Existing {o['wallet_native_ETH_observed']:,.0f} ETH of measured native balances are a capacity ceiling, not committed demand.

![Conditional price paths](behavior-results/conditional-paths.png)

![Flow decomposition](behavior-results/conditional-flows.png)

The cautious case produces a median {runs[runs.case=='Observed clocks; cautious beliefs'].ending_price_return.median():+.1%} one-day spot move, but its four paths span a gain and a loss. It must not be relabeled a “most likely” forecast. A recovery case requires considerably more speculative buying, supported here by stronger beliefs and twice the assumed newcomer arrival rate. Under faster seller activation and weaker incoming demand, the four runs end around −57% to −65%.

The separate [sensitivity runs](behavior-results/assumption-sensitivity.csv) alter action ordering, the time step, prospective branch prefunding and the branch valuation horizon. Changing the step from 15 to 7.5 minutes changes the two tested returns to roughly −21% and +6%. Random-clock discretization and feedback matter; these are **not numerically stable trade-timing estimates**.

## What would support a recovery?

The robust question is how much buying is needed for a specified seller inventory and price target. [The flow requirement table](behavior-results/recovery-flow-requirements.csv) uses the actual liquidity ranges, taxes and pool fee. With no sales, roughly **184 ETH** of gross market buying produces +10% spot, **427 ETH** produces +25%, and **775 ETH** produces +50%. Selling adds to those requirements; a spot recovery does not equal the same return to a new buyer after fees.

Watch these quantities together: new versus repeat seller volume; remaining inventories and fresh receipts; actual deposits funded by new market purchases; spending by genuinely new buyer addresses; and successfully executed buybacks. A shrinking old-seller inventory on its own is insufficient. Owner market buys must not all be labeled game purchases.

## Selling times and the “optimal” path

The notebook compares **precommitted 0, 1, 3, 6, 12 and 24-hour exits**, with both elapsed days and UTC timestamps. It reports executable proceeds for a 10,000-token marginal order and net returns for an illustrative 1 ETH re-entry. These quotes are on saved crowd paths and do not rerun the crowd around your order. Larger positions require a full counterfactual replay with their inventory removed from the population.

The model also saves every simulated license purchase and branch retirement with its elapsed time. Hindsight peak times are available in `scenario-runs.csv`, but are not a policy you could have known in advance. An end-of-window peak is unresolved beyond the horizon. The branch continuation grid spans one hour to 60 days by default; a best value at 60 days is not a predicted 60-day selling date.

**Practical interpretation:** this evidence supports separating optional game demand from committed market flows and testing seller replacement against real buying budgets. It does not establish that an exact recovery, top or best entry/exit time has been predicted.

## Reproduce and inspect

Install `requirements.txt`, then run offline from the repository root:

```bash
python behavior_refresh.py
python behavior_funding.py
python behavior_observations.py
OPENBLAS_NUM_THREADS=1 python behavior_model.py
OPENBLAS_NUM_THREADS=1 python behavior_sensitivity.py
python behavior_analysis.py
python build_behavior_notebook.py
python run_notebook.py participant_behavior.ipynb
python -m unittest discover -p test_behavior.py -v
python verify_behavior.py
```

The published manifest freezes evidence, source and outputs. Rebuilding compressed files, figures or notebook outputs can change byte hashes even when the analysis agrees; verify the published copy before rebuilding, and deliberately create a new manifest after a reviewed refresh. Collectors are read-only public-RPC scripts, but their output location is fixed: copy them into a new evidence workspace before collecting another snapshot. No keys, signatures, trading transactions or credentialed endpoints are needed.
'''
    (root/'BEHAVIOR_MAP.md').write_text(doc)
    md=nbf.v4.new_markdown_cell;code=nbf.v4.new_code_cell
    cells=[md('''# STANDARD: participant behavior, capital allocation and selling cadence

**Pinned at 2026-09-16 02:57:33 UTC, block 64,168,224, Robinhood chain 4663.**

This notebook separates observed flows, contract mechanics and assumed future behavior. It covers liquid holders, Charter owners, partial/full retirement, internal reinvestment, fresh game funding, prospective prefunding and conditional buybacks. Funding another owner gives no modeled native payout right. Locked liquidity stays in the modeled pool.

Read [the behavior map](BEHAVIOR_MAP.md) for the full decision tree and findings, and [the method](BEHAVIOR_METHOD.md) for equations and limitations. **No scenario probabilities or most-likely top are claimed.**'''),
    code("""from pathlib import Path
import json
import numpy as np
import pandas as pd
from IPython.display import display, Image
ROOT=Path.cwd(); D=ROOT/'behavior-results'
summary=json.loads((D/'analysis-summary.json').read_text())
runs=pd.read_csv(D/'scenario-runs.csv')
paths=pd.read_csv(D/'scenario-paths.csv.gz')
display(pd.Series(summary).to_frame('snapshot / rule'))"""),
    md('''## 1. Observed stocks and how game purchases were funded

Wallet inventory, internal bank claims and pool reserves are distinct. Ownership does not establish buying intent. Funding lineage is pro-rata for fungible tokens; aggregate balances and license cost reconcile exactly. The 54-license follow-up spans 00:44:57–02:57:33 UTC; only about 7.8% of license spend traces to new canonical purchases.'''),
    code("""display(pd.read_csv(D/'strategy-stocks.csv'))
funding=json.loads((D/'funding/followup-summary.json').read_text())
display(pd.Series({k:v for k,v in funding.items() if k.startswith('license_paid_')}).to_frame('STANDARD'))
allocation=pd.read_csv(D/'remaining-license-feasibility.csv')
display(allocation[['ledger_used','wallet_used','new_tokens_needed']].sum().to_frame('Feasible funding of remaining licenses'))"""),
    md('''## 2. Sale size, cadence and replacement sellers

The first-sale curve includes unsold wallets as right-censored observations. It uses snapshot-defined groups and approximate interpolated trade times: it is not a validated forward hazard. “Inactive holder” means no recent canonical activity, not no historical trade. A buy by a Charter owner is not automatically game demand.'''),
    code("""display(Image(filename=str(D/'observed-behavior.png')))
display(pd.read_csv(D/'cadence.csv'))
display(pd.read_csv(D/'flow-windows.csv').tail(6))
display(pd.read_csv(D/'participants/sell-provenance.csv').query('window_hours < 0.34'))"""),
    md('''## 3. Conditional paths, not a probability forecast

One day = September 16, 02:57:33 UTC → September 17, 02:57:33 UTC. Each case has four seeded paths. Changing beliefs changes the willingness to use otherwise identical cash and token inventories. Endogenous re-entry recycles sale proceeds; new entrants bring separately recorded budgets. The recovery case doubles assumed newcomer arrivals, not a measured promise of future capital.'''),
    code("""display(runs.groupby('case',sort=False).agg(median_return=('ending_price_return','median'),minimum=('ending_price_return','min'),maximum=('ending_price_return','max'),fresh_license_ETH=('license_fresh_ETH','median'),prefunding_ETH=('game_prefund_ETH','median'),branches_retired=('retired','median')))
display(Image(filename=str(D/'conditional-paths.png')))
display(Image(filename=str(D/'conditional-flows.png')))"""),
    md('''## 4. Buying requirements and buybacks

These curve calculations are more direct than forecasting private beliefs. The recovery table assumes specified recent-seller inventory sells first, followed by buying to a target. It includes pool fees and hook taxes. The buyback-only worksheet assumes owner execution every hour, TWAP gates passing, no opposing sellers, no vault replenishment and a 1 ETH investor entry. No buyback has executed at the pin; no start date is verified.'''),
    code("""display(pd.read_csv(D/'recovery-flow-requirements.csv').pivot(index='fraction_recent_seller_stock_sold',columns='target_spot_return',values='required_gross_buyer_ETH'))
display(pd.read_csv(D/'buyback-only-trade.csv'))"""),
    md('''## 5. Selling cadence and precommitted exits

The 10,000-token order is an illustrative marginal liquidation quote. The 1 ETH re-entry uses the snapshot purchase quote and later executable sale quote; its crowd path is not resimulated. No horizon is selected using future prices before the decision. A hindsight price peak is a descriptive statistic, not an optimal policy. UTC and elapsed hours/days are both retained.'''),
    code("""exits=pd.read_csv(D/'precommitted-exit-worksheet.csv')
display(exits[exits.seed==0].pivot(index=['hours','elapsed_days','timestamp_utc'],columns='case',values='new_one_ETH_entry_net_return'))
display(runs[['case','seed','hindsight_peak_hours','hindsight_peak_utc','peak_return']])
events=pd.read_csv(D/'case-1-events.csv')
events['elapsed_days']=events.hour/24
events['timestamp_utc']=(pd.Timestamp(summary['snapshot_utc'])+pd.to_timedelta(events.hour,unit='h')).astype(str)
display(events.head(20))"""),
    md('''## 6. What is and is not validated

Balance conservation and caps are tested. Price forecasting is not validated. The simple prior-hour-flow holdout illustrates instability; it is not an out-of-sample test of this agent model. The step-size and action-order variants also change results materially. Four paths per case and two per sensitivity do not support statistical confidence claims.'''),
    code("""display(pd.read_csv(D/'persistence-holdout.csv'))
display(pd.read_csv(D/'assumption-sensitivity.csv')[['case','seed','ending_price_return','license_fresh_ETH','game_prefund_ETH','retired']])
errors=pd.read_csv(D/'accounting.csv.gz')
display(errors[['ETH_error','token_error','ledger_error']].abs().max().to_frame('Maximum absolute accounting error'))
assert errors.ETH_error.abs().max()<1e-5
assert errors.token_error.abs().max()<.03
assert errors.ledger_error.abs().max()<1e-5
assert len(runs)==32
assert summary['remaining_licenses_feasible_fresh_tokens']==0"""),
    md('''## 7. Edit assumptions and run your own offline case

`prior_growth_day` is a subjective log-price-growth belief, not a forecast. `new_capital_multiplier` scales assumed arrival intensity. Previously inactive wallets have a separate activation process. Prices depend on all of these choices and on the actual liquidity curve. Set the switch below to `True` to run; it is off so opening/executing the shared notebook does not launch another scenario batch.

Limits include unknown motives, unmeasured outside wealth, no secondary-route execution, idle POL, assumed owner attention, no gas/MEV, a finite continuation grid and no Nash-equilibrium solution. The model does not promise that rational actors correctly predict one another.'''),
    code("""from behavior_model import Config,Economy
custom=Config(name='My conditional case',hours=24,prior_growth_day=-.03,new_capital_multiplier=1.,seller_activation_multiplier=1.,execute_buybacks=False,valuation_days=60,prefund_enabled=True)
RUN_CUSTOM=False
if RUN_CUSTOM:
    economy=Economy(custom,seed=123)
    custom_path,custom_events,custom_accounting=economy.run()
    display(custom_path)
else:
    display(pd.Series(vars(custom)).to_frame('Editable assumptions'))""")]
    nb=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}})
    nbf.write(nb,root/'participant_behavior.ipynb');print('Built behavior map, figures and notebook')

if __name__=='__main__':run()
