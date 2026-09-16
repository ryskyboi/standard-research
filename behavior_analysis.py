"""Saved-data diagnostics, funding bounds and executable marginal exit worksheets."""
import copy,json
import numpy as np
import pandas as pd
from behavior_model import Economy
from participant_flows import ROOT,read,utc
from reentry_model import allocate,price_buy_cost,buyback

def run(root=ROOT):
    out=root/'behavior-results';e=Economy(root=root);w=pd.read_csv(out/'population.csv.gz')
    c=pd.read_csv(out/'participants/charters.csv');used=dict(zip(e.ids,e.used))
    allocation=allocate(c,w,e.license_price(),e.quota-e.sold,used)
    allocation.to_csv(out/'remaining-license-feasibility.csv',index=False)
    sellers=w[w.sell_tokens_6h>0]
    # Buy-side budgets required to restore price after fractions of the observed stock sell.
    hurdles=[]
    for fraction in [0,.25,.5,1.]:
        for lift in [0,.1,.25,.5,1.]:
            p=copy.deepcopy(e.pool);cash,_,_=p.sell(sellers.wallet_tokens.sum()*fraction)
            needed=price_buy_cost(p,e.start_price*(1+lift))
            hurdles.append(dict(fraction_recent_seller_stock_sold=fraction,target_spot_return=lift,seller_net_ETH=cash,required_gross_buyer_ETH=needed))
    pd.DataFrame(hurdles).to_csv(out/'recovery-flow-requirements.csv',index=False)
    bb=[]
    for hours in [1,6,12,24]:
        p=copy.deepcopy(e.pool);qty,_=p.buy(1.)
        spent=buyback(p,e.vault,e.vault_depth,e.start_price,hours)
        proceeds=p.quote_sell(qty)
        bb.append(dict(hours=hours,elapsed_days=hours/24,timestamp_utc=utc(e.pin+hours*3600),buyback_spent_ETH=spent,spot_return=p.price/e.start_price-1,one_ETH_entry_net_return=proceeds-1))
    pd.DataFrame(bb).to_csv(out/'buyback-only-trade.csv',index=False)
    cohort=w.groupby('strategy').agg(addresses=('address','size'),positive_token_addresses=('wallet_tokens',lambda v:int((v>0).sum())),tokens=('wallet_tokens','sum'),native_ETH_observed=('native_ETH_budget','sum'),bought_tokens_6h=('buy_tokens_6h','sum'),sold_tokens_6h=('sell_tokens_6h','sum'))
    cohort.to_csv(out/'strategy-stocks.csv')
    paths=pd.read_csv(out/'scenario-paths.csv.gz');p=copy.deepcopy(e.pool);entry_tokens,_=p.buy(1.)
    rows=[]
    for (case,seed),g in paths.groupby(['case','seed'],sort=False):
        for h in [0,1,3,6,12,24]:
            r=g.iloc[(g.hours-h).abs().argmin()];sqrt=1/np.sqrt(r.price_ETH)
            rows.append(dict(case=case,seed=seed,hours=r.hours,elapsed_days=r.hours/24,timestamp_utc=r.timestamp_utc,existing_10000_tokens_net_ETH=float(e.pool.curve.sell_quotes(sqrt,10000,lp_fee=e.pool.lp_fee,sell_tax=e.pool.sell_tax)),new_one_ETH_entry_net_return=float(e.pool.curve.sell_quotes(sqrt,entry_tokens,lp_fee=e.pool.lp_fee,sell_tax=e.pool.sell_tax))-1))
    pd.DataFrame(rows).to_csv(out/'precommitted-exit-worksheet.csv',index=False)
    s=e.s;meta=dict(snapshot_utc=utc(e.pin),block=int(read(root/'behavior-evidence/target.json')['header']['number'],16),price_ETH=e.start_price,pool_principal_ETH=e.pool.available_eth,pool_principal_tokens=e.pool.real_tokens,non_protocol_wallet_tokens=w.wallet_tokens.sum(),six_hour_seller_addresses=len(sellers),six_hour_sellers_empty=int((sellers.wallet_tokens<1e-9).sum()),six_hour_seller_remaining_tokens=sellers.wallet_tokens.sum(),bank_pending=e.ledger.sum(),branches=int(e.n.sum()),live_charters=len(c),owners=len(set(c.owner)),remaining_daily_licenses=e.quota-e.sold,current_license_price=e.license_price(),remaining_licenses_feasible_fresh_tokens=float(allocation.new_tokens_needed.sum()),remaining_licenses_all_fresh_ETH=e.pool.quote_buy((e.quota-e.sold)*e.license_price()),buyback_vault_ETH=e.vault,buyback_last_tick=int(s['vault.lastTickAt']),first_tick_ETH=min(e.vault*.1,e.vault_depth*.002),hook_ETH=e.hook,POL_ETH=e.pol,expansion_ETH=e.expansion,epoch_end_utc=utc(e.pin+e.epoch_end*3600),next_license_reset_utc=utc(e.anchor+(e.day+1)*86400),small_trade_round_trip_spot_hurdle=1/((1-e.pool.buy_tax)*(1-e.pool.lp_fee)**2*(1-e.pool.sell_tax))-1,activation_rate_hour=e.activation_rate,analysis_limits='Funding allocation is feasibility, not a predicted auction. Marginal exit worksheet quotes small independent orders on saved paths; it does not resimulate the crowd or claim an attainable optimal date. Buyback-only case assumes successful hourly owner execution with no other trades. Locked liquidity remains in the curve; its ETH can still be sold against.')
    (out/'analysis-summary.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))

if __name__=='__main__':run()
