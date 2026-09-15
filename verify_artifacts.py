"""Offline integrity checks for the public research bundle."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import nbformat
from liquidity import ConcentratedPool

root=Path(__file__).resolve().parent
manifest=json.loads((root/'evidence-manifest.json').read_text())
for name,expected in manifest['sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,f'Changed evidence: {name}'
read=lambda name:json.loads((root/'notebook-evidence'/name).read_text())
home=read('home.json');done=read('collection-complete.json');profile=read('liquidity-ticks.json')
assert home['chainId']==4663
assert home['contracts']['standard'].lower()=='0x88ad8ddf1e3898412146a534538d418c6f8a9062'
assert home['blockHash']==done['hash']==profile['blockHash']==manifest['block_hash']
assert int(home['snapshot']['blockNumber'])==int(done['block'])==int(profile['block'])
pool=ConcentratedPool(profile);positions=read('liquidity-positions.json')
assert np.isclose(pool.available_eth,positions['totalEthPrincipal'])
assert np.isclose(pool.real_tokens,positions['totalTokenPrincipal'])
nb=nbformat.read(root/'standard_scenarios.ipynb',as_version=4);nbformat.validate(nb)
code=[c for c in nb.cells if c.cell_type=='code']
assert all(c.execution_count is not None for c in code),'Unexecuted cells'
assert not any(o.output_type=='error' for c in code for o in c.outputs),'Notebook error output'
result=json.loads((root/'notebook-results/notebook-results.json').read_text())
assert result['block_hash']==manifest['block_hash']
assert np.isclose(sum(result['subjective_weights'].values()),1)
for name,digest in result['evidence_sha256'].items():
    assert hashlib.sha256((root/'notebook-evidence'/name).read_bytes()).hexdigest()==digest
for name in ['peak-summary.csv','position-summary.csv','wallet-risk-reward.csv','third-party-participation.csv','timing-precision.csv','liquidity-depth.csv']:
    table=pd.read_csv(root/'notebook-results'/name)
    assert len(table)>0 and np.isfinite(table.select_dtypes('number')).all().all(),name
assert len(pd.read_csv(root/'notebook-results/peak-summary.csv'))==len(result['scenarios'])
print(f'OK: {len(manifest["sha256"])} evidence files; {len(code)} executed code cells; saved tables and liquidity reconcile.')
