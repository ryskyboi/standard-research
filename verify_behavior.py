"""Verify the frozen behavior evidence, outputs and executed notebook offline."""
from pathlib import Path
import hashlib,json
import nbformat
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parent
manifest=json.loads((root/'behavior-manifest.json').read_text())
for name,digest in manifest['sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,f'Changed behavior artifact: {name}'
target=json.loads((root/'behavior-evidence/target.json').read_text())
assert target['chainId']==4663 and target['status']=='complete'
assert target['header']['hash']==manifest['block_hash']
assert target['allWalletTokenBalancesReconciled']
assert target['token'].lower()=='0x88ad8ddf1e3898412146a534538d418c6f8a9062'
runs=pd.read_csv(root/'behavior-results/scenario-runs.csv')
assert len(runs)==32 and runs.groupby('case').size().eq(4).all()
paths=pd.read_csv(root/'behavior-results/scenario-paths.csv.gz')
assert np.isfinite(paths.select_dtypes('number')).all().all()
assert (paths.price_ETH>0).all()
for _,g in paths.groupby(['case','seed']):
    assert len(g)==97 and g.hours.iloc[0]==0 and g.hours.iloc[-1]==24
    end=pd.Timestamp(g.timestamp_utc.iloc[-1]);start=pd.Timestamp(g.timestamp_utc.iloc[0]);assert end-start==pd.Timedelta(days=1)
errors=pd.read_csv(root/'behavior-results/accounting.csv.gz')
assert errors.ETH_error.abs().max()<1e-5
assert errors.token_error.abs().max()<.03
assert errors.ledger_error.abs().max()<1e-5
sensitivity=pd.read_csv(root/'behavior-results/assumption-sensitivity.csv')
assert len(sensitivity)==8 and np.isfinite(sensitivity.select_dtypes('number')).all().all()
nb=nbformat.read(root/'participant_behavior.ipynb',as_version=4);nbformat.validate(nb)
cells=[c for c in nb.cells if c.cell_type=='code']
assert all(c.execution_count is not None for c in cells)
assert not any(o.output_type=='error' for c in cells for o in c.outputs)
print(f'Verified {len(manifest["sha256"])} frozen files, 32 primary paths, 8 sensitivities and {len(cells)} executed cells.')
