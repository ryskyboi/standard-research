"""Dated spot-entry sensitivity, with rebuilt tick liquidity and observed flows."""
import copy,json
from collections import defaultdict
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,key,utc,POOL,POL,ZERO,SECONDARY
from analyze_trade_tape import actor_for
from liquidity import ConcentratedPool,LiquidityCurve
from reentry_model import buyback

def main():
 out=ROOT/'decision-evidence/2026-09-16T0908';d=read(out/'tape.json');prev=read(ROOT/'tape-evidence/tape.json');s={x['label']:x['value'] for x in d['state']}
 profile=read(ROOT/'behavior-updates/2026-09-16T054047Z/evidence/liquidity.json');ticks={x['tick']:{k:int(v) for k,v in x.items()} for x in profile['ticks']}
 es=sorted(prev['events']+d['events'],key=key)
 for e in es:
  if e['event']!='ModifyLiquidity':continue
  v=e['decoded'];delta=int(v['liquidityDelta'])
  for t,sign in [(int(v['tickLower']),1),(int(v['tickUpper']),-1)]:
   ticks.setdefault(t,dict(tick=t,liquidityGross=0,liquidityNet=0));ticks[t]['liquidityGross']+=delta;ticks[t]['liquidityNet']+=sign*delta
 assert all(x['liquidityGross']>=0 for x in ticks.values())
 profile['ticks']=[{k:str(v) if k!='tick' else v for k,v in x.items()} for x in ticks.values() if x['liquidityGross']]
 profile.update(block=int(d['header']['number'],16),blockHash=d['header']['hash'],sqrtPriceX96=s['slot0'][0]);(out/'liquidity-replayed.json').write_text(json.dumps(profile,indent=2)+'\n')
 lp=int(s['slot0'][3])/1e6;b=int(s['buyTaxNowBps'])/1e4;st=int(s['sellTaxNowBps'])/1e4;p=ConcentratedPool(profile,lp,b,st)
 # Reconcile active integer liquidity against the final observed Swap event.
 last=next(x for x in reversed(es) if x['event']=='Swap');active=sum(int(x['liquidityNet']) for x in profile['ticks'] if x['tick']<=int(last['decoded']['tick']))
 assert active==int(last['decoded']['liquidity'])
 hs={int(h['number'],16):int(h['timestamp'],16) for h in d['headers']};bs=sorted(hs);pin=int(d['header']['timestamp'],16)
 home=read(ROOT/'notebook-evidence/home.json');custody={a.lower() for a in home['contracts'].values()}|{POOL,POL,ZERO}|SECONDARY
 bytx=defaultdict(list);evtx=defaultdict(list)
 for t in d['transfers']:bytx[t['transactionHash']].append(t)
 for e in d['events']:evtx[e['transactionHash']].append(e)
 rows=[]
 for tx,events in evtx.items():
  sw=[e for e in events if e['event']=='Swap']
  if not sw:continue
  for e in sw:
   v=e['decoded'];ts=float(np.interp(int(e['blockNumber'],16),bs,[hs[x] for x in bs]));rows.append(dict(tx=tx,timestamp=ts,utc_approx=utc(ts),side='buy' if int(v['amount0'])<0 else 'sell',pool_eth=abs(int(v['amount0']))/1e18,actor=actor_for(events,bytx[tx],custody)))
 f=pd.DataFrame(rows);f.to_csv(out/'trades.csv.gz',index=False);windows=[]
 for minutes in [20,60,120]:
  g=f[f.timestamp>=pin-minutes*60]
  for side in ['buy','sell']:
   a=g[g.side==side];v=a[a.actor!=''].groupby('actor').pool_eth.sum().sort_values(ascending=False)
   windows.append(dict(minutes=minutes,side=side,eth=a.pool_eth.sum(),transactions=len(a),attributed_eth=v.sum(),addresses=len(v),top_address=v.index[0] if len(v) else '',top_eth=v.iloc[0] if len(v) else 0,top3_eth=v.head(3).sum()))
 pd.DataFrame(windows).to_csv(out/'flow-windows.csv',index=False)
 # Replay all transfers since the full snapshot and verify every watched balance.
 balances={x['label'][:-6]:int(x['value']) for x in read(ROOT/'behavior-updates/2026-09-16T054047Z/evidence/wallet-balances.json') if x['label'].endswith('.token')}
 for t in sorted(prev['transfers']+d['transfers'],key=key):
  v=t['decoded'];a=v['from'].lower();z=v['to'].lower();q=int(v['value']);balances[a]=balances.get(a,0)-q;balances[z]=balances.get(z,0)+q
 for k,v in s.items():
  if k.startswith('wallet.'):assert balances[k[7:]]==int(v),(k,balances[k[7:]],v)
 def case(extra,sells):
  x=copy.deepcopy(p);q,_=x.buy(1);x.sell(sells);x.buy(extra);price=x.price;cash=x.quote_sell(q)
  return dict(other_buy_ETH=extra,other_sells_STANDARD=sells,spot_change=price/p.price-1,entry_ETH=1,exit_ETH=cash,net_return=cash-1)
 scenarios=[case(e,t) for t in [0,250000,750000] for e in [50,150,300]]
 pd.DataFrame(scenarios).to_csv(out/'entry-scenarios.csv',index=False)
 hurdles=[]
 for sells in [0,250000,750000]:
  lo,hi=0.,2000.
  for _ in range(50):
   mid=(lo+hi)/2
   if case(mid,sells)['net_return']<0:lo=mid
   else:hi=mid
  hurdles.append(dict(other_sells_STANDARD=sells,other_buy_ETH_break_even=(lo+hi)/2))
 bb=copy.deepcopy(p);q,_=bb.buy(1);spent=buyback(bb,int(s['vaultETH'])/1e18,int(s['poolEthDepth'])/1e18,p.price,24);ret=bb.quote_sell(q)-1
 friction=(1-b)*(1-lp)**2*(1-st);payoffs=[dict(spot_move=z,net_return=friction*(1+z)-1) for z in [-.10,0,.05,.10,.20]]
 summary=dict(snapshot_utc=utc(pin),block=profile['block'],hash=profile['blockHash'],price_ETH=p.price,change_since_0616=p.price/prev['price_ETH']-1,buy_ETH_since_0616=d['buy_ETH'],sell_ETH_since_0616=d['sell_ETH'],current_vault_ETH=int(s['vaultETH'])/1e18,lastTickAt=s['lastTickAt'],licenses_remaining=s['remainingToday'],buy_tax=b,sell_tax=st,lp_fee=lp,small_trade_break_even_rise=1/friction-1,payoffs=payoffs,flow_windows=windows,break_even=hurdles,buyback_24h_no_sellers_net_return=ret,buyback_24h_spent_ETH=spent,active_liquidity_reconciled=True,watched_balances_reconciled=True,assumptions='Illustrative 1 ETH spot entry and exit; unchanged current liquidity/taxes, no gas/router costs; sellers act before modeled new buyers. Amounts are conditional requirements, not forecasts. Future locked liquidity retained. Buyback case assumes successful hourly execution; none observed. Window times interpolated. Address concentration is not beneficial-owner concentration.')
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));print(pd.DataFrame(scenarios).to_string(index=False))
if __name__=='__main__':main()
