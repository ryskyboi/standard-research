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
executed=0
for notebook in ['standard_scenarios.ipynb','rational_scenarios.ipynb','assumption_sensitivity.ipynb']:
    nb=nbformat.read(root/notebook,as_version=4);nbformat.validate(nb)
    code=[c for c in nb.cells if c.cell_type=='code']
    assert all(c.execution_count is not None for c in code),f'Unexecuted cells: {notebook}'
    assert not any(o.output_type=='error' for c in code for o in c.outputs),f'Notebook error output: {notebook}'
    executed+=len(code)
result=json.loads((root/'notebook-results/notebook-results.json').read_text())
assert result['block_hash']==manifest['block_hash']
assert np.isclose(sum(result['subjective_weights'].values()),1)
for name,digest in result['evidence_sha256'].items():
    assert hashlib.sha256((root/'notebook-evidence'/name).read_bytes()).hexdigest()==digest
for name in ['peak-summary.csv','position-summary.csv','wallet-risk-reward.csv','third-party-participation.csv','timing-precision.csv','liquidity-depth.csv']:
    table=pd.read_csv(root/'notebook-results'/name)
    assert len(table)>0 and np.isfinite(table.select_dtypes('number')).all().all(),name
assert len(pd.read_csv(root/'notebook-results/peak-summary.csv'))==len(result['scenarios'])
# New model: stale implementation hashes must never pass as reproduced results.
agent=root/'agent-results'
for name in ['run-metadata.json','assumption-audit-metadata.json']:
    meta=json.loads((agent/name).read_text())
    for source,digest in meta['source_sha256'].items():
        assert hashlib.sha256((root/source).read_bytes()).hexdigest()==digest,f'Stale model results: {source}'
    for evidence,digest in meta['evidence_sha256'].items():
        assert hashlib.sha256((root/'notebook-evidence'/evidence).read_bytes()).hexdigest()==digest
meta=json.loads((agent/'run-metadata.json').read_text())
assert meta['block_hash']==manifest['block_hash']
for name in ['scenario-summary.csv','funding-and-fees.csv','license-willingness-to-pay.csv',
             'third-party-value-worksheet.csv','capital-and-quota-sensitivity.csv',
             'forecast-errors.csv','consistency-iteration.csv','accounting-checks.csv',
             'behavioral-assumption-sensitivity.csv']:
    table=pd.read_csv(agent/name)
    assert len(table)>0 and np.isfinite(table.select_dtypes('number')).all().all(),name
summary=pd.read_csv(agent/'scenario-summary.csv')
assert len(summary)==len(meta['scenarios'])
audit=pd.read_csv(agent/'accounting-checks.csv')
assert len(audit)==meta['paths']*len(meta['scenarios'])
assert audit.max_ETH_error.max()<1e-5
assert audit.max_token_error.max()<.02
assert audit.max_ledger_error.max()<1e-5
for i,cfg in enumerate(meta['scenarios'],start=1):
    f=pd.read_csv(agent/f'{i:02d}-example-path.csv')
    assert np.isfinite(f.select_dtypes('number')).all().all()
    assert f.hour.iloc[0]==0 and np.allclose(np.diff(f.hour),cfg['dt_hours'])
    assert np.isclose(f.hour.iloc[-1],cfg['days']*24)
    assert (f.remaining_slots==cfg['max_branches']*f.charters-f.branches).all()
    assert (f.protected_branch_count==1).all()
    assert f.eth_principal.min()>=0 and f.token_principal.min()>=0
    assert f.eth_accounting_error.abs().max()<1e-5
    assert f.token_accounting_error.abs().max()<.02
    assert f.ledger_accounting_error.abs().max()<1e-5
    np.testing.assert_allclose(f.eth_principal.diff().iloc[1:],
        (f.pool_buy_eth-f.pool_sell_eth_gross+f.pol_added_eth).iloc[1:],atol=1e-6)
    assert np.isclose(f.new_capital_eth.sum(),cfg['fresh_capital_eth_day']*cfg['days'])
    if cfg['charter_open_hour'] is None:assert f.charters_created.sum()==0
    events=pd.read_csv(agent/f'{i:02d}-example-events.csv')
    licenses=events[events.event=='license'].copy()
    # Group by actual auction anchor from the same snapshot helper used by the model.
    import model as old
    old.EVIDENCE=root/'notebook-evidence'
    initial=old.snapshot()
    licenses['day']=np.floor((initial['timestamp']+licenses.hour*3600-initial['auction_anchor'])/86400).astype(int)
    assert licenses.groupby('day')['count'].sum().max()<=cfg['license_daily_cap']
    assert licenses.groupby(['day','charter'])['count'].sum().max()<=cfg['per_charter_daily_cap']
    pop=pd.read_csv(agent/f'{i:02d}-final-charters.csv')
    assert pop.branches.between(0,cfg['max_branches']).all()
# Presentation timestamps must match elapsed model time; evidence stays frozen.
from time_display import with_utc
anchor=pd.Timestamp(result['snapshot_utc'])
for source,digest in result.get('presentation_source_sha256',{}).items():
    assert hashlib.sha256((root/source).read_bytes()).hexdigest()==digest
utc_tables=0
for directory in [root/'notebook-results',agent]:
    for path in directory.glob('*.csv'):
        table=pd.read_csv(path)
        expected=with_utc(table,anchor)
        date_columns=[c for c in expected if c.endswith('_utc')]
        for col in date_columns:
            assert col in table, f'Missing UTC column: {path.name}: {col}'
            assert table[col].fillna('').equals(expected[col].fillna('')),f'Wrong UTC timestamp: {path.name}: {col}'
        utc_tables+=bool(date_columns)
print(f'UTC presentation: verified {utc_tables} tables against the frozen snapshot.')
recovery=root/'recovery-results'
meta=json.loads((recovery/'metadata.json').read_text())
assert meta['calibrated_probabilities'] is False
observation=root/'live-observations'/meta['observation']
current=json.loads((observation/'summary.json').read_text())
assert current['blockHash']==meta['block_hash'] and current['block']==meta['block']
for source,digest in meta['source_sha256'].items():
    assert hashlib.sha256((root/source).read_bytes()).hexdigest()==digest,f'Stale recovery model: {source}'
for evidence,digest in meta['evidence_sha256'].items():
    assert hashlib.sha256((observation/evidence).read_bytes()).hexdigest()==digest,f'Changed recovery evidence: {evidence}'
nb=nbformat.read(root/'recovery_update.ipynb',as_version=4);nbformat.validate(nb)
code=[c for c in nb.cells if c.cell_type=='code']
assert all(c.execution_count is not None for c in code)
assert not any(o.output_type=='error' for c in code for o in c.outputs)
executed+=len(code)
audit=pd.read_csv(recovery/'accounting-checks.csv')
assert len(audit)==len(meta['scenarios'])
assert audit.max_eth_error.max()<1e-6 and audit.max_token_error.max()<.02
paths=pd.read_csv(recovery/'scenario-paths.csv')
assert np.isfinite(paths.select_dtypes('number')).all().all()
assert paths.timestamp_utc.equals(with_utc(paths,meta['timestamp_utc']).timestamp_utc)
summary=pd.read_csv(recovery/'scenario-summary.csv')
assert len(summary)==len(meta['scenarios'])
# NaN is intentional for recovery levels never reached; never fill these with an exit time.
expected=with_utc(summary,meta['timestamp_utc'])
for col in expected:
    if col.endswith('_utc'):assert summary[col].fillna('').equals(expected[col].fillna(''))
print(f'OK: {len(manifest["sha256"])} original evidence files plus recovery pin; {executed} executed code cells across four notebooks; source hashes, UTC times, liquidity and accounting reconcile.')

# Participant attribution and separate later auction observation.
part=root/'participant-results'
pm=json.loads((part/'manifest.json').read_text())
for category in ['evidence_sha256','source_sha256']:
    for name,digest in pm[category].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, f'Changed participant artifact: {name}'
pt=json.loads((root/'strategy-current/target.json').read_text())
assert pt['header']['hash']==pm['snapshot_hash']
assert pt['allWalletTokenBalancesReconciled'] and pt['status']=='complete'
follow=json.loads((part/'followup-summary.json').read_text())
assert follow['block_hash']==pm['followup_hash']
assert abs(follow['ledger_reconciliation_error_tokens'])<1e-5
nb=nbformat.read(root/'participant_analysis.ipynb',as_version=4);nbformat.validate(nb)
code=[c for c in nb.cells if c.cell_type=='code']
assert all(c.execution_count is not None for c in code)
assert not any(o.output_type=='error' for c in code for o in c.outputs)
pdpaths=pd.read_csv(part/'conditional-paths.csv')
assert pdpaths.ETH_error.abs().max()<1e-6 and pdpaths.token_error.abs().max()<.001
print(f'Participant extension OK: {len(code)} executed cells; evidence/source hashes, pinned balances and follow-up ledger reconcile.')
