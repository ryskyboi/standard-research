"""Build the evidence-conditioned recovery notebook; execution is offline."""
from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parent
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [md('''# STANDARD: has the earlier high held, and what would a recovery require?

**Updated evidence: September 15, 2026, 22:45:58 UTC.** Hours and days remain relative to this pin; calendar labels are UTC.

This notebook adds a short-horizon flow projection to the earlier agent research. It replaces the starting price, liquidity ranges, fees, pending rewards, vault state and measured turnover with a fresh, consistent on-chain observation. **It does not refit the older agents' unobserved budgets or assign probabilities to future behavior.** The original notebooks remain historical experiments.

A 10% bounce, reclaiming the 13:40 reference and reclaiming the 10:09 reference are different outcomes. Neither reference is asserted to be the all-time high. We have not reconstructed the full price history, and cannot estimate the probability that the ultimate top has occurred.

**Decision read:** current net selling and inactive buybacks favor caution about a prompt full recovery. A bounce remains plausible if selling exhausts itself. A prior high can remain the top while the token has several sizable rallies. Scenario counts are not probabilities.
'''), code('''from pathlib import Path
from dataclasses import replace, asdict
import json, hashlib, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display
ROOT = next(p for p in [Path.cwd(), Path.cwd()/'research'/'standard-exit'] if (p/'recovery_model.py').exists())
sys.path.insert(0, str(ROOT))
import recovery_model as rm
from time_display import utc_axis, utc_at
e = rm.load_evidence(ROOT)
OUT = ROOT/'recovery-results'; OUT.mkdir(exist_ok=True)
pd.set_option('display.max_columns', 30)
pool = rm.pool_for(e)
print('Pin:', utc_at(e['timestamp']), 'block', e['summary']['block'])
print('Token:', e['summary']['token'], 'chain:', e['summary']['chainId'])
print('Price ETH:', pool.price)
print('Actual ETH principal:', pool.available_eth, '| active virtual ETH:', pool.eth)
print('Measured 40-minute buy spending, before hook tax, ETH/hour:', e['buy_wallet_eth_hour'])
print('Measured token selling/hour:', e['sell_tokens_hour'])
print('Next license reset:', utc_at(e['timestamp'], e['reset_hour']), '| +hours:', e['reset_hour'])
print('Epoch scheduled end:', utc_at(pd.Timestamp(int(e['policy']['bank.epochEnd']), unit='s', tz='UTC')))
display(pd.DataFrame(e['summary']['windows'])[['label','startUTC','endUTC','buysETH','sellsETH','priceChangePct','withdrawals']])
'''), md('''## 1. Minimum buying required through the actual liquidity curve

These are **buy-only lower bounds**, including the observed 2% buy tax and 1% LP fee. Continuing sales increase the necessary expenditure. The token is priced against ETH; this does not forecast ETH/USD. Actual principal and active virtual reserves are kept separate. Existing locked protocol positions were rechecked unchanged and remain safe by assumption; no future LP withdrawal is modeled.
'''), code('''costs = rm.thresholds(e)
display(costs.round(6))
costs.to_csv(OUT/'recovery-thresholds.csv', index=False)
fig, ax = plt.subplots(figsize=(10, 4))
ax.barh(costs.target, costs.wallet_buy_eth_no_sellers, color='#287d8e')
ax.set_xlabel('Wallet ETH required if no one sells (buy tax + LP fee included)')
ax.set_title('A small bounce and a full recovery require different amounts of buying')
for i, value in enumerate(costs.wallet_buy_eth_no_sellers): ax.text(value+8, i, f'{value:,.0f} ETH', va='center')
ax.set_xlim(0, costs.wallet_buy_eth_no_sellers.max()*1.2)
fig.tight_layout(); fig.savefig(OUT/'recovery-costs.png', dpi=160); plt.show()
'''), md('''### How much buying could the next license allocation generate?

The current quota is exhausted and the next reset is shown above. This is a cap on new licenses, not a cap on speculative token buying. The table assumes all 100 licenses clear, and quotes the fresh-funded portion through the current pool. It is a counterfactual demand budget, not a prediction of the auction's price or fill rate. The opening-price case uses twice the last sale; the floor illustration uses two days of the current per-branch issuance. Actual clearing depends on auction sequence and time.
'''), code('''license_rows=[]
last_sale=int(e['state']['license.lastSalePrice'])/1e18
floor_illustration=(int(e['state']['bank.baseIssuancePerDay'])/1e18)*(int(e['state']['bank.multiplierWad'])/1e18)/int(e['state']['bank.totalBranches'])*int(e['auctions']['license.floorPaybackDays'])
for label,qty in [('Illustrative next floor',floor_illustration),('Last observed sale',last_sale),('Implied next opening',last_sale*int(e['auctions']['license.startMultiplier']))]:
    for fraction in [.2,1.]:
        tokens=100*qty*fraction
        license_rows.append(dict(assumed_average_price=label,tokens_per_license=qty,licenses=100,fresh_fraction=fraction,
            fresh_tokens=tokens,wallet_eth_at_current_pool=rm.pool_for(e).quote_buy(tokens),
            reset_utc=utc_at(e['timestamp'],e['reset_hour'])))
license_budget=pd.DataFrame(license_rows);display(license_budget.round(3))
license_budget.to_csv(OUT/'license-demand-budget.csv',index=False)
'''), md('''## 2. Explicit future-flow assumptions

The starting rates use the two adjacent twenty-minute windows, not the overlapping five-minute window. Purchases are measured ETH spending; sales are token quantities. A falling price therefore reduces the ETH received for the same token quantity. Input/output taxes and range crossings are executed by the curve.

**No case below is a fitted forecast.** Extrapolating 40 minutes over 48 hours is a stress test. Sustained buying requires continued spending, and sellers' remaining inventory and willingness are not known. A half-life describes an assumed decline in selling activity, not a measured lockup or unlock.

License cases assume 100 purchases per reset at the last observed price as an illustrative average. Actual sequential auction clearing prices, funding allocation among owners and purchase times are unknown. Internal ledger spending cannot exceed available aggregate earnings; per-owner eligibility is not solved here. Ledger funding creates no market buy. New ETH Charters remain disabled.

Buybacks are off by default because `lastTickAt` is zero. The enabled case assumes execution gates permit hourly purchases, respecting observed spend caps and the finite vault. It does not assume an expansion-vault transfer, tax-funded refill or POL deployment. Taxes collected are not recycled into additional purchases in this overlay.

Issuance continues into the internal ledger at the observed rate; it does not automatically become market selling. The withdrawal stress retires half the branches at +6h, applies the congestion fee and immediately sells the net mint. This is aggregate stress, not the full cohort decision model. The scheduled epoch end is September 18, 2026, 01:00:30 UTC, beyond this 48-hour horizon. The model rejects projections extending to that unsettled boundary; multiplier changes, recycled issuance and new policy allocations would require fresh inputs. The 24-hour results involve less extrapolation of the brief flow sample.
'''), code('''configs = rm.default_scenarios()
assumptions = pd.DataFrame([asdict(c) for c in configs])
display(assumptions)
assumptions.to_csv(OUT/'scenario-assumptions.csv', index=False)
paths = {c.name: rm.simulate(e, c) for c in configs}
summary = rm.summarize(e, paths)
display(summary[['scenario','price_ratio_6h','price_ratio_24h','price_ratio_48h','low_h','low_utc',
                 'speculative_buy_eth','license_buy_eth','buyback_eth']].round(4))
summary.to_csv(OUT/'scenario-summary.csv', index=False)
pd.concat([f.assign(scenario=name) for name,f in paths.items()], ignore_index=True).to_csv(OUT/'scenario-paths.csv', index=False)
'''), code('''fig, axes = plt.subplots(1,2,figsize=(15,5))
for i, (name, frame) in enumerate(paths.items()):
    ax = axes[0] if i < 5 else axes[1]
    ax.plot(frame.hour, frame.price_ratio, label=name, linewidth=1.6)
axes[1].plot(paths[configs[1].name].hour, paths[configs[1].name].price_ratio, '--', color='black', label='6h decay, no added support')
for ax in axes:
    ax.axhline(1, color='grey', linewidth=.7)
    ax.axhline(e['references']['Reclaim 13:40 UTC reference']/e['price'], color='grey', linestyle=':', label='13:40 reference')
    ax.set(xlabel='Hours after snapshot (24h = 1 day)', ylabel='Price / fresh snapshot price')
    ax.grid(alpha=.2); ax.legend(fontsize=7); utc_axis(ax,e['timestamp'])
axes[0].set_title('Future buying and seller exhaustion dominate')
axes[1].set_title('Licenses, buybacks and a withdrawal stress')
fig.tight_layout(); fig.savefig(OUT/'recovery-scenarios.png', dpi=160); plt.show()
'''), md('''## 3. Sensitivity: do not turn a chosen scenario mix into odds

Cells show the terminal price at +24h relative to the new snapshot. Rows vary the unobserved persistence of selling; columns vary buying relative to the measured starting rate. The grid does not assign likelihood to any cell. All use identical pinned liquidity and fees, with no automatic buyback or license demand.
'''), code('''grid=[]
for half in [2,6,12,None]:
    for multiple in [.5,1,2,3]:
        c=rm.Scenario(hours=24,buy_multiple=multiple,sell_half_life_hours=half)
        f=rm.simulate(e,c)
        grid.append(dict(selling_half_life='Persists' if half is None else f'{half}h',buy_multiple=multiple,
                         final_ratio=f.iloc[-1].price_ratio,scenario_end_utc=f.iloc[-1].timestamp_utc))
sensitivity=pd.DataFrame(grid)
sensitivity.to_csv(OUT/'flow-sensitivity.csv',index=False)
matrix=sensitivity.pivot(index='selling_half_life',columns='buy_multiple',values='final_ratio').reindex(['2h','6h','12h','Persists'])
display(matrix.round(3))
fig,ax=plt.subplots(figsize=(7,4))
im=ax.imshow(matrix.to_numpy(),cmap='RdYlGn',vmin=.4,vmax=1.6)
ax.set_xticks(range(len(matrix.columns)),[str(x)+'x' for x in matrix.columns]); ax.set_yticks(range(len(matrix.index)),matrix.index)
for i in range(len(matrix.index)):
    for j in range(len(matrix.columns)): ax.text(j,i,f'{matrix.iloc[i,j]:.2f}x',ha='center',va='center')
ax.set(xlabel='Buying / measured 40-minute rate',ylabel='Assumed selling half-life',title='Price ratio at '+utc_at(e['timestamp'],24)+' (+1 day)')
fig.colorbar(im,ax=ax,label='Price / snapshot');fig.tight_layout();fig.savefig(OUT/'flow-sensitivity.png',dpi=160);plt.show()
'''), md('''## 4. Turn recovery targets into falsifiable flow requirements

For each selling-persistence assumption, solve for the constant hourly buying needed to finish +24h at the target. These are conditional expenditure requirements, not available cash or forecasts. Buybacks and licenses are excluded to avoid counting assumed demand as measured demand.
'''), code('''required=[]
for half in [2,6,12,None]:
    for target in ['10% bounce','Reclaim 13:40 UTC reference','Reclaim 10:09 UTC reference']:
        lo,hi=0.,20.
        for _ in range(30):
            mid=(lo+hi)/2
            f=rm.simulate(e,rm.Scenario(hours=24,buy_multiple=mid,sell_half_life_hours=half))
            if f.iloc[-1].price < e['references'][target]:lo=mid
            else:hi=mid
        required.append(dict(selling_half_life='Persists' if half is None else f'{half}h',target=target,
            hourly_wallet_buy_eth=hi*e['buy_wallet_eth_hour'],multiple_of_observed=hi,
            total_wallet_buy_eth_24h=hi*e['buy_wallet_eth_hour']*24,
            target_time_utc=utc_at(e['timestamp'],24)))
required=pd.DataFrame(required);display(required.round(2))
required.to_csv(OUT/'required-buying.csv',index=False)
'''), md('''## 5. Validation and what would change the assessment

- Sustained net buying over several non-overlapping windows would support a recovery thesis more than a single positive five-minute candle.
- Actual fresh-funded license purchases matter. A sold-out auction funded internally does not establish new ETH demand.
- Successful buyback transactions matter; an idle vault balance is not buy pressure.
- Continuing declines in token sell volume favor seller exhaustion. Renewed large sales or branch withdrawals weaken that case.
- The earlier 10:09 and 13:40 prices are reference levels, not verified all-time highs. No full historical-top classification or statistical posterior is supplied.

The comparison is a short-horizon supplement, not a solved multiplayer equilibrium. It does not know seller cost bases, future capital arrivals, unobserved venue flows or catalysts. A bounce and an already-established earlier top are compatible.
'''), code('''audits=[]
for name,f in paths.items():
    audits.append(dict(scenario=name,max_eth_error=f.eth_error.abs().max(),max_token_error=f.token_error.abs().max(),
                       minimum_stock=f.outside_pool_token_bound.min(),minimum_vault=f.vault_eth.min()))
audit=pd.DataFrame(audits);display(audit)
audit.to_csv(OUT/'accounting-checks.csv',index=False)
base=rm.Scenario(sell_half_life_hours=6)
coarse=rm.simulate(e,base).iloc[-1].price
fine=rm.simulate(e,replace(base,dt=.05)).iloc[-1].price
reversed_order=rm.simulate(e,replace(base,sell_first=True)).iloc[-1].price
print('Final-price sensitivity to 3-minute steps:',fine/coarse-1)
print('Final-price sensitivity to sell-first order:',reversed_order/coarse-1)
assert audit.max_eth_error.max()<1e-6 and audit.max_token_error.max()<.02
metadata=dict(observation=rm.OBSERVATION,block=e['summary']['block'],block_hash=e['summary']['blockHash'],
    timestamp_utc=utc_at(e['timestamp']),calibrated_probabilities=False,scenarios=[asdict(c) for c in configs],
    source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['recovery_model.py','liquidity.py','time_display.py']},
    evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(e['folder'].glob('*.json'))},
    time_step_price_relative_difference=fine/coarse-1,execution_order_price_relative_difference=reversed_order/coarse-1)
(OUT/'metadata.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\\n')
''')]
nb = nbf.v4.new_notebook(cells=cells, metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11.6'}})
nbf.write(nb, root/'recovery_update.ipynb')
