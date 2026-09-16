"""Track fixed seller cohorts, replacement selling and acquisition provenance.

Run offline against saved polls. No calibrated stopping-time probability is claimed.
Remaining inventory lineage is pro-rata; entry dates describe observed addresses.
"""
from collections import defaultdict
import json
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,key,utc,ZERO,POOL,POL,SECONDARY,KINDS,transferred

def inventory_bridge(transfers,cohort,after_block):
    incoming=outgoing=0
    for x in transfers:
        if int(x['blockNumber'],16)<=after_block:continue
        d=x['decoded'];a=d['from'].lower();b=d['to'].lower();q=int(d['value'])
        # Transfers inside the fixed group do not change its aggregate inventory.
        if a not in cohort and b in cohort:incoming+=q
        if a in cohort and b not in cohort:outgoing+=q
    return incoming/1e18,outgoing/1e18

def run(root=ROOT):
    monitor=root/'seller-monitor';folders=sorted(p for p in monitor.iterdir() if p.is_dir() and (p/'target.json').exists() and read(p/'target.json')['status']=='complete')
    if not folders:raise ValueError('No completed polls')
    seed=read(root/'reentry-evidence/target.json');expected=int(seed['header']['number'],16)
    transfers=[];events=[];secondary=[];anchors={expected:int(seed['header']['timestamp'],16)}
    for p in folders:
        target=read(p/'target.json');assert target['previousBlock']==expected,'Non-contiguous poll history'
        expected=int(target['header']['number'],16);anchors[expected]=int(target['header']['timestamp'],16)
        transfers+=read(p/'transfers.json.gz');events+=read(p/'events.json.gz');secondary+=read(p/'secondary.json.gz')
    target=read(folders[-1]/'target.json');pin=int(target['header']['timestamp'],16);block=int(target['header']['number'],16)
    s={x['label']:x['value'] for x in read(folders[-1]/'state.json')}
    # Additional exact intermediate header improves first-poll interpolation.
    prior=read(root/'buyback-seller-evidence/target.json');pb=int(prior['header']['number'],16);pt=int(prior['header']['timestamp'],16)
    if min(anchors)<pb<max(anchors):anchors[pb]=pt
    bs=np.array(sorted(anchors));ts=np.array([anchors[x] for x in bs]);timestamp=lambda b:float(np.interp(b,bs,ts))
    custody={a.lower() for a in read(root/'notebook-evidence/home.json')['contracts'].values()}|{ZERO,POOL,POL}|SECONDARY
    balance=defaultdict(int);mix=defaultdict(lambda:np.zeros(len(KINDS)))
    for x in read(root/'reentry-evidence/wallet-balances.json'):
        if x['label'].endswith('.token'):balance[x['label'][:-6]]=int(x['value'])
    for a,b in balance.items():mix[a][6]=b/1e18
    oldwallet=pd.read_csv(root/'reentry-results/participants/wallets.csv.gz')
    for x in oldwallet.to_dict('records'):mix[x['address']]=np.array([x['inventory_'+k] for k in KINDS])
    bytx=defaultdict(list);evtx=defaultdict(list);othertx=defaultdict(list)
    for x in sorted(transfers,key=key):bytx[x['transactionHash']].append(x)
    for x in events:evtx[x['transactionHash']].append(x)
    for x in secondary:othertx[x['transactionHash']].append(x)
    trades=[];acquisitions=[];unresolved=[]
    for h,logs in bytx.items():
        es=evtx[h];swaps=[x for x in es if x['event']=='Swap'];withdraw=any(x['event'] in ['Withdrawn','Revoked'] for x in es)
        b=int(logs[0]['blockNumber'],16);moment=timestamp(b)
        net=defaultdict(int)
        for x in logs:
            d=x['decoded'];net[d['from'].lower()]-=int(d['value']);net[d['to'].lower()]+=int(d['value'])
        pos={a:q for a,q in net.items() if q>0};neg={a:-q for a,q in net.items() if q<0}
        sides={'buy' if int(x['decoded']['amount1'])>0 else 'sell' for x in swaps};side=next(iter(sides)) if len(sides)==1 else None
        qswap=sum(abs(int(x['decoded']['amount1'])) for x in swaps);eth=sum(abs(int(x['decoded']['amount0'])) for x in swaps)/1e18
        actors={a:q for a,q in (pos if side=='buy' else neg).items() if a not in custody} if side else {}
        opposite={a:q for a,q in (neg if side=='buy' else pos).items() if a not in custody} if side else {}
        lp=any(x['event']=='ModifyLiquidity' for x in es)
        accepted=bool(swaps and side and not opposite and sum(actors.values())==qswap and not lp)
        if not accepted and swaps and side and len(actors)==1 and sum(actors.values())>=qswap and not lp:
            a=next(iter(actors))
            if (side=='sell' and set(neg)=={a} and net.get(POOL,0)==qswap) or (side=='buy' and set(pos)=={a} and net.get(POOL,0)==-qswap):accepted=True;actors={a:qswap}
        outgoing={};combined=np.zeros(len(KINDS));total=sum(neg.values())/1e18
        for a,q in neg.items():
            if a==ZERO:
                v=np.zeros(len(KINDS));v[2 if withdraw else 6]=q/1e18
            elif a in {POOL}|SECONDARY:
                v=np.zeros(len(KINDS));v[6]=q/1e18
                legs=[x for x in othertx[h] if x['address'].lower()==a]
                if legs and all(int(x['decoded']['amount1'])<0 for x in legs) and sum(-int(x['decoded']['amount1']) for x in legs)==q:v[7]=q/1e18;v[6]=0
                assert balance[a]>=q
                if balance[a]:mix[a]*=max(0,1-q/balance[a])
            else:
                assert balance[a]>=q,(a,h,balance[a],q)
                v=mix[a]*(q/balance[a]) if balance[a] else np.zeros(len(KINDS));mix[a]-=v
            outgoing[a]=v;combined+=v if a in SECONDARY and v[7]>0 else transferred(v)
        for a,q in pos.items():
            if a==ZERO:continue
            qty=q/1e18
            if accepted and side=='buy' and a in actors:
                direct=actors[a]/1e18;v=np.zeros(len(KINDS));v[0]=direct
                if qty>direct:
                    other=sum((vv if aa in SECONDARY and vv[7]>0 else transferred(vv) for aa,vv in outgoing.items() if aa!=POOL),start=np.zeros(len(KINDS)))
                    if other.sum():v+=other*((qty-direct)/other.sum())
                    else:v[6]+=qty-direct
            else:
                v=combined*(qty/total) if total else np.zeros(len(KINDS))
                if set(neg)=={ZERO}:v=np.zeros(len(KINDS));v[2 if withdraw else 6]=qty
            mix[a]+=v
            if a not in custody:acquisitions.append(dict(address=a,timestamp=moment,tokens=qty))
        for a,q in net.items():
            if a==ZERO:continue
            balance[a]+=q;assert balance[a]>=0
            assert abs(mix[a].sum()-balance[a]/1e18)<.002,(a,'source reconciliation')
        if accepted:
            for a,q in actors.items():
                row=dict(address=a,side=side,tokens=q/1e18,pool_eth=eth*q/qswap,block=b,timestamp=moment,tx=h)
                if side=='sell':row.update(dict(zip(KINDS,outgoing[a]*(q/neg[a]))))
                trades.append(row)
        elif swaps:unresolved.append(dict(tx=h,block=b,pool_ETH=eth))
    assert sum(balance.values())==int(s['token.totalSupply'])
    t=pd.concat([pd.read_csv(root/'reentry-results/participants/trades.csv.gz'),pd.DataFrame(trades)],ignore_index=True)
    acq=pd.read_csv(root/'reentry-results/participants/acquisitions.csv.gz')
    acq['timestamp']=pd.to_datetime(acq.timestamp_utc_approx,format='ISO8601',utc=True).astype('int64')/1e9
    acq=pd.concat([acq[['address','timestamp','tokens']],pd.DataFrame(acquisitions)],ignore_index=True)
    first=acq.groupby('address').timestamp.min();first_buy=t[t.side=='buy'].groupby('address').timestamp.min()
    recent=t[(t.side=='sell')&(t.timestamp>=pin-21600)]
    sellers=recent.groupby('address').agg(sold_6h=('tokens','sum'),sell_ETH_6h=('pool_eth','sum'))
    genesis=int(read(root/'notebook-evidence/home.json')['snapshot']['bank']['genesisTime'])
    rows=[]
    for a,x in sellers.iterrows():
        buys=t[(t.address==a)&(t.side=='buy')];hist=t[(t.address==a)&(t.side=='sell')]
        age=first.get(a,np.nan);entry=(age-genesis)/3600
        phase='unknown' if not np.isfinite(entry) else ('first_hour' if entry<1 else 'hours_1_to_6' if entry<6 else 'hours_6_to_18' if entry<18 else 'after_hour_18')
        short=t[(t.address==a)&(t.timestamp>=pin-1200)];sold20=short.loc[short.side=='sell','tokens'].sum();bought20=short.loc[short.side=='buy','tokens'].sum()
        remaining=balance[a]/1e18;netpace=(sold20-bought20)*3
        row=dict(address=a,remaining_tokens=remaining,first_observed_receipt_utc=utc(age) if np.isfinite(age) else '',first_canonical_buy_utc=utc(first_buy[a]) if a in first_buy else '',entry_phase=phase,canonical_buy_tokens_lifetime=buys.tokens.sum(),canonical_buy_pool_ETH_lifetime=buys.pool_eth.sum(),canonical_entry_pool_VWAP_ETH=buys.pool_eth.sum()/buys.tokens.sum() if buys.tokens.sum() else np.nan,sold_tokens_6h=x.sold_6h,sell_ETH_6h=x.sell_ETH_6h,sold_tokens_20m=sold20,bought_tokens_20m=bought20,net_sale_pace_tokens_hour_20m=netpace,constant_net_sale_pace_hours_to_empty=remaining/netpace if netpace>0 and remaining>0 else np.nan,last_sell_utc=utc(hist.timestamp.max()),current_own_canonical_purchase_tokens=mix[a][0],current_transferred_market_purchase_tokens=mix[a][1]+mix[a][8],current_own_other_pool_purchase_tokens=mix[a][7],current_branch_withdrawal_tokens=mix[a][2]+mix[a][3],current_other_tokens=mix[a][4]+mix[a][5]+mix[a][6])
        rows.append(row)
    wallets=pd.DataFrame(rows).sort_values('remaining_tokens',ascending=False)
    fixed=set(pd.read_csv(root/'buyback-seller-results/sellers-6h.csv').address);initial=read(root/'buyback-seller-results/summary.json')['recent_seller_inventory']
    fixed_remaining=sum(balance[a]/1e18 for a in fixed);incoming,outgoing=inventory_bridge(transfers,fixed,pb)
    assert abs(initial+incoming-outgoing-fixed_remaining)<1e-6
    since=t[t.block>pb];new_sellers=set(since.loc[since.side=='sell','address'])-fixed
    replacement_stock=sum(balance[a]/1e18 for a in new_sellers)
    windows=[]
    for hours in [1/3,1,2,6]:
        cutoff=pin-hours*3600;recent_t=t[t.timestamp>=cutoff]
        sells=recent_t[recent_t.side=='sell'];buys=recent_t[recent_t.side=='buy']
        group=set(sells.address);known=sum(balance[a]/1e18 for a in group)
        before=set(t[(t.side=='sell')&(t.timestamp<cutoff)].address);new=group-before
        windows.append(dict(window_hours=hours,sold_tokens=sells.tokens.sum(),bought_tokens=buys.tokens.sum(),sell_pool_ETH=sells.pool_eth.sum(),buy_pool_ETH=buys.pool_eth.sum(),net_pool_ETH=buys.pool_eth.sum()-sells.pool_eth.sum(),seller_addresses=len(group),new_first_time_sellers=len(new),new_first_time_seller_tokens=sells.loc[sells.address.isin(new),'tokens'].sum(),remaining_inventory=known,constant_gross_sale_pace_hours_to_clear=known/(sells.tokens.sum()/hours) if sells.tokens.sum() else None))
    phases=wallets.groupby('entry_phase').agg(addresses=('address','count'),remaining_tokens=('remaining_tokens','sum'),sold_tokens_6h=('sold_tokens_6h','sum'),sold_tokens_20m=('sold_tokens_20m','sum')).reset_index()
    out=folders[-1]/'analysis';out.mkdir(exist_ok=True)
    wallets.to_csv(out/'sellers.csv',index=False);phases.to_csv(out/'entry-cohorts.csv',index=False);pd.DataFrame(windows).to_csv(out/'flow-windows.csv',index=False)
    t[t.timestamp>=pin-86400].to_csv(out/'recent-trades.csv.gz',index=False)
    pd.DataFrame(unresolved).to_csv(out/'unresolved.csv',index=False)
    fixed_sales=since.loc[(since.side=='sell')&since.address.isin(fixed),'tokens'].sum()
    fixed_buys=since.loc[(since.side=='buy')&since.address.isin(fixed),'tokens'].sum()
    delta_minutes=(pin-pt)/60;net_drain=(initial-fixed_remaining)/(delta_minutes/60)
    top=wallets.head(10)[['address','remaining_tokens','entry_phase','first_observed_receipt_utc','first_canonical_buy_utc','sold_tokens_20m','bought_tokens_20m','constant_net_sale_pace_hours_to_empty']]
    top.to_csv(out/'watchlist.csv',index=False)
    allswap=[x for x in events if x['event']=='Swap'];gross=sum(abs(int(x['decoded']['amount0']))/1e18 for x in allswap)
    meta=dict(timestamp_utc=utc(pin),block=block,block_hash=target['header']['hash'],price_ETH=2**192/int(s['slot0'][0])**2,source_inventory_reconciled=True,total_supply_reconciled=True,recent_seller_addresses=len(wallets),recent_sellers_empty=int((wallets.remaining_tokens<1e-9).sum()),recent_seller_inventory=wallets.remaining_tokens.sum(),fixed_cohort_start_utc=utc(pt),fixed_cohort_initial_tokens=initial,fixed_cohort_remaining_tokens=fixed_remaining,fixed_cohort_incoming_tokens=incoming,fixed_cohort_outgoing_tokens=outgoing,fixed_cohort_net_drain_tokens_hour=net_drain,fixed_cohort_canonical_sold_tokens=fixed_sales,fixed_cohort_canonical_bought_tokens=fixed_buys,fixed_cohort_other_net_outgoing_tokens=outgoing-incoming-fixed_sales+fixed_buys,fixed_cohort_constant_net_drain_hours_to_empty=fixed_remaining/net_drain if net_drain>0 else None,fixed_cohort_constant_net_drain_empty_utc=utc(pin+fixed_remaining/net_drain*3600) if net_drain>0 else None,new_seller_addresses_since_fixed_snapshot=len(new_sellers),new_seller_remaining_inventory=replacement_stock,new_seller_tokens_sold_since_fixed_snapshot=since.loc[(since.side=='sell')&since.address.isin(new_sellers),'tokens'].sum(),buyback_vault_ETH=int(s['vaultETH'])/1e18,last_buyback_timestamp=int(s['vault.lastTickAt']),new_buyback_events=sum(x['event']=='BuybackExecuted' for x in events),delta_attribution_fraction=1-sum(x['pool_ETH'] for x in unresolved)/gross if gross else 1,entry_cohorts=phases.to_dict('records'),inventory_sources={k:wallets[k].sum() for k in wallets.columns if k.startswith('current_')},limitations='Entry dates are first observed receipts or first canonical purchases at an address; transferred tokens can have older economic owners. Pool-side lifetime VWAP excludes buy tax, router/gas, secondary basis and basis allocation to remaining units: not profit/loss. Source mix uses pro-rata accounting. Constant-pace empty times assume unchanged net drain and zero replacement cohorts; they are mechanical illustrations, not forecasts. Transfers can relocate selling capacity without selling. No persistent background alert service is implied.')
    (out/'summary.json').write_text(json.dumps(meta,indent=2,default=lambda x:x.item())+'\n')
    (monitor/'latest.json').write_text(json.dumps({'snapshot':str(folders[-1].relative_to(root)),'timestamp_utc':utc(pin),'block':block},indent=2)+'\n')
    print(json.dumps(meta,indent=2,default=lambda x:x.item()));return meta

if __name__=='__main__':run()
