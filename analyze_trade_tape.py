"""Canonical STANDARD tape: transaction runs, material flows and address concentration.

Addresses are token sources/recipients, not verified people. Times between saved
headers are interpolated; block order and amounts are exact chain observations.
"""
from collections import defaultdict
import json
import numpy as np
import pandas as pd
from participant_flows import ROOT, read, key, utc, POOL, POL, ZERO, SECONDARY

UPDATE = 'behavior-updates/2026-09-16T054047Z'

def runs(frame, threshold=0):
    f=frame[frame.gross_eth>=threshold].copy()
    if f.empty:return pd.DataFrame()
    f['run']=(f.side!=f.side.shift()).cumsum()
    rows=[]
    for _,g in f.groupby('run',sort=False):
        by=g[g.actor!=''].groupby('actor').gross_eth.sum().sort_values(ascending=False)
        rows.append(dict(side=g.side.iloc[0],transactions=len(g),eth=g.gross_eth.sum(),
            start_utc=utc(g.timestamp.iloc[0]),end_utc=utc(g.timestamp.iloc[-1]),
            seconds=g.timestamp.iloc[-1]-g.timestamp.iloc[0],
            addresses=g.loc[g.actor!='','actor'].nunique(),attributed_eth=by.sum(),
            top_address=by.index[0] if len(by) else '',top_address_eth=by.iloc[0] if len(by) else 0,
            first_tx=g.tx.iloc[0],last_tx=g.tx.iloc[-1],threshold_eth=threshold))
    return pd.DataFrame(rows)

def actor_for(es, ts, custody):
    swaps=[e for e in es if e['event']=='Swap']
    sides={'buy' if int(e['decoded']['amount1'])>0 else 'sell' for e in swaps}
    if len(sides)!=1 or any(e['event']=='ModifyLiquidity' for e in es):return ''
    side=next(iter(sides));net=defaultdict(int)
    for t in ts:
        d=t['decoded'];q=int(d['value']);net[d['from'].lower()]-=q;net[d['to'].lower()]+=q
    positive={a:q for a,q in net.items() if q>0};negative={a:-q for a,q in net.items() if q<0}
    actors={a:q for a,q in (positive if side=='buy' else negative).items() if a not in custody}
    opposite={a:q for a,q in (negative if side=='buy' else positive).items() if a not in custody}
    qswap=sum(abs(int(e['decoded']['amount1'])) for e in swaps)
    if len(actors)!=1:return ''
    a=next(iter(actors))
    if not opposite and sum(actors.values())==qswap:return a
    if actors[a]>=qswap:
        if side=='sell' and set(negative)=={a} and net.get(POOL,0)==qswap:return a
        if side=='buy' and set(positive)=={a} and net.get(POOL,0)==-qswap:return a
    return ''

def main():
    out=ROOT/'tape-results';out.mkdir(exist_ok=True)
    fresh=read(ROOT/'tape-evidence/tape.json');base=ROOT/UPDATE/'evidence'
    start=64168224
    events=sorted([x for x in read(base/'delta-events.json.gz')+fresh['events'] if int(x['blockNumber'],16)>start and x['event'] in ['Swap','ModifyLiquidity']],key=key)
    transfers=[x for x in read(base/'delta-transfers.json.gz')+fresh['transfers'] if int(x['blockNumber'],16)>start]
    headers=read(base/'headers.json')+fresh['headers']
    headers += [x['response']['result'] for x in read(base/'milestone-headers.json')]
    details=read(ROOT/'tape-evidence/details.json') if (ROOT/'tape-evidence/details.json').exists() else []
    headers += [x['response']['result'] for x in details if x['request']['method']=='eth_getBlockByNumber']
    envelopes={x['response']['result']['hash']:x['response']['result'] for x in details if x['request']['method']=='eth_getTransactionByHash'}
    # Additional saved exact headers take precedence over interpolation.
    for x in read(ROOT/'seller-origin-evidence/raw.json.gz'):
        if x['request']['method']=='eth_getBlockByNumber' and x['response'].get('result'):headers.append(x['response']['result'])
    anchors={int(h['number'],16):int(h['timestamp'],16) for h in headers}
    blocks=sorted(anchors);times=[anchors[b] for b in blocks]
    home=read(ROOT/'notebook-evidence/home.json')
    custody={a.lower() for a in home['contracts'].values()}|{POOL,POL,ZERO}|SECONDARY
    bytx=defaultdict(list);evtx=defaultdict(list)
    for t in transfers:bytx[t['transactionHash']].append(t)
    for e in events:evtx[e['transactionHash']].append(e)
    records=[]
    for tx,es in evtx.items():
        swaps=[e for e in es if e['event']=='Swap']
        if not swaps:continue
        b=key(es[0])[0];stamp=float(np.interp(b,blocks,times))
        buy=sum(max(0,-int(e['decoded']['amount0'])) for e in swaps)/1e18
        sell=sum(max(0,int(e['decoded']['amount0'])) for e in swaps)/1e18
        side='mixed' if buy and sell else 'buy' if buy else 'sell'
        records.append(dict(tx=tx,block=b,transaction_index=key(es[0])[1],timestamp=stamp,
            utc_approx=utc(stamp),exact_header=b in anchors,side=side,buy_eth=buy,sell_eth=sell,
            gross_eth=buy+sell,swap_logs=len(swaps),actor=actor_for(es,bytx[tx],custody),
            transaction_sender=envelopes.get(tx,{}).get('from',''),transaction_to=envelopes.get(tx,{}).get('to',''),
            tokens=sum(abs(int(e['decoded']['amount1'])) for e in swaps)/1e18,
            price_eth=2**192/int(swaps[-1]['decoded']['sqrtPriceX96'])**2))
    f=pd.DataFrame(records).sort_values(['block','transaction_index']).reset_index(drop=True)
    f.to_csv(out/'transactions.csv.gz',index=False)
    rr=pd.concat([runs(f,t) for t in [0,.1,1]],ignore_index=True)
    rr.to_csv(out/'runs.csv',index=False)
    f['bin_utc']=pd.to_datetime(f.timestamp,unit='s',utc=True).dt.floor('5min')
    bins=f.groupby('bin_utc').agg(buy_eth=('buy_eth','sum'),sell_eth=('sell_eth','sum'),transactions=('tx','count'),buy_count=('side',lambda s:(s=='buy').sum()),sell_count=('side',lambda s:(s=='sell').sum()),addresses=('actor',lambda s:s[s!=''].nunique()),price_eth=('price_eth','last'))
    bins.to_csv(out/'five-minute-flows.csv')
    w=f[f.actor!=''].groupby(['actor','side']).agg(transactions=('tx','count'),eth=('gross_eth','sum'),first=('timestamp','min'),last=('timestamp','max')).reset_index()
    w['first_utc']=w['first'].map(utc);w['last_utc']=w['last'].map(utc)
    w.sort_values('eth',ascending=False).to_csv(out/'address-flows.csv',index=False)
    segments=[]
    for label,a,b in [('full',None,None),('sell_wave','2026-09-16T04:15:00Z','2026-09-16T05:56:10Z'),('rebound','2026-09-16T05:56:10Z',None),('last20',utc(int(fresh['header']['timestamp'],16)-1200),None)]:
        g=f.copy()
        if a:g=g[g.timestamp>=pd.Timestamp(a).timestamp()]
        if b:g=g[g.timestamp<pd.Timestamp(b).timestamp()]
        for side in ['buy','sell']:
            s=g[g.side==side];v=s[s.actor!=''].groupby('actor').gross_eth.sum().sort_values(ascending=False)
            segments.append(dict(segment=label,side=side,transactions=len(s),eth=s.gross_eth.sum(),addresses=len(v),attributed_eth=v.sum(),top_address=v.index[0] if len(v) else '',top_eth=float(v.iloc[0]) if len(v) else 0,top3_eth=float(v.head(3).sum())))
    pd.DataFrame(segments).to_csv(out/'segments.csv',index=False)
    # A concrete synchronized group selected by the first dense block of the sell burst.
    group=set(f.loc[f.block==64214492,'actor'])-{''}
    g=f[f.actor.isin(group)&f.block.between(64214492,64214560)].copy()
    balances=defaultdict(int)
    for x in read(ROOT/'behavior-evidence/wallet-balances.json'):
        if x['label'].endswith('.token'):balances[x['label'][:-6]]=int(x['value'])
    before={}
    for tx,ts in sorted(((tx,ts) for tx,ts in bytx.items() if ts),key=lambda x:key(x[1][0])):
        if tx in set(g.tx):before[tx]={a:balances[a] for a in group}
        for t in ts:
            d=t['decoded'];q=int(d['value']);balances[d['from'].lower()]-=q;balances[d['to'].lower()]+=q
    g['wallet_tokens_before']=[before[row.tx][row.actor]/1e18 for row in g.itertuples()]
    g['fraction_sold']=g.tokens/g.wallet_tokens_before
    g.to_csv(out/'synchronized-sells.csv',index=False)
    acq=pd.read_csv(ROOT/UPDATE/'results/participants/acquisitions.csv.gz')
    acq[acq.address.isin(group)].to_csv(out/'synchronized-wallet-acquisitions.csv.gz',index=False)
    summary=dict(pin_utc=utc(int(fresh['header']['timestamp'],16)),block=int(fresh['header']['number'],16),hash=fresh['header']['hash'],transactions=len(f),swap_logs=int(f.swap_logs.sum()),multi_swap_transactions=int((f.swap_logs>1).sum()),mixed_transactions=int((f.side=='mixed').sum()),buy_eth=f.buy_eth.sum(),sell_eth=f.sell_eth.sum(),actor_attributed_eth=f.loc[f.actor!='','gross_eth'].sum(),gross_eth=f.gross_eth.sum(),price_eth=fresh['price_ETH'],lastTickAt=fresh['lastTickAt'],segments=segments)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    print(rr.sort_values('transactions',ascending=False).groupby(['threshold_eth','side']).head(2).to_string(index=False))

if __name__=='__main__':main()
