"""Verify a frozen update and its dependency on the previous research packet."""
import argparse,hashlib,json
from pathlib import Path
import nbformat
from participant_flows import ROOT

def run(packet):
    packet=Path(packet).resolve();m=json.loads((packet/'manifest.json').read_text())
    for name,digest in m['sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,f'Changed update artifact: {name}'
    t=json.loads((packet/'evidence/target.json').read_text())
    assert t['chainId']==4663 and t['status']=='complete' and t['allWalletTokenBalancesReconciled']
    assert t['header']['hash']==m['block_hash']
    nb=nbformat.read(packet/'update.ipynb',as_version=4);nbformat.validate(nb)
    cells=[c for c in nb.cells if c.cell_type=='code']
    assert all(c.execution_count is not None for c in cells)
    assert not any(o.output_type=='error' for c in cells for o in c.outputs)
    print(f'Verified {len(m["sha256"])} frozen update/dependency files and {len(cells)} executed cells.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('packet');a=p.parse_args();run(a.packet)
