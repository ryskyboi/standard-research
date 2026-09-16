"""Verify the frozen, publicly shareable re-entry artifact and executed notebook."""
from pathlib import Path
import hashlib,json
import nbformat
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parent
manifest=json.loads((root/'reentry-manifest.json').read_text())
for name,digest in manifest['sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,f'Changed re-entry artifact: {name}'
target=json.loads((root/'reentry-evidence/target.json').read_text())
summary=json.loads((root/'reentry-results/summary.json').read_text())
assert target['chainId']==4663 and target['status']=='complete'
assert summary['block_hash']==manifest['block_hash']==target['header']['hash']
assert target['token'].lower()=='0x88ad8ddf1e3898412146a534538d418c6f8a9062'
assert target['allWalletTokenBalancesReconciled'] and summary['pending_sum_reconciled']
for name in ['price-hurdles','buyback-cases','license-waiting','optional-bank-exits','six-hour-cases','branch-payback']:
    table=pd.read_csv(root/'reentry-results'/f'{name}.csv')
    assert len(table) and np.isfinite(table.select_dtypes('number')).all().all(),name
notebook=nbformat.read(root/'reentry_analysis.ipynb',as_version=4);nbformat.validate(notebook)
cells=[c for c in notebook.cells if c.cell_type=='code']
assert all(c.execution_count is not None for c in cells)
assert not any(o.output_type=='error' for c in cells for o in c.outputs)
print(f'Verified {len(manifest["sha256"])} frozen files and {len(cells)} executed cells; block {summary["block"]}.')
