"""Reuse the audited attribution engine with a separate, fresh evidence view.

Archived snapshots and source hashes are never overwritten. Historical inactive
addresses with zero tokens can still lack fresh cash observations.
"""
import json,gzip,tempfile,shutil
from pathlib import Path
from participant_flows import ROOT,read,analyze

def run(root=ROOT):
    new=root/'reentry-evidence';out=root/'reentry-results'/'participants'
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='standard-reentry-') as tmp:
        stage=Path(tmp)
        for name in ['notebook-evidence','strategy-evidence','empirical-evidence']:
            (stage/name).symlink_to((root/name).resolve(),target_is_directory=True)
        current=stage/'strategy-current';current.mkdir()
        for p in (root/'strategy-current').iterdir():
            if p.is_file(): (current/p.name).symlink_to(p.resolve())
        def put(name,data):
            p=current/name
            if p.is_symlink():p.unlink()
            if name.endswith('.gz'):
                with gzip.open(p,'wt') as f:json.dump(data,f)
            else:p.write_text(json.dumps(data))
        for name in ['target.json','state.json','charters.json','wallet-balances.json','liquidity.json','withdrawals.json']:
            put(name,read(new/name))
        for name in ['delta-transfers.json.gz','delta-events.json.gz','headers.json']:
            put(name,read(root/'strategy-current'/name)+read(new/name))
        put('secondary-swaps.json.gz',{'logs':read(root/'strategy-current/secondary-swaps.json.gz')['logs']+read(new/'secondary-swaps.json.gz')['logs']})
        (stage/'participant-results').symlink_to(out.resolve(),target_is_directory=True)
        return analyze(stage)

if __name__=='__main__':run()
