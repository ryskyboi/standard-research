"""Trace inventory replenishment through ordered token transfers and swap legs.

Within-transaction relays preserve source labels. A mixed balance is allocated
pro-rata; neither token lineage nor shared routing establishes common ownership.
"""
from collections import defaultdict,Counter
from pathlib import Path
import json
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,key,utc,ZERO,POOL,SECONDARY,KINDS

PACKET='behavior-updates/2026-09-16T054047Z'

def run(root=ROOT):
    packet=root/PACKET;e=packet/'evidence';out=root/'seller-origin-results';out.mkdir(exist_ok=True)
    oldtarget=read(root/'behavior-evidence/target.json');target=read(e/'target.json');cut=int(oldtarget['header']['number'],16)
    old=pd.read_csv(root/'behavior-results/population.csv.gz');current=pd.read_csv(packet/'results/population.csv.gz');trades=pd.read_csv(packet/'results/participants/trades.csv.gz')
    fixed=set(old.loc[old.sell_tokens_6h>0,'address']);rolling=set(current.loc[current.sell_tokens_6h>0,'address'])
    balances=defaultdict(int)
    for x in read(root/'behavior-evidence/wallet-balances.json'):
        if x['label'].endswith('.token'):balances[x['label'][:-6]]=int(x['value'])
    logs=sorted([x for x in read(e/'delta-transfers.json.gz') if int(x['blockNumber'],16)>cut],key=key)
    txs=defaultdict(list);ev=defaultdict(list);secondary=defaultdict(list)
    for x in logs:txs[x['transactionHash']].append(x)
    for x in read(e/'delta-events.json.gz'):ev[x['transactionHash']].append(x)
    for x in read(e/'secondary-swaps.json.gz')['logs']:secondary[x['transactionHash']].append(x)
    headers={int(h['number'],16):int(h['timestamp'],16) for h in read(e/'headers.json')};headers[cut]=int(oldtarget['header']['timestamp'],16);hs=sorted(headers)
    timestamp=lambda b:float(np.interp(b,hs,[headers[k] for k in hs]))
    roots=[];incoming=[];edges=[];gross_in=gross_out=internal=churn=0;max_error=0
    for tx,ls in txs.items():
        touched={x['decoded'][k].lower() for x in ls for k in ['from','to']}-{ZERO}
        # Source means pre-transaction inventory unless an observed swap/mint
        # replaces it. Empty relay addresses cannot manufacture a new source.
        mixtures={a:Counter({('wallet_inventory',a):balances[a]/1e18}) if balances[a] else Counter() for a in touched}
        outs=Counter()
        for x in ls:outs[x['decoded']['from'].lower()]+=int(x['decoded']['value'])
        canonical_bought=sum(max(0,int(x['decoded']['amount1'])) for x in ev[tx] if x['event']=='Swap')
        if any(x['event']=='ModifyLiquidity' for x in ev[tx]):canonical_bought=0
        verified_other=Counter()
        for x in secondary[tx]:verified_other[x['address'].lower()]+=max(0,-int(x['decoded']['amount1']))
        withdraw=any(x['event']=='Withdrawn' for x in ev[tx]);tin=tout=0
        for x in ls:
            v=x['decoded'];a=v['from'].lower();b=v['to'].lower();raw=int(v['value']);q=raw/1e18;block=int(x['blockNumber'],16)
            if a==ZERO:source=Counter({('branch_withdrawal_mint' if withdraw else 'other_mint',a):q})
            else:
                assert balances[a]>=raw,(tx,a,balances[a],raw)
                fraction=raw/balances[a] if balances[a] else 0
                source=Counter({k:v*fraction for k,v in mixtures[a].items() if v>1e-20})
                for k,value in source.items():mixtures[a][k]-=value
                balances[a]-=raw
                if a in {POOL}|SECONDARY:
                    verified=canonical_bought if a==POOL else verified_other[a]
                    portion=min(1,verified/outs[a]) if outs[a] else 0
                    label='canonical_swap_output' if a==POOL else 'verified_secondary_swap_output'
                    source=Counter({(label,a):q*portion,('other_custody_output',a):q*(1-portion)})
            if b!=ZERO:
                balances[b]+=raw
                for k,value in source.items():mixtures[b][k]+=value
                err=abs(sum(mixtures[b].values())-balances[b]/1e18);max_error=max(max_error,err);assert err<.0001,(tx,b,err)
            if a not in fixed and b in fixed:
                gross_in+=q;tin+=q
                incoming.append(dict(tx=tx,block=block,timestamp_utc_approx=utc(timestamp(block)),immediate_sender=a,recipient=b,tokens=q))
                for (kind,origin),value in source.items():
                    if value<=1e-15:continue
                    label=('same_group_inventory_via_relay' if origin in fixed else 'outside_wallet_inventory') if kind=='wallet_inventory' else kind
                    roots.append(dict(tx=tx,block=block,timestamp_utc_approx=utc(timestamp(block)),recipient=b,immediate_sender=a,economic_source=origin,source=label,tokens=value,routed=origin!=a))
            if a in fixed and b not in fixed:gross_out+=q;tout+=q
            if a in fixed and b in fixed:internal+=q
            edges.append(dict(tx=tx,block=block,log_index=int(x['logIndex'],16),sender=a,recipient=b,tokens=q))
        churn+=min(tin,tout)
    state={x['label']:x.get('value') for x in read(e/'state.json')}
    assert sum(balances.values())==int(state['token.totalSupply'])
    for row in read(e/'wallet-balances.json'):
        if row['label'].endswith('.token'):assert balances[row['label'][:-6]]==int(row['value'])
    r=pd.DataFrame(roots);inc=pd.DataFrame(incoming)
    assert abs(r.tokens.sum()-gross_in)<1e-6
    r.to_csv(out/'incoming-economic-sources.csv.gz',index=False);inc.to_csv(out/'incoming-transfers.csv',index=False)
    pd.DataFrame(edges).to_csv(out/'interval-transfer-graph.csv.gz',index=False)
    r.groupby(['source','economic_source'],sort=False).agg(tokens=('tokens','sum'),transactions=('tx','nunique'),recipients=('recipient','nunique')).sort_values('tokens',ascending=False).to_csv(out/'source-addresses.csv')
    r.groupby('source').tokens.sum().sort_values(ascending=False).to_csv(out/'replenishment-sources.csv')
    recent=trades[trades.block>cut];sold=recent[recent.side=='sell'];bought=recent[recent.side=='buy']
    pd.DataFrame([dict(source=k,sold_tokens=sold[k].sum(),share=sold[k].sum()/sold.tokens.sum()) for k in KINDS]).to_csv(out/'sold-token-origins.csv',index=False)
    inventory=current[current.address.isin(rolling)]
    pd.DataFrame([dict(source=k,remaining_tokens=inventory['inventory_'+k].sum(),share=inventory['inventory_'+k].sum()/inventory.wallet_tokens.sum()) for k in KINDS]).to_csv(out/'remaining-token-origins.csv',index=False)
    base=old.set_index('address').wallet_tokens;now=current.set_index('address').wallet_tokens
    rows=[]
    for address in fixed:
        buy=bought[bought.address==address];sell=sold[sold.address==address];rr=r[r.recipient==address]
        rows.append(dict(address=address,initial_tokens=float(base.get(address,0)),current_tokens=float(now.get(address,0)),bought_canonical_tokens=buy.tokens.sum(),buy_pool_ETH=buy.pool_eth.sum(),sold_canonical_tokens=sell.tokens.sum(),sell_pool_ETH=sell.pool_eth.sum(),gross_external_incoming=rr.tokens.sum(),**{k:g.tokens.sum() for k,g in rr.groupby('source')}))
    pd.DataFrame(rows).fillna(0).sort_values('gross_external_incoming',ascending=False).to_csv(out/'replenished-wallets.csv',index=False)
    membership=[]
    for label,addresses in [('retained',fixed&rolling),('newly_in_rolling_group',rolling-fixed),('aged_out_of_rolling_group',fixed-rolling)]:
        group=current[current.address.isin(addresses)];membership.append(dict(membership=label,addresses=len(addresses),current_tokens=group.wallet_tokens.sum()))
        if label=='newly_in_rolling_group':
            group=group.copy();group['previous_tokens']=group.address.map(base).fillna(0);group.sort_values('wallet_tokens',ascending=False).to_csv(out/'new-seller-group-members.csv',index=False)
    pd.DataFrame(membership).to_csv(out/'cohort-membership.csv',index=False)
    oldstock=old[old.address.isin(fixed)].wallet_tokens.sum();currentfixed=current[current.address.isin(fixed)].wallet_tokens.sum()
    assert abs(oldstock+gross_in-gross_out-currentfixed)<1e-6
    assert abs(currentfixed-membership[2]['current_tokens']+membership[1]['current_tokens']-inventory.wallet_tokens.sum())<1e-6
    # Concrete upstream histories for peer inventory, not inferred common ownership.
    acq=pd.read_csv(packet/'results/participants/acquisitions.csv.gz')
    peer=r[r.source=='outside_wallet_inventory'].groupby('economic_source').tokens.sum().sort_values(ascending=False)
    acq[acq.address.isin(peer.index)].to_csv(out/'peer-source-acquisition-history.csv.gz',index=False)
    examples=inc.sort_values('tokens',ascending=False).head(12).tx.to_list()
    examples+=r[(r.routed)&(r.tokens>1000)].sort_values('tokens',ascending=False).head(4).tx.to_list()
    examples+=r[r.source=='outside_wallet_inventory'].sort_values('tokens',ascending=False).head(4).tx.to_list()
    chosen=set(examples);pd.DataFrame(edges).query('tx in @chosen').to_csv(out/'example-transaction-paths.csv',index=False)
    meta=dict(from_utc=utc(int(oldtarget['header']['timestamp'],16)),to_utc=utc(int(target['header']['timestamp'],16)),from_block=cut,to_block=int(target['header']['number'],16),block_hash=target['header']['hash'],fixed_seller_addresses=len(fixed),initial_fixed_tokens=oldstock,remaining_fixed_tokens=currentfixed,gross_external_incoming=gross_in,gross_external_outgoing=gross_out,internal_group_transfers=internal,same_transaction_boundary_churn=churn,replenishment_sources=r.groupby('source').tokens.sum().to_dict(),fixed_cohort_canonical_rebuys=bought.loc[bought.address.isin(fixed),'tokens'].sum(),fixed_cohort_rebuy_addresses=bought.loc[bought.address.isin(fixed),'address'].nunique(),fixed_cohort_rebuy_pool_ETH=bought.loc[bought.address.isin(fixed),'pool_eth'].sum(),attributed_sold_tokens=sold.tokens.sum(),sale_origins={k:sold[k].sum() for k in KINDS},rolling_inventory=inventory.wallet_tokens.sum(),inventory_origins={k:inventory['inventory_'+k].sum() for k in KINDS},cohort_membership=membership,all_token_balances_reconciled=True,total_supply_reconciled=True,maximum_mixed_source_error=max_error,limitations='Sources refer to tokens, not private wallet ownership or origin of ETH used to buy. Same-transaction relays are traced in log order, with pro-rata allocation if a relay mixes balances. Pool output counts as a verified purchase only to the extent supported by matching Swap legs; canonical transactions with liquidity changes stay unresolved. Other custody output remains unresolved. Historical sale/inventory lineage uses the frozen pro-rata attribution. Cohort membership uses approximate six-hour timestamps; interval transfers use exact block cutoffs.')
    (out/'summary.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2));return meta

if __name__=='__main__':run()
