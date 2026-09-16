"""Descriptive participant timing, execution sizes and conservative action labels.

History measures actions, not private motives. No fitted price probabilities.
"""
from collections import defaultdict
import json
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,key,ZERO,load,utc

def strategy(w,cutoff=None):
    if w.charter_count>0:return 'charter_owner'
    b,s=w.buy_tokens_6h,w.sell_tokens_6h
    if b>0 and s>0 and min(b,s)/max(b,s)>=.3:return 'two_way'
    if s>0:return 'recent_seller'
    if b>0:return 'recent_buyer'
    return 'inactive_holder'

def run(root=ROOT):
    out=root/'behavior-results';d=out/'participants';target=read(root/'behavior-evidence/target.json');pin=int(target['header']['timestamp'],16)
    w=pd.read_csv(d/'wallets.csv.gz');t=pd.read_csv(d/'trades.csv.gz');c=pd.read_csv(d/'charters.csv')
    w['strategy']=w.apply(strategy,axis=1)
    # Fresh observed native ETH only. Missing cash reads remain explicitly missing.
    w['cash_observed']=w.native_eth.notna();w['native_ETH_budget']=w.native_eth.fillna(0.)
    w.to_csv(out/'population.csv.gz',index=False)
    _,transfers,old_events=load(root)
    transfers=sorted(transfers+read(root/'behavior-evidence/delta-transfers.json.gz'),key=key)
    events=old_events+read(root/'behavior-evidence/delta-events.json.gz')
    grouped=defaultdict(list)
    for x in transfers:grouped[x['transactionHash']].append(x)
    txtrades={h:g for h,g in t.groupby('tx')};balances=defaultdict(int);fraction={}
    for h,logs in grouped.items():
        if h in txtrades:
            for x in txtrades[h].itertuples():
                pre=balances[x.address]/1e18
                if x.side=='sell' and pre>0 and x.tokens<=pre+1e-6:fraction[(h,x.address)]=min(1,x.tokens/pre)
        for x in logs:
            v=x['decoded'];a=v['from'].lower();b=v['to'].lower();q=int(v['value'])
            if a!=ZERO:balances[a]-=q
            if b!=ZERO:balances[b]+=q
    t['pre_inventory_sale_fraction']=[fraction.get((x.tx,x.address),np.nan) if x.side=='sell' else np.nan for x in t.itertuples()]
    t['strategy']=t.address.map(w.set_index('address').strategy)
    recent=t[t.timestamp>=pin-21600]
    for side in ['buy','sell']:
        counts=recent[recent.side==side].groupby('address').size()/6
        w[side+'_event_rate_hour']=w.address.map(counts).fillna(0.)
    fracs=recent[recent.side=='sell'].groupby('address').pre_inventory_sale_fraction.median()
    tickets=recent[recent.side=='buy'].groupby('address').pool_eth.mean()/.98
    w['sale_fraction_median']=w.address.map(fracs)
    w['buy_ticket_mean_ETH']=w.address.map(tickets)
    w.to_csv(out/'population.csv.gz',index=False)
    owners=set(c.owner);deposits=pd.read_csv(d/'bank-deposits.csv');depositors=set(deposits.depositor)
    # Association at a wallet is not sufficient evidence that a particular buy funded a license.
    t['action_label']=np.where(t.side=='sell','market_sale',np.where(t.address.isin(depositors),'buy_by_observed_bank_depositor_intent_uncertain',np.where(t.address.isin(owners),'buy_by_charter_owner_intent_uncertain','market_buy_no_observed_game_use')))
    cadence=[];rates=[]
    for group,pop in w.groupby('strategy'):
        histories=t[t.address.isin(pop.address)]
        for side in ['buy','sell']:
            h=histories[histories.side==side].sort_values('timestamp');gaps=h.groupby('address').timestamp.diff().dropna()/60
            first=h.groupby('address').timestamp.min();recent=h[h.timestamp>=pin-21600]
            # Positive inventory or known cash is the risk-set proxy; no fitted universal hazard.
            eligible=(pop.wallet_tokens>0)|(pop.native_ETH_budget>0)|(pop.sell_tokens_6h>0)|(pop.buy_tokens_6h>0)
            count=max(1,int(eligible.sum()));event_rate=len(recent)/(6*count)
            fr=recent.pre_inventory_sale_fraction.dropna()
            frac=float(fr.median()) if len(fr) else .5
            ticket=float(recent.pool_eth.median()/.98) if len(recent) else .1
            rates.append(dict(strategy=group,side=side,events_6h=len(recent),eligible_addresses=count,events_per_address_hour=event_rate,median_sell_fraction=frac,median_buy_wallet_ETH=ticket,notes='Snapshot-conditioned eligible-address proxy; endogenous/censored participation. Not a validated hazard.'))
            cadence.append(dict(strategy=group,side=side,trading_addresses=h.address.nunique(),repeat_gap_observations=len(gaps),repeat_gap_p25_minutes=float(gaps.quantile(.25)) if len(gaps) else None,repeat_gap_median_minutes=float(gaps.median()) if len(gaps) else None,repeat_gap_p75_minutes=float(gaps.quantile(.75)) if len(gaps) else None,single_trade_addresses=int((h.groupby('address').size()==1).sum()),median_sale_fraction=frac,full_exit_fraction_of_measured_sales=float((fr>=.99).mean()) if len(fr) else None))
    pd.DataFrame(rates).to_csv(out/'activity-calibration.csv',index=False);pd.DataFrame(cadence).to_csv(out/'cadence.csv',index=False)
    t.to_csv(out/'classified-trades.csv.gz',index=False)
    # First-sale survival includes wallets that have not yet sold, right-censored at the pin.
    acq=pd.read_csv(d/'acquisitions.csv.gz');acq['time']=pd.to_datetime(acq.timestamp_utc_approx,format='ISO8601',utc=True).astype('int64')/1e9
    first_acq=acq.groupby('address').time.min();first_sell=t[t.side=='sell'].groupby('address').timestamp.min()
    timing=[]
    for x in w.itertuples():
        if x.address not in first_acq:continue
        start=first_acq[x.address];end=first_sell.get(x.address,pin)
        if end<start-1:continue
        timing.append(dict(address=x.address,strategy=x.strategy,entry_utc=utc(start),duration_hours=max(0,(end-start)/3600),first_sale_observed=x.address in first_sell))
    survival=[];timing=pd.DataFrame(timing);timing.to_csv(out/'first-sale-observations.csv.gz',index=False)
    for group,g in timing.groupby('strategy'):
        surv=1.
        for h in np.arange(.25,26,.25):
            lo=h-.25;at=int((g.duration_hours>=lo).sum());n=int(((g.duration_hours>=lo)&(g.duration_hours<h)&g.first_sale_observed).sum())
            if at:surv*=1-n/at
            survival.append(dict(strategy=group,hours_since_first_receipt=h,at_risk=at,first_sales=n,descriptive_survival=surv))
    pd.DataFrame(survival).to_csv(out/'first-sale-survival.csv',index=False)
    # Non-overlapping 20-minute windows, separating new and repeat sellers/buyers.
    firstbuy=t[t.side=='buy'].groupby('address').timestamp.min();firstsell=t[t.side=='sell'].groupby('address').timestamp.min();windows=[]
    for left in np.arange(pin-21600,pin,1200):
        r=t[(t.timestamp>=left)&(t.timestamp<left+1200)];buys=r[r.side=='buy'];sells=r[r.side=='sell'];newbuy=buys[buys.address.map(firstbuy)>=left];newsell=sells[sells.address.map(firstsell)>=left]
        windows.append(dict(from_utc=utc(left),to_utc=utc(left+1200),buy_ETH=buys.pool_eth.sum(),sell_ETH=sells.pool_eth.sum(),sold_tokens=sells.tokens.sum(),new_seller_tokens=newsell.tokens.sum(),new_seller_addresses=newsell.address.nunique(),new_buyer_ETH=newbuy.pool_eth.sum()/.98,new_buyer_addresses=newbuy.address.nunique(),owner_buy_ETH=buys.loc[buys.address.isin(owners),'pool_eth'].sum()))
    windows=pd.DataFrame(windows);windows.to_csv(out/'flow-windows.csv',index=False)
    recent=t[t.timestamp>=pin-7200];new=recent[(recent.side=='buy')&(recent.address.map(firstbuy)>=pin-7200)]
    tickets=new.groupby('address').pool_eth.sum()/.98
    # Holdout diagnostic: prior hour's flow vs following hour, never a calibration success claim.
    diagnostic=[]
    for i in range(3,len(windows),3):
        train=windows.iloc[i-3:i];test=windows.iloc[i:i+3]
        if len(test)<3:continue
        for col in ['buy_ETH','sell_ETH','new_seller_tokens']:
            prediction=train[col].sum();actual=test[col].sum();diagnostic.append(dict(metric=col,forecast_from_utc=test.from_utc.iloc[0],predicted_next_hour=prediction,observed_next_hour=actual,absolute_error=abs(actual-prediction)))
    pd.DataFrame(diagnostic).to_csv(out/'persistence-holdout.csv',index=False)
    meta=dict(snapshot_utc=utc(pin),block=int(target['header']['number'],16),new_buyer_native_ETH_hour_last2h=new.pool_eth.sum()/2/.98,new_buyer_addresses_hour_last2h=new.address.nunique()/2,observed_new_buyer_tickets_ETH=tickets.to_list(),game_owner_addresses=len(owners),game_depositor_addresses=len(depositors),unknown_native_cash_addresses=int((~w.cash_observed).sum()),positive_wallet_tokens=w.wallet_tokens.sum(),wallet_native_ETH_observed=w.native_ETH_budget.sum(),limitations='Strategies describe observed actions, not identities or intent. Cadence among repeaters is selection-biased. Survival is descriptive under right censoring, not a future first-sale forecast. Activity rates use snapshot-conditioned risk sets and are scenario inputs; the persistence holdout exposes regime instability. Public wallet capital is capacity, not committed demand.')
    (out/'observation-metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({k:v for k,v in meta.items() if k!='observed_new_buyer_tickets_ETH'},indent=2))
    return meta

if __name__=='__main__':run()
