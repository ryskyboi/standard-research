"""Compare a new focused market check with the preceding pinned observations."""
import sys,json,copy
from collections import defaultdict
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,key,utc,POOL,POL,ZERO,SECONDARY
from analyze_trade_tape import actor_for
from liquidity import ConcentratedPool

def main():
 out=ROOT/sys.argv[1];d=read(out/'tape.json');prior=read(ROOT/'decision-evidence/2026-09-16T0908/tape.json');bsnap=read(ROOT/'buyer-investigation/snapshot.json')
 s={x['label']:x['value'] for x in d['state']};old={x['label']:x['value'] for x in prior['state']};buyer={x['label']:x['value'] for x in bsnap['state'] if x['success']};pin=int(d['header']['timestamp'],16);cut=int(prior['header']['number'],16);bcut=int(bsnap['header']['number'],16)
 assert d['from_header']['hash']==prior['header']['hash'],'Collector must start at the 09:11 baseline'
 targets=read(ROOT/'buyer-investigation/targets.json')['addresses'];home=read(ROOT/'notebook-evidence/home.json');custody={a.lower() for a in home['contracts'].values()}|{POOL,POL,ZERO}|SECONDARY
 events=sorted(prior['events']+d['events'],key=key);transfers=prior['transfers']+d['transfers'];ev=defaultdict(list);ts=defaultdict(list)
 for e in events:ev[e['transactionHash']].append(e)
 for t in transfers:ts[t['transactionHash']].append(t)
 anchors={int(h['number'],16):int(h['timestamp'],16) for h in prior['headers']+d['headers']};blocks=sorted(anchors)
 rows=[]
 for tx,es in ev.items():
  actor=actor_for(es,ts[tx],custody)
  for e in es:
   if e['event']!='Swap':continue
   v=e['decoded'];b=int(e['blockNumber'],16);stamp=float(np.interp(b,blocks,[anchors[x] for x in blocks]));rows.append(dict(tx=tx,block=b,timestamp=stamp,utc_approx=utc(stamp),actor=actor,side='buy' if int(v['amount0'])<0 else 'sell',pool_eth=abs(int(v['amount0']))/1e18,tokens=abs(int(v['amount1']))/1e18,price=2**192/int(v['sqrtPriceX96'])**2))
 f=pd.DataFrame(rows);fresh=f[f.block>cut];assert abs(fresh[fresh.side=='buy'].pool_eth.sum()-d['buy_ETH'])<1e-8;assert abs(fresh[fresh.side=='sell'].pool_eth.sum()-d['sell_ETH'])<1e-8
 fresh.to_csv(out/'trades.csv.gz',index=False);windows=[]
 for minutes in [5,20,60]:
  g=f[f.timestamp>=pin-minutes*60]
  for side in ['buy','sell']:
   h=g[g.side==side];a=h[h.actor!=''].groupby('actor').pool_eth.sum().sort_values(ascending=False)
   windows.append(dict(minutes=minutes,side=side,eth=h.pool_eth.sum(),transactions=len(h),attributed_eth=a.sum(),addresses=len(a),top_address=a.index[0] if len(a) else '',top_eth=a.iloc[0] if len(a) else 0,top3_eth=a.head(3).sum()))
 pd.DataFrame(windows).to_csv(out/'windows.csv',index=False)
 wallets=[]
 for k,v in s.items():
  if not k.startswith('wallet.'):continue
  a=k[7:];initial=int(buyer[a+'.STANDARD']) if a in targets else int(old[k]);start=bcut if a in targets else cut;bal=initial;incoming=outgoing=0
  for t in d['transfers']:
   if int(t['blockNumber'],16)<=start:continue
   x=t['decoded'];q=int(x['value'])
   if x['from'].lower()==a:bal-=q;outgoing+=q
   if x['to'].lower()==a:bal+=q;incoming+=q
  assert bal==int(v),(a,bal,v)
  h=fresh[(fresh.actor==a)&(fresh.block>start)]
  wallets.append(dict(address=a,baseline_utc=utc(int((bsnap if a in targets else prior)['header']['timestamp'],16)),prior_tokens=initial/1e18,tokens=int(v)/1e18,change_tokens=(int(v)-initial)/1e18,incoming=incoming/1e18,outgoing=outgoing/1e18,attributed_buy_ETH=h.loc[h.side=='buy','pool_eth'].sum(),attributed_sell_ETH=h.loc[h.side=='sell','pool_eth'].sum(),ETH=int(s['cash.'+a+'.ETH'])/1e18 if a in targets else None,WETH=int(s['cash.'+a+'.WETH'])/1e18 if a in targets else None,USDG=int(s['cash.'+a+'.USDG'])/1e6 if a in targets else None))
 pd.DataFrame(wallets).to_csv(out/'watched-wallets.csv',index=False)
 profile=read(ROOT/'decision-evidence/2026-09-16T0908/liquidity-replayed.json');ticks={x['tick']:{k:int(v) for k,v in x.items()} for x in profile['ticks']}
 for e in d['events']:
  if e['event']!='ModifyLiquidity':continue
  v=e['decoded'];delta=int(v['liquidityDelta'])
  for t,sign in [(int(v['tickLower']),1),(int(v['tickUpper']),-1)]:
   ticks.setdefault(t,dict(tick=t,liquidityGross=0,liquidityNet=0));ticks[t]['liquidityGross']+=delta;ticks[t]['liquidityNet']+=sign*delta
 assert all(x['liquidityGross']>=0 for x in ticks.values())
 profile['ticks']=[{k:str(v) if k!='tick' else v for k,v in x.items()} for x in ticks.values() if x['liquidityGross']];profile.update(block=int(d['header']['number'],16),blockHash=d['header']['hash'],sqrtPriceX96=s['slot0'][0]);last=next(x for x in reversed(events) if x['event']=='Swap');active=sum(int(x['liquidityNet']) for x in profile['ticks'] if x['tick']<=int(last['decoded']['tick']));assert active==int(last['decoded']['liquidity'])
 (out/'liquidity.json').write_text(json.dumps(profile,indent=2)+'\n');pool=ConcentratedPool(profile,int(s['slot0'][3])/1e6,int(s['buyTaxNowBps'])/1e4,int(s['sellTaxNowBps'])/1e4)
 lo,hi=0.,2000.
 for _ in range(45):
  mid=(lo+hi)/2;x=copy.deepcopy(pool);q,_=x.buy(1);x.buy(mid)
  if x.quote_sell(q)<1:lo=mid
  else:hi=mid
 result=dict(snapshot_utc=utc(pin),block=profile['block'],hash=profile['blockHash'],price_ETH=d['price_ETH'],prior_utc=utc(int(prior['header']['timestamp'],16)),price_change=d['price_ETH']/prior['price_ETH']-1,interval_buy_ETH=d['buy_ETH'],interval_sell_ETH=d['sell_ETH'],lastTickAt=s['lastTickAt'],vault_ETH=int(s['vaultETH'])/1e18,licenses_remaining=int(s['remainingToday']),total_branches=int(s['bank.totalBranches']),bank_pending_STANDARD=int(s['bank.totalPendingLive'])/1e18,fees=dict(buy=pool.buy_tax,sell=pool.sell_tax,lp=pool.lp_fee),break_even_additional_buy_ETH_no_sellers=(lo+hi)/2,windows=windows,watched_wallets=wallets,watched_balances_reconciled=True,active_liquidity_reconciled=True,limitations='Focused canonical tape and 21 watched balances, not all holders. Window times interpolated; transaction/block order exact. Addresses not beneficial owners. Break-even is a conditional 1 ETH spot round trip with fixed current liquidity/taxes and zero other sellers, excluding gas and router fees; not a prediction.')
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
