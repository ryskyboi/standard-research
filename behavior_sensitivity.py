"""Numerical/decision-rule sensitivity, not additional probability-weighted forecasts."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
import pandas as pd
from behavior_model import Config,simulate_job
from participant_flows import ROOT

def run(root=ROOT):
    configs=[Config(name='Wallet actions first',wallet_first=True),
             Config(name='Half-sized time step',dt_hours=.125),
             Config(name='No speculative game prefunding',prefund_enabled=False),
             Config(name='Seven-day branch valuation',valuation_days=7)]
    jobs=[(i,c,s,root) for i,c in enumerate(configs) for s in range(2)]
    rows=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for _,_,p,e,a,summary,flow in pool.map(simulate_job,jobs):
            rows.append({**summary,**{k:float(a[k].abs().max()) for k in ['ETH_error','token_error','ledger_error']}})
    pd.DataFrame(rows).to_csv(root/'behavior-results/assumption-sensitivity.csv',index=False)
    (root/'behavior-results/sensitivity-configs.json').write_text(json.dumps([asdict(c) for c in configs],indent=2)+'\n')
    print(pd.DataFrame(rows)[['case','seed','ending_price_return','license_fresh_ETH','game_prefund_ETH','retired']].to_string(index=False))

if __name__=='__main__':run()
