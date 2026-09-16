"""Separate post-snapshot auction observation with deposit-inventory lineage."""
from collections import defaultdict,Counter
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,ZERO,POOL,SECONDARY,key,utc
import json

def run(root=ROOT):
    d=read(root/'strategy-current/followup.json.gz');out=root/'participant-results'
    balance=defaultdict(int);mix=defaultdict(lambda:np.zeros(3))
    for x in read(root/'strategy-current/wallet-balances.json'):
        if x['label'].endswith('.token'):
            a=x['label'][:-6];balance[a]=int(x['value']);mix[a][0]=balance[a]/1e18
    # Origins: inventory already in wallets; new canonical-pool acquisition;
    # post-snapshot other custody/mint. Transfers retain the origin mixture.
    legs=defaultdict(int);pool_out=defaultdict(int)
    for x in d['swaps']:
        if int(x['decoded']['amount1'])>0:legs[x['transactionHash']]+=int(x['decoded']['amount1'])
    for x in d['transfers']:
        if x['decoded']['from'].lower()==POOL:pool_out[x['transactionHash']]+=int(x['decoded']['value'])
    burns=defaultdict(lambda:np.zeros(3));tx_acq=defaultdict(lambda:np.zeros(3))
    for x in sorted(d['transfers'],key=key):
        q=int(x['decoded']['value']);a=x['decoded']['from'].lower();b=x['decoded']['to'].lower();h=x['transactionHash']
        if a==ZERO:v=np.array([0.,0.,q/1e18])
        else:
            assert balance[a]>=q,(a,h,balance[a],q)
            v=mix[a]*(q/balance[a]) if balance[a] else np.zeros(3)
            mix[a]-=v;balance[a]-=q
            if a==POOL:
                fraction=min(1,legs[h]/pool_out[h]) if pool_out[h] else 0
                v=np.array([0.,q/1e18*fraction,q/1e18*(1-fraction)])
            elif a in SECONDARY:v=np.array([0.,0.,q/1e18])
        if b==ZERO:burns[(h,a)]+=v
        else:mix[b]+=v;balance[b]+=q
    deposits=[];licenses=[]
    for x in d['events']:
        e=x['event'];v=x['decoded']
        if e=='Deposited':
            a=v['from'].lower();q=int(v['amount'])/1e18;provenance=burns[(x['transactionHash'],a)]
            assert abs(provenance.sum()-q)<1e-6
            deposits.append({'charter_id':int(v['charterId']),'depositor':a,'tokens':q,'pre_snapshot_wallet_inventory':provenance[0],'new_canonical_acquisition':provenance[1],'new_other_custody_or_mint':provenance[2],'tx':x['transactionHash'],'block':int(x['blockNumber'],16)})
        elif e=='LicensesPurchased':licenses.append({'charter_id':int(v['charterId']),'licenses':int(v['count']),'paid_tokens':int(v['unitPrice'])*int(v['count'])/1e18,'tx':x['transactionHash'],'block':int(x['blockNumber'],16)})
    dep=pd.DataFrame(deposits);lic=pd.DataFrame(licenses);dep.to_csv(out/'followup-deposits.csv',index=False);lic.to_csv(out/'followup-licenses.csv',index=False)
    charters=pd.read_csv(out/'charters.csv').set_index('charter_id');owners=set(charters.owner)
    license_buyers=set(charters.loc[lic.charter_id,'owner']);depositors=set(dep.depositor)
    custody={a.lower() for a in read(root/'notebook-evidence/home.json')['contracts'].values()}|{ZERO,POOL}|SECONDARY
    nets=defaultdict(lambda:defaultdict(int));swaps_by_tx=defaultdict(list)
    for x in d['transfers']:
        h=x['transactionHash'];v=x['decoded'];q=int(v['value']);nets[h][v['from'].lower()]-=q;nets[h][v['to'].lower()]+=q
    for x in d['swaps']:swaps_by_tx[x['transactionHash']].append(x)
    attributed=[]
    for h,ss in swaps_by_tx.items():
        sides={'buy' if int(x['decoded']['amount1'])>0 else 'sell' for x in ss}
        if len(sides)!=1:continue
        side=next(iter(sides));sign=1 if side=='buy' else -1;q=sum(abs(int(x['decoded']['amount1'])) for x in ss)
        candidates={a:sign*v for a,v in nets[h].items() if a not in custody and sign*v>0}
        if len(candidates)!=1:continue
        a=next(iter(candidates))
        if candidates[a]<q or nets[h].get(POOL,0)!=-sign*q:continue
        attributed.append({'address':a,'side':side,'canonical_tokens':q/1e18,'canonical_ETH':sum(abs(int(x['decoded']['amount0']))/1e18 for x in ss),'charter_owner':a in owners,'bought_license_in_window':a in license_buyers,'deposited_in_window':a in depositors,'tx':h})
    follow_trades=pd.DataFrame(attributed);follow_trades.to_csv(out/'followup-trades.csv',index=False)
    counts=Counter(x['event'] for x in d['events']);pool_buy=sum(-int(x['decoded']['amount0'])/1e18 for x in d['swaps'] if int(x['decoded']['amount0'])<0);pool_sell=sum(int(x['decoded']['amount0'])/1e18 for x in d['swaps'] if int(x['decoded']['amount0'])>0)
    state={x['label']:x['value'] for x in d['state']};first=read(root/'participant-results/decision-metadata.json')
    latest=2**192/int(d['swaps'][-1]['decoded']['sqrtPriceX96'])**2
    result={'timestamp_utc':utc(int(d['header']['timestamp'],16)),'block':int(d['header']['number'],16),'block_hash':d['header']['hash'],'from_snapshot_utc':first['snapshot_utc'],'new_licenses':int(lic.licenses.sum()),'license_cost_tokens':lic.paid_tokens.sum(),'bank_deposit_tokens':dep.tokens.sum(),'deposit_existing_wallet_tokens':dep.pre_snapshot_wallet_inventory.sum(),'deposit_new_canonical_tokens':dep.new_canonical_acquisition.sum(),'deposit_new_other_custody_tokens':dep.new_other_custody_or_mint.sum(),'new_withdrawals':counts.get('Withdrawn',0),'total_branches':int(state['totalBranches']),'remaining_licenses':int(state['remainingToday']),'canonical_buy_ETH':pool_buy,'canonical_sell_ETH':pool_sell,'canonical_net_ETH':pool_buy-pool_sell,'last_swap_price_ETH':latest,'price_change_since_snapshot':latest/first['price_ETH']-1,'token_lineage_convention':'Pro-rata inventory; not proof of which fungible units were deposited. New acquisitions include possible mixed swap/LP routes and are identified as custody outflows if unresolved. A matched canonical Swap leg supplies the canonical-acquisition allocation.','forecast_use':'Later observation, never used as pre-cutoff calibration or claimed as an out-of-sample forecasting success.'}
    for side in ['buy','sell']:
        ss=follow_trades[follow_trades.side==side]
        result[side+'_attributed_ETH']=ss.canonical_ETH.sum()
        for label in ['charter_owner','bought_license_in_window','deposited_in_window']:
            result[side+'_'+label+'_ETH']=ss.loc[ss[label],'canonical_ETH'].sum()
    # Reconcile the branch ledger across the follow-up interval. Individual event
    # timestamps are interpolated; aggregate issuance uses exact endpoint times.
    ids=charters.index.to_list();index={cid:i for i,cid in enumerate(ids)}
    branches=charters.branches.to_numpy(dtype=float).copy();ledger=np.zeros((len(ids),5))
    ledger[:,0]=charters.pending_tokens.to_numpy();previous=int(read(root/'strategy-current/target.json')['header']['timestamp'],16)
    begin_block=int(read(root/'strategy-current/target.json')['header']['number'],16);end_block=int(d['header']['number'],16);end_time=int(d['header']['timestamp'],16);start_time=previous
    depmap={(x.tx,x.charter_id):x for x in dep.itertuples()};paid=[]
    for e in sorted(d['events'],key=key):
        moment=start_time+(int(e['blockNumber'],16)-begin_block)/(end_block-begin_block)*(end_time-start_time)
        ledger[:,1]+=(moment-previous)/86400*700000*branches/branches.sum();previous=moment
        v=e['decoded'];event=e['event']
        if event=='Deposited':
            i=index[int(v['charterId'])];r=depmap[(e['transactionHash'],int(v['charterId']))]
            ledger[i,2:]+=np.array([r.pre_snapshot_wallet_inventory,r.new_canonical_acquisition,r.new_other_custody_or_mint])
        elif event=='BranchesOpened':
            i=index[int(v['charterId'])];cost=int(v['cost'])/1e18
            assert ledger[i].sum()+1>=cost,'Interpolation error exceeds one token'
            allocation=ledger[i]*(cost/ledger[i].sum());ledger[i]-=allocation
            branches[i]+=int(v['count'])
            paid.append({'charter_id':int(v['charterId']),'cost_tokens':cost,'prior_bank_balance':allocation[0],'new_issuance':allocation[1],'prefunded_wallet_tokens':allocation[2],'new_canonical_tokens':allocation[3],'new_other_custody_tokens':allocation[4],'tx':e['transactionHash']})
        elif event=='Withdrawn':raise ValueError('Follow-up withdrawal requires an explicit ledger extension')
    ledger[:,1]+=(end_time-previous)/86400*700000*branches/branches.sum()
    result['ledger_reconciliation_error_tokens']=float(ledger.sum()-int(state['totalPendingLive'])/1e18)
    assert abs(result['ledger_reconciliation_error_tokens'])<1e-5
    assert int(branches.sum())==int(state['totalBranches'])
    paid=pd.DataFrame(paid);paid.to_csv(out/'followup-license-funding.csv',index=False)
    for name in ['prior_bank_balance','new_issuance','prefunded_wallet_tokens','new_canonical_tokens','new_other_custody_tokens']:
        result['license_paid_from_'+name]=paid[name].sum()
    result['ledger_lineage_caveat']='Pro-rata ledger accounting with interpolated action times; source composition approximate. Aggregate issuance, deposits, license costs, ending branches and total pending reconcile to pinned state.'
    (out/'followup-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result
if __name__=='__main__':run()
