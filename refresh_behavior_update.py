"""Rebuild a dated update using the frozen model and a fresh evidence packet.

No archived snapshot is overwritten. The temporary layout adapts existing
analysis functions to a new evidence/results directory. RPC collection is separate.
"""
import argparse,gzip,json,shutil,tempfile
from pathlib import Path
from participant_flows import ROOT,read
import behavior_refresh,behavior_observations,behavior_model
from participant_followup import run as followup

def interval_funding(stage,out,base=ROOT):
    prior=read(base/'behavior-evidence/target.json');cut=int(prior['header']['number'],16)
    e=stage/'behavior-evidence';state={x['label']:x.get('value') for x in read(e/'state.json')}
    events=[x for x in read(e/'delta-events.json.gz') if int(x['blockNumber'],16)>cut]
    data={'header':read(e/'target.json')['header'],'transfers':[x for x in read(e/'delta-transfers.json.gz') if int(x['blockNumber'],16)>cut],'swaps':[x for x in events if x['event']=='Swap'],'events':[x for x in events if x['event'] not in ['Swap','ModifyLiquidity']],'state':[{'label':k,'value':state[v]} for k,v in [('totalBranches','bank.totalBranches'),('totalPendingLive','bank.totalPendingLive'),('remainingToday','license.remainingToday')]]}
    # The frozen funding replay supports unchanged issuance and no withdrawals.
    # Refuse unsupported new events rather than presenting a false reconciliation.
    assert not any(x['event'] in ['Withdrawn','EpochSettled'] for x in events),'Extend ledger replay for retirement/epoch changes before publishing funding attribution'
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='standard-update-funding-') as tmp:
        r=Path(tmp);(r/'notebook-evidence').symlink_to(base/'notebook-evidence',target_is_directory=True)
        (r/'strategy-current').mkdir()
        for name in ['wallet-balances.json','target.json']:(r/'strategy-current'/name).symlink_to(base/'behavior-evidence'/name)
        with gzip.open(r/'strategy-current/followup.json.gz','wt') as h:json.dump(data,h)
        shutil.copy2(base/'behavior-results/participants/charters.csv',out/'charters.csv')
        shutil.copy2(base/'behavior-results/analysis-summary.json',out/'decision-metadata.json')
        (r/'participant-results').symlink_to(out,target_is_directory=True)
        return followup(r)

def run(packet,paths=4):
    packet=Path(packet).resolve();e=packet/'evidence';out=packet/'results';out.mkdir(exist_ok=True)
    target=read(e/'target.json');assert target['status']=='complete' and target['allWalletTokenBalancesReconciled']
    assert target['chainId']==4663
    with tempfile.TemporaryDirectory(prefix='standard-behavior-update-') as tmp:
        stage=Path(tmp)
        for name in ['notebook-evidence','strategy-evidence','empirical-evidence','strategy-current','reentry-abi','participant-results']:(stage/name).symlink_to(ROOT/name,target_is_directory=True)
        (stage/'behavior-evidence').symlink_to(e,target_is_directory=True);(stage/'behavior-results').symlink_to(out,target_is_directory=True)
        behavior_refresh.run(stage)
        interval_funding(stage,out/'interval-funding')
        behavior_observations.run(stage)
        behavior_model.run(stage,paths=paths,hours=24,workers=3)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('packet');p.add_argument('--paths',type=int,default=4);a=p.parse_args();run(a.packet,a.paths)
