"""Address-level canonical-pool attribution and pro-rata acquisition provenance.

A token source is an accounting lineage, not proof of beneficial ownership or intent.
Raw Transfer replay is integer exact; provenance proportions use floating point.
"""
from pathlib import Path
from collections import defaultdict, Counter
import gzip, json, hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
ZERO='0x'+'0'*40
POOL='0x8366a39cc670b4001a1121b8f6a443a643e40951'
POL='0x242f3e67bef43470c2434d95e7d618e19f87c8f8'
# Two STANDARD pair contracts verified through token0/token1; the third is a
# repeated execution-route counterparty, kept out of investor cohorts conservatively.
SECONDARY={'0xbbd8f14be91b0eab9dcc6538b8360de243c8a4ca','0x17df14744076421e165d04372f196885c6292417','0x65ee0e9d98ed1564655ac51d78ffd6ef61f66404'}
KINDS=['own_pool_buy','transferred_pool_buy','branch_withdrawal','transferred_branch_withdrawal','initial_allocation','transferred_allocation','other_custody_or_unresolved','own_other_pool_buy','transferred_other_pool_buy']
def read(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path)) as handle:
        return json.load(handle)
def key(x):return (int(x['blockNumber'],16),int(x['transactionIndex'],16),int(x['logIndex'],16))
def utc(s):return pd.Timestamp(s,unit='s',tz='UTC').isoformat()
def transferred(v):
    x=v.copy();x[1]+=x[0];x[0]=0;x[3]+=x[2];x[2]=0;x[5]+=x[4];x[4]=0;x[8]+=x[7];x[7]=0;return x

def load(root=ROOT):
    target=read(root/'strategy-current/target.json')
    transfers=read(root/'strategy-evidence/transfers.json.gz')+read(root/'strategy-current/delta-transfers.json.gz')
    events=read(root/'empirical-evidence/events.json.gz')['logs']+read(root/'strategy-current/delta-events.json.gz')
    return target,sorted(transfers,key=key),sorted(events,key=key)

def analyze(root=ROOT):
    target,transfers,events=load(root);pin=int(target['header']['timestamp'],16)
    home=read(root/'notebook-evidence/home.json')
    custody={a.lower() for a in home['contracts'].values()}|{POOL,POL,ZERO}|SECONDARY
    bytx=defaultdict(list);evtx=defaultdict(list)
    for t in transfers:bytx[t['transactionHash']].append(t)
    for e in events:
        evtx[e['transactionHash']].append(e)
        bytx.setdefault(e['transactionHash'],[])
    secondary=defaultdict(list)
    for e in read(root/'strategy-current/secondary-swaps.json.gz')['logs']:
        secondary[e['transactionHash']].append(e)
    headers=read(root/'empirical-evidence/boundaries.json')+read(root/'strategy-current/headers.json')+[target['header']]
    details=read(root/'strategy-current/details.json') if (root/'strategy-current/details.json').exists() else []
    headers += [x['response']['result'] for x in details if x['request']['method']=='eth_getBlockByNumber']
    transactions={x['response']['result']['hash']:x['response']['result'] for x in details if x['request']['method']=='eth_getTransactionByHash'}
    # Launch is an exact saved header time in home; early trade times remain interpolated.
    anchors={int(h['number'],16):int(h['timestamp'],16) for h in headers}
    genesis=int(home['snapshot']['bank']['genesisTime'])
    launch=min(int(e['blockNumber'],16) for e in events)
    anchors[launch]=genesis
    blocks=np.array(sorted(anchors));times=np.array([anchors[b] for b in blocks])
    timestamp=lambda b:float(np.interp(b,blocks,times))
    owners={};charters=defaultdict(dict)
    for row in read(root/'strategy-current/charters.json'):
        i,field=row['label'].split('.');charters[int(i)][field]=row.get('value')
    owner_ids=defaultdict(list)
    for i,c in charters.items():
        if c.get('ownerOf'):
            owners[i]=c['ownerOf'].lower();owner_ids[owners[i]].append(i)
    wallet_state=defaultdict(dict)
    for row in read(root/'strategy-current/wallet-balances.json'):
        a,k=row['label'].rsplit('.',1);wallet_state[a][k]=int(row['value'])/1e18
    balances=defaultdict(int);mix=defaultdict(lambda:np.zeros(len(KINDS)))
    inventory_max_error=0.;records=[];unresolved=[];transfer_edges=[];acquisitions=[]
    all_swap_eth=Counter();attributed_eth=Counter();all_swap_tokens=Counter();attributed_tokens=Counter()
    provenance_sells=[];gross_minted=0;gross_burned=0
    for tx,ts in bytx.items():
        es=evtx[tx];swaps=[e for e in es if e['event']=='Swap'];withdraw=[e for e in es if e['event']=='Withdrawn']
        b=key(ts[0] if ts else es[0])[0];stamp=timestamp(b)
        net=defaultdict(int)
        for t in ts:
            d=t['decoded'];a=d['from'].lower();z=d['to'].lower();q=int(d['value'])
            net[a]-=q;net[z]+=q
            if a==ZERO:gross_minted+=q
            if z==ZERO:gross_burned+=q
        positive={a:q for a,q in net.items() if q>0};negative={a:-q for a,q in net.items() if q<0}
        sides={'buy' if int(e['decoded']['amount1'])>0 else 'sell' for e in swaps}
        side=next(iter(sides)) if len(sides)==1 else None
        qswap=sum(abs(int(e['decoded']['amount1'])) for e in swaps)
        eth=sum(abs(int(e['decoded']['amount0'])) for e in swaps)/1e18
        for e in swaps:
            sd='buy' if int(e['decoded']['amount1'])>0 else 'sell'
            all_swap_eth[sd]+=abs(int(e['decoded']['amount0']))/1e18
            all_swap_tokens[sd]+=abs(int(e['decoded']['amount1']))/1e18
        actors={a:q for a,q in (positive if side=='buy' else negative).items() if a not in custody} if side else {}
        opposite={a:q for a,q in (negative if side=='buy' else positive).items() if a not in custody} if side else {}
        accepted=bool(swaps and side and not opposite and sum(actors.values())==qswap and not any(e['event']=='ModifyLiquidity' for e in es))
        split_route=False
        # An exact single wallet source/destination remains identifiable when a
        # router sends part of the trade through another venue. Only the canonical
        # leg is allocated here; other-venue ETH is never invented or counted.
        if not accepted and swaps and side and len(actors)==1 and sum(actors.values())>=qswap and not any(e['event']=='ModifyLiquidity' for e in es):
            a=next(iter(actors))
            if side=='sell' and set(negative)=={a} and net.get(POOL,0)==qswap:
                accepted=True;split_route=True;actors={a:qswap}
            elif side=='buy' and set(positive)=={a} and net.get(POOL,0)==-qswap:
                accepted=True;split_route=True;actors={a:qswap}
        # A negative net inventory comes from the wallet's pre-transaction stock.
        outgoing={};source=np.zeros(len(KINDS));total_out=sum(negative.values())/1e18
        for a,qraw in negative.items():
            q=qraw/1e18
            if a==ZERO:
                v=np.zeros(len(KINDS));v[2 if withdraw else 4]=q
            elif a in {POOL}|SECONDARY:
                v=np.zeros(len(KINDS));v[6]=q
                leg=[e for e in secondary[tx] if e['address'].lower()==a]
                if leg and all(int(e['decoded']['amount1'])<0 for e in leg) and sum(-int(e['decoded']['amount1']) for e in leg)==qraw:
                    v[7]=q;v[6]=0
                # Custody holdings are tracked for reconciliation but not investor origin.
                if balances[a]:mix[a]*=max(0,1-qraw/balances[a])
            else:
                if balances[a]<qraw:raise AssertionError(('negative replay',tx,a,balances[a],qraw))
                v=mix[a]*(qraw/balances[a]) if balances[a] else np.zeros(len(KINDS))
                mix[a]-=v
            outgoing[a]=v;source+=v if a in SECONDARY and v[7]>0 else transferred(v)
        for a,qraw in positive.items():
            if a==ZERO:continue
            q=qraw/1e18
            if accepted and side=='buy' and a in actors:
                direct=actors[a]/1e18
                v=np.zeros(len(KINDS));v[0]=direct;origin='canonical_pool_purchase'
                if q>direct:
                    extra=sum((vv if aa in SECONDARY and vv[7]>0 else transferred(vv) for aa,vv in outgoing.items() if aa!=POOL),start=np.zeros(len(KINDS)))
                    if extra.sum():v+=extra*((q-direct)/extra.sum())
                    else:v[6]+=q-direct
                    origin='canonical_pool_plus_other_source'
            else:
                v=source*(q/total_out) if total_out else np.zeros(len(KINDS));origin='wallet_transfer'
                # Newly minted branch tokens/initial allocation are direct at their first recipient.
                if set(negative)=={ZERO}:
                    v=np.zeros(len(KINDS));v[2 if withdraw else 4]=q
                    origin='branch_withdrawal' if withdraw else 'initial_allocation'
                elif POOL in negative:origin='custody_outflow_unresolved'
            mix[a]+=v
            if a not in custody:
                acquisitions.append({'address':a,'block':b,'timestamp_utc_approx':utc(stamp),'tx':tx,'tokens':q,'acquisition':origin})
                if origin=='wallet_transfer':
                    for sender,raw in negative.items():
                        if sender not in custody:transfer_edges.append({'from':sender,'to':a,'tokens_allocated_pro_rata':q*raw/sum(negative.values()),'block':b,'tx':tx})
        for a,n in net.items():
            if a==ZERO:continue
            balances[a]+=n
            err=abs(mix[a].sum()-balances[a]/1e18);inventory_max_error=max(inventory_max_error,err)
            if err>.002:raise AssertionError(('provenance reconciliation',a,err))
        if accepted:
            for a,qraw in actors.items():
                q=qraw/1e18;record={'address':a,'side':side,'tokens':q,'pool_eth':eth*qraw/qswap,'block':b,'timestamp':stamp,'timestamp_utc_approx':utc(stamp),'timestamp_exact_header':b in anchors,'tx':tx,'split_route':split_route,'split_eth_allocation':len(actors)>1,'charter_owner':a in owner_ids,'transaction_sender':transactions.get(tx,{}).get('from',''),'transaction_router':transactions.get(tx,{}).get('to','')}
                if side=='sell':
                    record.update(dict(zip(KINDS,outgoing[a]*(qraw/negative[a]))))
                    provenance_sells.append(record.copy())
                records.append(record)
            attributed_eth[side]+=eth;attributed_tokens[side]+=qswap/1e18
        elif swaps:
            unresolved.append({'tx':tx,'block':b,'timestamp_utc_approx':utc(stamp),'swap_count':len(swaps),'pool_eth_gross_activity':eth,'sides':','.join(sorted(sides)),'external_positive_addresses':len([a for a in positive if a not in custody]),'external_negative_addresses':len([a for a in negative if a not in custody])})
    observed_supply=int(next(x['value'] for x in read(root/'strategy-current/state.json') if x['label']=='token.totalSupply'))
    assert sum(balances.values())==gross_minted-gross_burned==observed_supply
    for a,s in wallet_state.items():
        assert abs(s['token']-balances[a]/1e18)<1e-6
    trades=pd.DataFrame(records);acq=pd.DataFrame(acquisitions);edges=pd.DataFrame(transfer_edges)
    historical=trades.pivot_table(index='address',columns='side',values=['tokens','pool_eth'],aggfunc='sum',fill_value=0)
    recent=trades[trades.timestamp>=pin-6*3600]
    addresses=(set(balances)|set(owner_ids)|set(wallet_state))-custody
    rows=[]
    first_buy=trades[trades.side=='buy'].groupby('address').timestamp.min().to_dict()
    deposits=defaultdict(float);license_count=Counter()
    for e in events:
        if e['event']=='Deposited':deposits[e['decoded']['from'].lower()]+=int(e['decoded']['amount'])/1e18
        if e['event']=='LicensesPurchased':license_count[owners.get(int(e['decoded']['charterId']),'burned_charter_owner_unresolved')]+=int(e['decoded']['count'])
    recentagg=recent.groupby(['address','side']).agg(tokens=('tokens','sum'),pool_eth=('pool_eth','sum'),count=('tx','count')).to_dict('index')
    for a in sorted(addresses):
        r={'address':a,'wallet_tokens':balances[a]/1e18,'native_eth':wallet_state.get(a,{}).get('eth',np.nan),'native_eth_observed':a in wallet_state,'charter_count':len(owner_ids.get(a,[])),'branches':sum(int(charters[i]['branchCountOf']) for i in owner_ids.get(a,[])),'pending_tokens':sum(int(charters[i]['pendingOf'])/1e18 for i in owner_ids.get(a,[])),'deposited_tokens_lifetime':deposits[a],'licenses_bought_lifetime':license_count[a]}
        for sd in ['buy','sell']:
            for metric in ['tokens','pool_eth']:
                r[sd+'_'+metric+'_lifetime']=float(historical.loc[a,(metric,sd)]) if a in historical.index else 0.
                r[sd+'_'+metric+'_6h']=recentagg.get((a,sd),{}).get(metric,0.)
            r[sd+'_count_6h']=recentagg.get((a,sd),{}).get('count',0)
        buy,sell=r['buy_tokens_6h'],r['sell_tokens_6h']
        if r['charter_count']:cohort='charter_operator'
        elif buy>0 and sell>0 and min(buy,sell)/max(buy,sell)>=.3:cohort='two_way_trader'
        elif sell>buy:cohort='net_seller'
        elif buy>sell:cohort='net_buyer'
        else:cohort='inactive_or_unattributed'
        r['cohort']=cohort;r['first_pool_buy_utc_approx']=utc(first_buy[a]) if a in first_buy else ''
        r.update({'inventory_'+k:v for k,v in zip(KINDS,mix[a])});rows.append(r)
    wallets=pd.DataFrame(rows)
    # Windows use interpolation solely to select a cutoff; exact block and tx remain provided.
    windows=[]
    for hours in [1/3,2,6,12,24]:
        tx=trades[trades.timestamp>=pin-hours*3600]
        for side in ['buy','sell']:
            s=tx[tx.side==side];new=s[s.address.map(first_buy).fillna(-1)>=pin-hours*3600] if side=='buy' else s.iloc[:0]
            all_eth=sum(abs(int(e['decoded']['amount0']))/1e18 for e in events if e['event']=='Swap' and ('buy' if int(e['decoded']['amount1'])>0 else 'sell')==side and timestamp(int(e['blockNumber'],16))>=pin-hours*3600)
            windows.append({'window_hours':hours,'from_utc_approx':utc(pin-hours*3600),'to_utc':utc(pin),'side':side,'attributed_pool_eth':s.pool_eth.sum(),'all_pool_eth':all_eth,'attribution_fraction':s.pool_eth.sum()/all_eth if all_eth else 1,'attributed_tokens':s.tokens.sum(),'addresses':s.address.nunique(),'tx_count':s.tx.nunique(),'new_to_canonical_pool_buy_eth':new.pool_eth.sum(),'charter_owner_pool_eth':s.loc[s.charter_owner,'pool_eth'].sum()})
    cohort=wallets.groupby('cohort').agg(addresses=('address','count'),wallet_tokens=('wallet_tokens','sum'),native_eth_observed=('native_eth','sum'),native_eth_missing=('native_eth_observed',lambda s:(~s).sum()),buy_eth_6h=('buy_pool_eth_6h','sum'),sell_eth_6h=('sell_pool_eth_6h','sum'),buy_tokens_6h=('buy_tokens_6h','sum'),sell_tokens_6h=('sell_tokens_6h','sum'),branches=('branches','sum'),pending_tokens=('pending_tokens','sum')).reset_index()
    sell=pd.DataFrame(provenance_sells);provenance=[]
    for hours in [1/3,2,6,24]:
        s=sell[sell.timestamp>=pin-hours*3600]
        for kind in KINDS:provenance.append({'window_hours':hours,'source':kind,'sold_tokens':s[kind].sum(),'share_of_attributed_sold_tokens':s[kind].sum()/s.tokens.sum() if s.tokens.sum() else 0})
    meta={'block':int(target['header']['number'],16),'block_hash':target['header']['hash'],'snapshot_utc':utc(pin),'transfer_logs':len(transfers),'canonical_swaps':sum(e['event']=='Swap' for e in events),'all_pool_eth':dict(all_swap_eth),'attributed_pool_eth':dict(attributed_eth),'all_swap_tokens':dict(all_swap_tokens),'attributed_swap_tokens':dict(attributed_tokens),'attribution_eth_fraction':{s:attributed_eth[s]/all_swap_eth[s] for s in all_swap_eth},'unresolved_transactions':len(unresolved),'integer_supply_reconciled':True,'all_collected_wallet_balances_reconciled':True,'provenance_max_error_tokens':inventory_max_error,'timing':'Trade timestamps interpolated between archived block headers; exact block/transaction IDs retained. Window boundaries approximate.','scope':'Canonical pool only. Addresses are not people. Pool ETH before output sell tax / after input buy hook accounting; no assumed identity, motive or ETH funding provenance. Pro-rata token lineage is a convention; no P&L claimed for unknown basis. Current Charter ownership used; Charter transfers disabled at this snapshot. Native ETH is buying-capacity ceiling, not intention. Fully exited inactive addresses lack fresh ETH reads and remain missing, never zero-filled.'}
    out=root/'participant-results';out.mkdir(exist_ok=True)
    for name,df in [('trades',trades),('wallets',wallets),('acquisitions',acq),('transfer-edges',edges),('unresolved-trades',pd.DataFrame(unresolved)),('cohorts',cohort),('windows',pd.DataFrame(windows)),('sell-provenance',pd.DataFrame(provenance))]:
        df.to_csv(out/(name+'.csv.gz' if name in ['trades','wallets','acquisitions','transfer-edges'] else name+'.csv'),index=False)
    for sd in ['sell','buy']:
        top=wallets.sort_values(sd+'_pool_eth_6h',ascending=False).head(30)
        top.to_csv(out/('top-'+sd+'ers.csv'),index=False)
    (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    charter_rows=[{'charter_id':i,'owner':owners[i],'branches':int(c['branchCountOf']),'pending_tokens':int(c['pendingOf'])/1e18} for i,c in charters.items() if i in owners]
    pd.DataFrame(charter_rows).to_csv(out/'charters.csv',index=False)
    # Compare each bank depositor with Charter ownership at that event, including
    # the subsequently burned Charter. Current ownership alone would mislabel it.
    nft=read(root/'strategy-current/charter-transfer-history.json')['response']['result']
    history={};deposit_rows=[]
    merged=sorted([(key(x),'nft',x) for x in nft]+[(key(x),'deposit',x) for x in events if x['event']=='Deposited'])
    for _,kind,x in merged:
        if kind=='nft':
            history[int(x['topics'][3],16)]='0x'+x['topics'][2][-40:]
        else:
            d=x['decoded'];i=int(d['charterId']);a=d['from'].lower()
            deposit_rows.append({'charter_id':i,'depositor':a,'owner_at_deposit':history.get(i,''),'owner_deposit':a==history.get(i),'tokens':int(d['amount'])/1e18,'block':int(x['blockNumber'],16),'timestamp_utc_approx':utc(timestamp(int(x['blockNumber'],16))),'tx':x['transactionHash']})
    assert {i:a for i,a in history.items() if a!=ZERO}==owners
    pd.DataFrame(deposit_rows).to_csv(out/'bank-deposits.csv',index=False)
    print(json.dumps(meta,indent=2));print(cohort.to_string(index=False));print(pd.DataFrame(windows).to_string(index=False))
    return meta
if __name__=='__main__':analyze()
