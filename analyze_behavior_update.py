"""Compare new observations to the frozen snapshot and unchanged model cases."""
import argparse,copy,json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,utc,key
from liquidity import ConcentratedPool
from reentry_model import allocate,price_buy_cost,buyback

def run(packet,base=ROOT):
    packet=Path(packet).resolve();e=packet/'evidence';out=packet/'results'
    target=read(e/'target.json');pin=int(target['header']['timestamp'],16);block=int(target['header']['number'],16)
    prev=read(base/'behavior-results/analysis-summary.json');oldtarget=read(base/'behavior-evidence/target.json');cut=int(oldtarget['header']['number'],16);start=int(oldtarget['header']['timestamp'],16)
    s={x['label']:x.get('value') for x in read(e/'state.json')};p=ConcentratedPool(read(e/'liquidity.json'),buy_tax=int(s['hook.buyTaxBps'])/10000,sell_tax=int(s['hook.sellTaxBps'])/10000)
    w=pd.read_csv(out/'population.csv.gz');t=pd.read_csv(out/'classified-trades.csv.gz');oldw=pd.read_csv(base/'behavior-results/population.csv.gz');c=pd.read_csv(out/'participants/charters.csv')
    oldset=set(oldw.loc[oldw.sell_tokens_6h>0,'address']);new=t[t.block>cut].copy();sells=new[new.side=='sell'];buys=new[new.side=='buy'];first=t[t.side=='sell'].groupby('address').block.min()
    sellers=w[w.sell_tokens_6h>0];fixed=w[w.address.isin(oldset)];oldstock=oldw.loc[oldw.address.isin(oldset),'wallet_tokens'].sum()
    stock=w[['address','strategy','wallet_tokens','sell_tokens_6h','charter_count','first_pool_buy_utc_approx']].copy();stock['previous_seller_group']=stock.address.isin(oldset)
    for col in [x for x in w.columns if x.startswith('inventory_')]:stock[col]=w[col]
    stock.sort_values('wallet_tokens',ascending=False).to_csv(out/'seller-inventory-and-entry.csv',index=False)
    events=sorted([x for x in read(e/'delta-events.json.gz') if int(x['blockNumber'],16)>cut],key=key);swaps=[x for x in events if x['event']=='Swap']
    buy=sum(-int(x['decoded']['amount0'])/1e18 for x in swaps if int(x['decoded']['amount0'])<0);sell=sum(int(x['decoded']['amount0'])/1e18 for x in swaps if int(x['decoded']['amount0'])>0)
    # Exact block-based split, rather than an interpolated-time boundary.
    new_seller_volume=sells.loc[sells.address.map(first)>cut,'tokens'].sum();replacement=sells.loc[~sells.address.isin(oldset),'tokens'].sum()
    headers={int(h['number'],16):int(h['timestamp'],16) for h in read(e/'headers.json')};headers[cut]=start;hs=sorted(headers)
    actual=[dict(hours=0,elapsed_days=0,timestamp_utc=utc(start),price_ETH=prev['price_ETH'],price_return=0,block=cut)]
    for x in swaps:
        b=int(x['blockNumber'],16);stamp=float(np.interp(b,hs,[headers[k] for k in hs]));price=2**192/int(x['decoded']['sqrtPriceX96'])**2
        actual.append(dict(hours=(stamp-start)/3600,elapsed_days=(stamp-start)/86400,timestamp_utc=utc(stamp),price_ETH=price,price_return=price/prev['price_ETH']-1,block=b))
    actual.append(dict(hours=(pin-start)/3600,elapsed_days=(pin-start)/86400,timestamp_utc=utc(pin),price_ETH=p.price,price_return=p.price/prev['price_ETH']-1,block=block))
    pd.DataFrame(actual).to_csv(out/'observed-since-previous.csv',index=False)
    topbuyers=buys.groupby('address').agg(buy_ETH=('pool_eth','sum'),tokens_bought=('tokens','sum')).join(w.set_index('address')[['wallet_tokens','charter_count','strategy']]).sort_values('buy_ETH',ascending=False)
    topbuyers.to_csv(out/'interval-buyers.csv')
    sells.groupby('address').agg(sell_ETH=('pool_eth','sum'),tokens_sold=('tokens','sum')).join(w.set_index('address')[['wallet_tokens','charter_count','strategy']]).sort_values('sell_ETH',ascending=False).to_csv(out/'interval-sellers.csv')
    oldpaths=pd.read_csv(base/'behavior-results/scenario-paths.csv.gz');comparison=[]
    elapsed=(pin-start)/3600
    for (case,seed),g in oldpaths.groupby(['case','seed'],sort=False):
        if elapsed>g.hours.max():continue
        pred=float(np.interp(elapsed,g.hours,g.price_return));comparison.append(dict(case=case,seed=seed,hours=elapsed,timestamp_utc=utc(pin),previous_path_return_at_new_pin=pred,observed_return=p.price/prev['price_ETH']-1,error_percentage_points=100*(pred-(p.price/prev['price_ETH']-1))))
    pd.DataFrame(comparison).to_csv(out/'previous-path-check.csv',index=False)
    vault=int(s['balance.contractionVault'])/1e18;depth=int(s['vault.poolEthDepth'])/1e18
    cases=[]
    for h in [1,6,12,24]:
        pool=copy.deepcopy(p);q,_=pool.buy(1);spent=buyback(pool,vault,depth,p.price,h)
        cases.append(dict(hours=h,elapsed_days=h/24,timestamp_utc=utc(pin+h*3600),buyback_ETH=spent,spot_change=pool.price/p.price-1,one_ETH_entry_net_return=pool.quote_sell(q)-1))
    pd.DataFrame(cases).to_csv(out/'buyback-only-trade.csv',index=False)
    hurdles=[]
    for fraction in [0,.25,.5,1]:
        for target_return in [0,.1,.25,.5,1]:
            pool=copy.deepcopy(p);pool.sell(sellers.wallet_tokens.sum()*fraction)
            hurdles.append(dict(fraction_recent_seller_stock_sold=fraction,target_spot_return=target_return,required_gross_buyer_ETH=price_buy_cost(pool,p.price*(1+target_return))))
    pd.DataFrame(hurdles).to_csv(out/'recovery-flow-requirements.csv',index=False)
    issuance=int(s['bank.baseIssuancePerDay'])/1e18*int(s['bank.multiplierWad'])/1e18+int(s['bank.recycleRate'])/1e18*86400
    reset=int(s['license.auctionAnchor'])+(int(s['license.currentDay'])+1)*86400
    projected=c.copy();projected.pending_tokens+=issuance*(reset-pin)/86400*projected.branches/projected.branches.sum()
    next_price=2*int(s['license.lastSalePrice'])/1e18
    alloc=allocate(projected,w,next_price,int(s['license.licensesPerDay']),{})
    alloc.to_csv(out/'next-day-license-feasibility.csv',index=False)
    funding=read(out/'interval-funding/followup-summary.json');windows=pd.read_csv(out/'flow-windows.csv');last=windows.iloc[-1]
    cohort=w.groupby('strategy').agg(addresses=('address','size'),tokens=('wallet_tokens','sum'),native_ETH=('native_ETH_budget','sum'),sold_tokens_6h=('sell_tokens_6h','sum'));cohort.to_csv(out/'strategy-stocks.csv')
    # Exact fixed-group inventory bridge using transfers, including acquisitions.
    transfer_in=transfer_out=0
    for x in read(e/'delta-transfers.json.gz'):
        if int(x['blockNumber'],16)<=cut:continue
        a=x['decoded']['from'].lower();b=x['decoded']['to'].lower();q=int(x['decoded']['value'])/1e18
        if a not in oldset and b in oldset:transfer_in+=q
        if a in oldset and b not in oldset:transfer_out+=q
    bridge_error=fixed.wallet_tokens.sum()-(oldstock+transfer_in-transfer_out)
    assert abs(bridge_error)<1e-5
    summary=dict(snapshot_utc=utc(pin),previous_snapshot_utc=utc(start),block=block,block_hash=target['header']['hash'],elapsed_hours=elapsed,price_ETH=p.price,price_change_since_previous=p.price/prev['price_ETH']-1,pool_principal_ETH=p.available_eth,pool_principal_tokens=p.real_tokens,buy_ETH=buy,sell_ETH=sell,net_pool_ETH=buy-sell,attributed_buy_ETH=buys.pool_eth.sum(),attributed_sell_ETH=sells.pool_eth.sum(),new_first_seller_share=new_seller_volume/sells.tokens.sum() if len(sells) else 0,outside_previous_seller_group_share=replacement/sells.tokens.sum() if len(sells) else 0,previous_seller_group_initial_tokens=oldstock,previous_seller_group_current_tokens=fixed.wallet_tokens.sum(),previous_seller_group_inflows=transfer_in,previous_seller_group_outflows=transfer_out,fixed_group_bridge_error=bridge_error,six_hour_seller_addresses=len(sellers),six_hour_sellers_empty=int((sellers.wallet_tokens<1e-9).sum()),six_hour_seller_remaining_tokens=sellers.wallet_tokens.sum(),wallet_tokens=w.wallet_tokens.sum(),bank_pending=float(c.pending_tokens.sum()),branches=int(c.branches.sum()),live_charters=len(c),remaining_licenses=int(s['license.remainingToday']),new_licenses=funding['new_licenses'],license_cost_tokens=funding['license_cost_tokens'],new_market_funded_license_tokens=funding['license_paid_from_new_canonical_tokens'],new_market_funded_license_share=funding['license_paid_from_new_canonical_tokens']/funding['license_cost_tokens'],new_withdrawals=funding['new_withdrawals'],buyback_vault_ETH=vault,buyback_last_tick=int(s['vault.lastTickAt']),first_tick_ETH=min(vault*.1,depth*.002),hook_ETH=int(s['balance.taxHook'])/1e18,next_license_reset_utc=utc(reset),next_opening_price_if_no_parameter_changes=next_price,next_day_feasible_fresh_tokens=alloc.new_tokens_needed.sum(),next_day_all_fresh_ETH=p.quote_buy(next_price*100),branch_daily_tokens=issuance/c.branches.sum(),latest20m_buy_ETH=last.buy_ETH,latest20m_sell_ETH=last.sell_ETH,latest20m_first_seller_share=last.new_seller_tokens/last.sold_tokens if last.sold_tokens else 0,ETH_Charters_per_day=int(s['charter.chartersPerDay']))
    oldpool=ConcentratedPool(read(base/'behavior-evidence/liquidity.json'));hypothetical_tokens,_=oldpool.buy(1.)
    summary['previous_one_ETH_entry_net_return_now']=p.quote_sell(hypothetical_tokens)-1
    summary['liquidity_modification_events']=sum(x['event']=='ModifyLiquidity' for x in events)
    latest_swaps=[x for x in swaps if np.interp(int(x['blockNumber'],16),hs,[headers[k] for k in hs])>=pin-1200]
    summary['latest20m_all_pool_buy_ETH']=sum(-int(x['decoded']['amount0'])/1e18 for x in latest_swaps if int(x['decoded']['amount0'])<0)
    summary['latest20m_all_pool_sell_ETH']=sum(int(x['decoded']['amount0'])/1e18 for x in latest_swaps if int(x['decoded']['amount0'])>0)
    summary['largest_attributed_buyer_ETH']=float(topbuyers.buy_ETH.iloc[0]);summary['largest_attributed_buyer']=topbuyers.index[0]
    summary['largest_buyer_share_of_attributed_buy_ETH']=float(topbuyers.buy_ETH.iloc[0]/buys.pool_eth.sum())
    peak=max(actual,key=lambda x:x['price_ETH']);summary['interval_peak_return']=peak['price_return'];summary['interval_peak_utc_approx']=peak['timestamp_utc'];summary['drawdown_from_interval_peak']=p.price/peak['price_ETH']-1
    for item in read(e/'milestone-headers.json'):
        summary[item['label']+'_utc_exact']=utc(int(item['response']['result']['timestamp'],16))
    (out/'update-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('packet');a=p.parse_args();run(a.packet)
