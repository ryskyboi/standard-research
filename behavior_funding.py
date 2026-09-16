"""Extend the observed license-funding ledger to the fresh pin without altering history."""
import tempfile,json,gzip,shutil
from pathlib import Path
from participant_flows import ROOT,read
from participant_followup import run as followup

def run(root=ROOT):
    e=root/'behavior-evidence';s={x['label']:x.get('value') for x in read(e/'state.json')}
    events=read(e/'delta-events.json.gz')
    data={'header':read(e/'target.json')['header'],'transfers':read(e/'delta-transfers.json.gz'),'swaps':[x for x in events if x['event']=='Swap'],'events':[x for x in events if x['event'] not in ['Swap','ModifyLiquidity']],'state':[{'label':k,'value':s[v]} for k,v in [('totalBranches','bank.totalBranches'),('totalPendingLive','bank.totalPendingLive'),('remainingToday','license.remainingToday')]]}
    out=root/'behavior-results/funding';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='standard-funding-') as tmp:
        stage=Path(tmp);(stage/'notebook-evidence').symlink_to((root/'notebook-evidence').resolve(),target_is_directory=True)
        current=stage/'strategy-current';current.mkdir()
        for p in (root/'strategy-current').iterdir():
            if p.is_file() and p.name!='followup.json.gz':(current/p.name).symlink_to(p.resolve())
        with gzip.open(current/'followup.json.gz','wt') as f:json.dump(data,f)
        for name in ['charters.csv','decision-metadata.json']:shutil.copyfile(root/'participant-results'/name,out/name)
        (stage/'participant-results').symlink_to(out.resolve(),target_is_directory=True)
        return followup(stage)

if __name__=='__main__':run()
