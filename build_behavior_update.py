"""Build dated findings and an executable notebook; do not rewrite old reports."""
import argparse,json,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/standard-research-mpl')
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import nbformat as nbf
from participant_flows import ROOT,read

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def run(packet):
    packet=Path(packet).resolve();d=packet/'results';s=read(d/'update-summary.json');old=read(ROOT/'behavior-results/analysis-summary.json');o=read(d/'observation-metadata.json')
    runs=pd.read_csv(d/'scenario-runs.csv');paths=pd.read_csv(d/'scenario-paths.csv.gz');actual=pd.read_csv(d/'observed-since-previous.csv');check=pd.read_csv(d/'previous-path-check.csv');oldpaths=pd.read_csv(ROOT/'behavior-results/scenario-paths.csv.gz');bb=pd.read_csv(d/'buyback-only-trade.csv')
    plt.rcParams.update({'figure.dpi':140,'axes.grid':True,'grid.alpha':.2,'font.size':9})
    fig,ax=plt.subplots(figsize=(11,5))
    for case in ['Observed clocks; cautious beliefs','Stabilization; patient buyers','Speculative recovery']:
        g=oldpaths[(oldpaths.case==case)&(oldpaths.hours<=s['elapsed_hours']+.25)];a=g.groupby('hours').price_return.agg(['min','median','max']);times=pd.Timestamp(s['previous_snapshot_utc'])+pd.to_timedelta(a.index,unit='h')
        ax.plot(times,a['median']*100,label=case);ax.fill_between(times,a['min']*100,a['max']*100,alpha=.1)
    ax.plot(pd.to_datetime(actual.timestamp_utc,format='ISO8601',utc=True),actual.price_return*100,color='black',lw=2,label='Observed swaps after previous snapshot')
    ax.set_ylabel('Change from previous snapshot (%)');ax.set_xlabel('UTC, September 16, 2026');ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'));ax.legend();ax.set_title('Earlier saved scenarios checked against later observations');fig.tight_layout();fig.savefig(d/'previous-path-check.png');plt.close(fig)
    fig,axes=plt.subplots(4,2,figsize=(13,13),sharey=True)
    for ax,(case,g) in zip(axes.flat,paths.groupby('case',sort=False)):
        for _,h in g.groupby('seed'):ax.plot(pd.to_datetime(h.timestamp_utc,utc=True),h.price_return*100,lw=1,alpha=.8)
        ax.axhline(0,color='black',lw=.6);ax.set_title(case);ax.set_ylabel('Change from fresh snapshot (%)');ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=4));ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'));ax.set_xlabel('UTC · 24-hour horizon / 1 day')
    fig.suptitle(f"Fresh-state scenarios from {s['snapshot_utc']} — no probability weights",y=1.005);fig.tight_layout();fig.savefig(d/'updated-paths.png',bbox_inches='tight');plt.close(fig)
    beforeafter=table(['Metric','02:57:33 UTC','05:40:47 UTC'],[
        ['Spot ETH / STANDARD',f"{old['price_ETH']:.9f}",f"{s['price_ETH']:.9f} ({s['price_change_since_previous']:+.2%})"],
        ['Pool ETH principal',f"{old['pool_principal_ETH']:,.2f}",f"{s['pool_principal_ETH']:,.2f}"],
        ['Branches',old['branches'],s['branches']],['Daily licenses remaining',old['remaining_daily_licenses'],s['remaining_licenses']],
        ['Bank claims (STANDARD)',f"{old['bank_pending']:,.0f}",f"{s['bank_pending']:,.0f}"],
        ['Rolling six-hour seller inventory',f"{old['six_hour_seller_remaining_tokens']:,.0f}",f"{s['six_hour_seller_remaining_tokens']:,.0f}"],
        ['Same old seller group inventory',f"{s['previous_seller_group_initial_tokens']:,.0f}",f"{s['previous_seller_group_current_tokens']:,.0f}"],
        ['Buyback vault ETH',f"{old['buyback_vault_ETH']:,.2f}",f"{s['buyback_vault_ETH']:,.2f}"],['Executed buyback tick timestamp',old['buyback_last_tick'],s['buyback_last_tick']]])
    rows=[]
    for case,g in runs.groupby('case',sort=False):rows.append([case,f'{g.ending_price_return.median():+.1%}',f'{g.ending_price_return.min():+.1%} to {g.ending_price_return.max():+.1%}',f'{g.license_fresh_ETH.median():.1f}',f'{g.game_prefund_ETH.median():.1f}'])
    case_table=table(['Same assumption set','24h median','Four-run range','Fresh license ETH','Prospective prefunding ETH'],rows)
    recent_net=s['latest20m_buy_ETH']-s['latest20m_sell_ETH'];caut=check[check.case=='Observed clocks; cautious beliefs'];lastbb=bb[bb.hours==24].iloc[0]
    report=f'''# Fresh STANDARD findings — September 16, 05:40:47 UTC

**Block {s['block']:,}, chain 4663.** Token `0x88ad8DdF1E3898412146a534538d418c6F8A9062`. This update compares the frozen **02:57:33 UTC** snapshot with **05:40:47 UTC**, a gap of **{s['elapsed_hours']:.3f} hours / {s['elapsed_hours']/24:.4f} days**.

**[Open the executed notebook](update.ipynb)** · [Previous research](../../BEHAVIOR_MAP.md) · [Unchanged decision-model rules](../../BEHAVIOR_METHOD.md) · [Machine-readable summary](results/update-summary.json).

## What changed

**The token recovered {s['price_change_since_previous']:.2%} without any executed buybacks.** Canonical buying was **{s['buy_ETH']:,.2f} ETH** versus **{s['sell_ETH']:,.2f} ETH** selling over the interval: **{s['net_pool_ETH']:+,.2f} ETH net pool flow**. These are pool-side amounts: buy ETH after input hook tax, sell ETH before output hook tax; LP fees also affect principal. Exact new swaps are selected by block number.

**It has already given back part of that rebound:** the interval high was **{s['interval_peak_return']:+.2%}** at **{s['interval_peak_utc_exact']}**, and the fresh price is **{s['drawdown_from_interval_peak']:.2%} below that high**. Across all canonical swaps, the last 20 minutes show **{s['latest20m_all_pool_buy_ETH']:.2f} ETH buying versus {s['latest20m_all_pool_sell_ETH']:.2f} ETH selling**. This makes the immediate picture weaker than the positive full-interval net flow suggests.

{beforeafter}

**The latest window is weaker than the interval average:** its attributed buying is only **{s['latest20m_buy_ETH']:.2f} ETH**, against **{s['latest20m_sell_ETH']:.2f} ETH** selling. The rolling seller inventory has increased even though the fixed old group's balance fell slightly. This is evidence of a rebound with renewed selling pressure, not evidence that sellers are exhausted.

The previous cautious case did **not** capture the magnitude of this rebound. At the new observation time, its four old paths showed **{caut.previous_path_return_at_new_pin.min():+.2%} to {caut.previous_path_return_at_new_pin.max():+.2%}**, median **{caut.previous_path_return_at_new_pin.median():+.2%}**, versus the actual **{s['price_change_since_previous']:+.2%}**. The bullish case overshot the observed move. This is a genuine comparison against previously saved paths, not a claim of predictive success or a reason to assign new probabilities from one observation.

![Previous projections versus the observed move](results/previous-path-check.png)

## Branch buying: the auction is now sold out

All **{s['new_licenses']}** licenses that remained at 02:57:33 UTC sold, taking the total to **{s['branches']} branches**. They consumed **{s['license_cost_tokens']:,.0f} STANDARD**. Under the same pro-rata lineage convention, **{s['new_market_funded_license_tokens']:,.0f} tokens ({s['new_market_funded_license_share']:.1%})** came from canonical purchases **after the previous snapshot**. The remaining sources are tabulated in [the interval funding ledger](results/interval-funding/followup-license-funding.csv). This is rebased to 02:57:33 UTC, not merely a subtraction from the older 00:44 dataset.

There are **zero licenses left today**. New license purchases resume at **{s['next_license_reset_utc']}** (September 17, 01:04:04 UTC), unless protocol parameters change. ETH Charter auctions remain disabled. Buying to prefund tomorrow or to speculate can continue; sold out does not logically force all buying to stop.

The final license sale was at **{s['quota_filled_utc_exact']}**, about 12½ minutes before the observed price high. Both milestone times are verified from [their exact block headers](evidence/milestone-headers.json). This sequence is consistent with auction-related attention fading, but does not establish that quota exhaustion caused the reversal; most buying was not traced into spent licenses.

[Interval buyers](results/interval-buyers.csv) and [sellers](results/interval-sellers.csv) include their current inventories and Charter ownership. The largest attributed buyer, `{s['largest_attributed_buyer']}`, bought **{s['largest_attributed_buyer_ETH']:.2f} pool ETH** ({s['largest_buyer_share_of_attributed_buy_ETH']:.1%} of attributed buying). Ownership alone does not prove that those purchases funded licenses; the separate deposit and license ledger supplies the stronger evidence of use.

At unchanged parameters and the current branch count, the next day's opening license ask is about **{s['next_opening_price_if_no_parameter_changes']:,.0f} STANDARD**. A constructive allocation of the next 100 licenses, crediting issuance until reset and sharing each owner's wallet only once, needs **{s['next_day_feasible_fresh_tokens']:,.0f} freshly acquired tokens**. This is feasibility, not expected winners or guaranteed demand. Buying all 100 entirely fresh at that opening ask would cost about **{s['next_day_all_fresh_ETH']:,.1f} ETH** on today's curve; the ask decays later and the curve can change.

Current gross accrual per branch is **{s['branch_daily_tokens']:,.2f} STANDARD/day**. Extra branches dilute this rate. There were **{s['new_withdrawals']} new branch withdrawals** in this interval, so this observed flow was not a new branch-retirement wave. Claims accrue internally and only become tradeable through retirement/minting.

## Are sellers exhausting?

The same old seller group went from **{s['previous_seller_group_initial_tokens']/1e6:.3f}m** to **{s['previous_seller_group_current_tokens']/1e6:.3f}m STANDARD**. Its exact transfer bridge includes **{s['previous_seller_group_inflows']:,.0f} incoming** and **{s['previous_seller_group_outflows']:,.0f} outgoing tokens**; transfers are not all sales. Meanwhile, the current rolling six-hour seller group retains **{s['six_hour_seller_remaining_tokens']/1e6:.3f}m**. Those groups are different and must not be treated as one depleting stock.

Across the update interval, **{s['outside_previous_seller_group_share']:.1%}** of attributed sold tokens came from addresses outside the previous six-hour seller set; **{s['new_first_seller_share']:.1%}** came from addresses making their first observed canonical sale after the previous pin. [Address inventories and acquisition sources](results/seller-inventory-and-entry.csv) are saved so this can be inspected directly.

The latest 20-minute attributed window had **{s['latest20m_buy_ETH']:,.2f} ETH buying** and **{s['latest20m_sell_ETH']:,.2f} ETH selling**, net **{recent_net:+,.2f} ETH**. First-observed sellers supplied **{s['latest20m_first_seller_share']:.1%}** of tokens sold in that window. Short-window membership uses interpolated timestamps; the full-interval block-based totals above do not.

## Buybacks and re-entry economics

The vault still holds **{s['buyback_vault_ETH']:,.2f} ETH**, with `lastTickAt = {s['buyback_last_tick']}`. The buyback address remains `0x796e80E8ABcedc30c700A9587F7933d3342B8946`. Fresh [execution calls](evidence/buyback-execution.json) and [event history](evidence/vault-events.json) are included. No buyback start date is established by this evidence.

At this new price, the first-tick limit is **{s['first_tick_ETH']:,.2f} ETH**. With no opposing sellers and successful hourly execution, the 24-hour buyback-only test spends **{lastbb.buyback_ETH:,.2f} ETH**, moves spot **{lastbb.spot_change:+.2%}**, and leaves a new 1 ETH canonical entry at **{lastbb.one_ETH_entry_net_return:+.2%}** after selling. It excludes gas and assumes TWAP gates pass. The hook's **{s['hook_ETH']:,.2f} ETH** is separate from the executable vault; it is not immediately counted as buyback spending.

For perspective, a hypothetical 1 ETH purchase at the **old** snapshot and sale at the **new** snapshot quotes about **{s['previous_one_ETH_entry_net_return_now']:+.2%}** after canonical fees and impact. This is a small-order hindsight counterfactual, not a trade we made and not a prediction that buying now repeats that return. Today's re-entry faces today's price and seller inventories.

## Updated conditional paths

The same eight parameter sets were rerun with **fresh wallet balances, activity rates, branch state and liquidity**. Each has four seeds and a 24-hour horizon ending **{pd.Timestamp(s['snapshot_utc'])+pd.Timedelta(days=1)}**. These restart the original model, including its zero initial momentum and fresh mean-reversion anchor; they are not a Bayesian posterior or a seamless continuation of an earlier trajectory.

{case_table}

Newcomer capital is still an assumption extrapolated from observed first-buyer spending, now about **{o['new_buyer_native_ETH_hour_last2h']:,.2f} ETH/hour** before the scenario multiplier. Public cash balances remain capacity rather than committed demand. The earlier time-step, action-order and valuation sensitivities still apply. No probability weights or precise selling deadline are justified by these reruns.

![Updated conditional paths](results/updated-paths.png)

## Interpretation

The rebound is observed, and the market has absorbed selling better over this interval than the old cautious paths assumed. It was not caused by an executed buyback. Whether the improvement persists depends on new purchases after today's license quota is exhausted, continued prefunding/speculation, and the activation or replenishment of sellers. A smaller old-seller balance alone cannot establish that selling is finished.

The latest window's return to net selling and the larger rolling seller inventory argue against treating the rebound as a confirmed sustained recovery. Conversely, the actual +9.15% move disproves any claim that decline from the previous snapshot was inevitable. The refreshed evidence supports this conditional assessment rather than a precise recovery probability or a deadline for selling to stop.

The [fresh recovery-budget table](results/recovery-flow-requirements.csv) asks how much buying is needed for +10%, +25%, +50% or +100% spot under different fractions of recent-seller inventory being sold. This is a more directly testable condition than asserting that the token has permanently topped or that a further recovery is inevitable.

## Reproduction and evidence

All **8,787 measured token balances** reconcile individually, and the replay reconciles total supply. Both snapshots, the fixed seller inventory bridge, the branch-funding ledger and simulated asset conservation are checked. Historical route attribution remains incomplete and motives are inferred only as labeled; token lineage is pro-rata, not proof of particular fungible units. Locked liquidity is retained in the future model, with its actual fresh ranges and principal.

From the repository root:

```bash
OPENBLAS_NUM_THREADS=1 python refresh_behavior_update.py behavior-updates/2026-09-16T054047Z
python analyze_behavior_update.py behavior-updates/2026-09-16T054047Z
python build_behavior_update.py behavior-updates/2026-09-16T054047Z
python run_notebook.py behavior-updates/2026-09-16T054047Z/update.ipynb
python verify_behavior_update.py behavior-updates/2026-09-16T054047Z
```

The manifest freezes the published bytes. Rebuilding changes output hashes; verify the published copy first and regenerate the manifest deliberately after a reviewed rebuild. The original collection scripts were run in an isolated layout with the old shared inputs and a new output directory, so previous evidence was preserved. Public RPC requests and responses are archived; no credentialed endpoint, key or signed transaction is needed.
'''
    tail=read(packet/'tail-check.json') if (packet/'tail-check.json').exists() else None
    if tail:
        tailtime=pd.Timestamp(int(tail['header']['timestamp'],16),unit='s',tz='UTC')
        banner=f"\n## Final market check — {tailtime}\n\nA later, limited check shows **{tail['price_ETH']/s['price_ETH']-1:+.2%}** since the full 05:40:47 snapshot, with **{tail['buy_ETH']:.2f} ETH buying versus {tail['sell_ETH']:.2f} ETH selling** during that interval. Spot is **{tail['price_ETH']:.9f} ETH per STANDARD**, and `lastTickAt` remains **{tail['lastTickAt']}**. This reinforces the observation of renewed selling after the rebound. [Raw final check](tail-check.json). Wallet inventories, branch funding and model scenarios below still use **05:40:47 UTC**; they were not silently relabeled as newer.\n"
        report=report.replace('## What changed',banner+'\n## What changed',1)
    (packet/'FINDINGS.md').write_text(report)
    md=nbf.v4.new_markdown_cell;code=nbf.v4.new_code_cell;rel=packet.relative_to(ROOT).as_posix()
    cells=[md(f'''# STANDARD update — {s['snapshot_utc']}

Block **{s['block']:,}**, Robinhood chain **4663**. Compared with **{s['previous_snapshot_utc']}**. [Full findings and interpretation](FINDINGS.md).

This is a fresh evidence update using the previous model. Scenario weights are not calibrated, and hypothetical returns are not executed trades. Locked liquidity remains in the future modeled curve.'''),
    code(f"""from pathlib import Path
import json
import numpy as np
import pandas as pd
from IPython.display import display,Image
ROOT=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'behavior_model.py').exists()); PACKET=ROOT/{rel!r}; D=PACKET/'results'
s=json.loads((D/'update-summary.json').read_text())
display(pd.Series(s).to_frame('Fresh observation'))"""),
    md('## 1. Check the earlier paths against what actually happened\n\nThe old paths were already saved before this observation. One comparison cannot calibrate probabilities; the cautious case missed the rebound and the bullish case overshot it.'),
    code("""display(Image(filename=str(D/'previous-path-check.png')))
check=pd.read_csv(D/'previous-path-check.csv')
display(check.groupby('case',sort=False).agg(old_path_min=('previous_path_return_at_new_pin','min'),old_path_median=('previous_path_return_at_new_pin','median'),old_path_max=('previous_path_return_at_new_pin','max'),actual=('observed_return','first')))"""),
    md('## 2. Actual branch funding and remaining seller inventories\n\nFunding is rebased to the previous 02:57:33 snapshot. Today is sold out. The next-day allocation is a feasible funding construction, not a prediction of auction participation.'),
    code("""funding=json.loads((D/'interval-funding/followup-summary.json').read_text())
display(pd.Series({k:v for k,v in funding.items() if k.startswith('license_paid_')}).to_frame('STANDARD'))
display(pd.read_csv(D/'next-day-license-feasibility.csv')[['ledger_used','wallet_used','new_tokens_needed']].sum().to_frame('Next-day feasible funding'))
display(pd.read_csv(D/'strategy-stocks.csv'))
display(pd.read_csv(D/'seller-inventory-and-entry.csv').query('previous_seller_group').head(15))
display(pd.read_csv(D/'flow-windows.csv').tail(6))"""),
    md('## 3. Fresh-state scenarios\n\nSame eight parameter sets, fresh on-chain inputs, four seeds each. These restart momentum and the reversion anchor at the new snapshot. The numbers are conditional experiments, not updated probabilities. All paths include elapsed hours/days and UTC timestamps.'),
    code("""runs=pd.read_csv(D/'scenario-runs.csv')
display(runs.groupby('case',sort=False).agg(median_return=('ending_price_return','median'),minimum=('ending_price_return','min'),maximum=('ending_price_return','max'),licenses=('licenses','median'),fresh_license_ETH=('license_fresh_ETH','median'),prefunding_ETH=('game_prefund_ETH','median')))
display(Image(filename=str(D/'updated-paths.png')))"""),
    md('## 4. Buying budgets and a new buyback trade\n\nNo buyback has executed. The isolated trade below assumes successful hourly owner execution with no sellers. The hook balance is not treated as immediately spendable vault ETH.'),
    code("""display(pd.read_csv(D/'buyback-only-trade.csv'))
display(pd.read_csv(D/'recovery-flow-requirements.csv').pivot(index='fraction_recent_seller_stock_sold',columns='target_spot_return',values='required_gross_buyer_ETH'))"""),
    md('## 5. Accounting checks\n\nThese verify consistency, not forecasting accuracy. Motives, future capital and optimal selling times remain uncertain. The previous method and sensitivity limitations still apply.'),
    code("""errors=pd.read_csv(D/'accounting.csv.gz')
display(errors[['ETH_error','token_error','ledger_error']].abs().max().to_frame('Maximum absolute error'))
assert errors.ETH_error.abs().max()<1e-5
assert errors.token_error.abs().max()<.03
assert errors.ledger_error.abs().max()<1e-5
assert abs(s['fixed_group_bridge_error'])<1e-5
assert len(runs)==32
assert s['remaining_licenses']==0
assert abs(funding['ledger_reconciliation_error_tokens'])<1e-5
print('Saved-state and simulation checks passed.')""")]
    if tail:
        cells[2:2]=[md('## Final market check\n\nThis later check covers price, canonical flows and the buyback vault only. The full wallet/branch dataset and model remain pinned at 05:40:47 UTC.'),code("""tail=json.loads((PACKET/'tail-check.json').read_text())
display(pd.Series({'timestamp_utc':str(pd.Timestamp(int(tail['header']['timestamp'],16),unit='s',tz='UTC')),'price_ETH':tail['price_ETH'],'change_since_full_snapshot':tail['price_ETH']/s['price_ETH']-1,'buy_ETH_since_full_snapshot':tail['buy_ETH'],'sell_ETH_since_full_snapshot':tail['sell_ETH'],'lastTickAt':tail['lastTickAt']}).to_frame('Later market check'))""")]
    nb=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}});nbf.write(nb,packet/'update.ipynb');print('Built update findings, figures and notebook')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('packet');a=p.parse_args();run(a.packet)
