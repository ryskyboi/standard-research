"""Pinned three-recipient attribution and cash accounting; no ownership inference."""
from pathlib import Path
from collections import defaultdict
import json
import pandas as pd
from participant_flows import ROOT,read,key,utc

def main():
 p=ROOT/'buyer-investigation';snapshot=read(p/'snapshot.json');a=read(p/'targets.json')['addresses'];s={x['label']:x.get('value') for x in snapshot['state'] if x['success']}
 for name,decimals in [('STANDARD',18),('WETH',18),('USDG',6)]:assert int(s[name+'.decimals'])==decimals
 logs=read(p/'historical-target-transfers.json')+[t for t in read(p/'delta-transfers.json') if t['decoded']['from'].lower() in a or t['decoded']['to'].lower() in a]
 logs=list({(t['transactionHash'],t['logIndex']):t for t in logs}.values());logs.sort(key=key)
 edges=[];balances=defaultdict(int)
 for t in logs:
  v=t['decoded'];src=v['from'].lower();dst=v['to'].lower();q=int(v['value']);balances[src]-=q;balances[dst]+=q
  edges.append(dict(tx=t['transactionHash'],block=int(t['blockNumber'],16),log_index=int(t['logIndex'],16),sender=src,recipient=dst,tokens=q/1e18))
 pd.DataFrame(edges).to_csv(p/'target-token-history.csv',index=False)
 txs=read(p/'transactions.json');calls=[]
 for item in txs:
  t=item['transaction'];r=item['receipt'];assert t['hash']==r['transactionHash'] and t['blockHash']==r['blockHash'] and r['status']=='0x1'
  calls.append(dict(tx=t['hash'],sender=t['from'].lower(),destination=t['to'].lower(),value_ETH=int(t['value'],16)/1e18,nonce=int(t['nonce'],16),block=int(t['blockNumber'],16)))
 c=pd.DataFrame(calls);c.to_csv(p/'purchase-transactions.csv',index=False)
 protocol={x.lower() for x in read(ROOT/'notebook-evidence/home.json')['contracts'].values()}
 owners={v.lower() for k,v in s.items() if k.startswith('protocol.') and isinstance(v,str) and len(v)==42 and int(v,16)}
 direct=[]
 for e in edges:
  other=e['recipient'] if e['sender'] in a else e['sender']
  if other in protocol|owners:direct.append(e)
 assert not direct,'Review newly found protocol transfers'
 rows=[];initial=read(ROOT/'behavior-updates/2026-09-16T054047Z/evidence/wallet-balances.json');old={x['label'][:-6]:int(x['value']) for x in initial if x['label'].endswith('.token')}
 for addr in a:
  assert balances[addr]==int(s[addr+'.STANDARD']),(addr,balances[addr],s[addr+'.STANDARD'])
  rows.append(dict(address=addr,STANDARD=int(s[addr+'.STANDARD'])/1e18,ETH=int(s[addr+'.ETH'])/1e18,WETH=int(s[addr+'.WETH'])/1e18,USDG=int(s[addr+'.USDG'])/1e6,charters=int(s[addr+'.charters']),tokens_at_0540=old.get(addr,0)/1e18,recent_tokens_added=(int(s[addr+'.STANDARD'])-old.get(addr,0))/1e18,recent_purchase_transactions_submitted=int((c.sender==addr).sum()),recent_submitted_ETH=float(c.loc[c.sender==addr,'value_ETH'].sum()),known_protocol_address=addr in protocol|owners))
 pd.DataFrame(rows).to_csv(p/'wallet-summary.csv',index=False)
 third=txs[-1];token_transfers=[]
 for l in third['receipt']['logs']:
  if l['topics'] and l['topics'][0].startswith('0xddf252ad') and len(l['topics'])==3 and l['address'].lower() in {v.lower() for v in snapshot['assets'].values()}:
   name=next(n for n,v in snapshot['assets'].items() if v.lower()==l['address'].lower());token_transfers.append(dict(token=name,sender='0x'+l['topics'][1][-40:],recipient='0x'+l['topics'][2][-40:],amount=int(l['data'],16)/10**int(s[name+'.decimals'])))
 pd.DataFrame(token_transfers).to_csv(p/'routed-purchase-token-legs.csv',index=False)
 route='0x5399d94d2cab7c252a6034042e1917a0e5e17a18';route_usdg=sum(x['amount'] for x in token_transfers if x['token']=='USDG' and x['sender']==route)
 assert abs(route_usdg-19999.935843)<1e-8
 assert len(c)==17 and sum(c.sender==a[0])==5 and sum(c.sender==a[1])==11
 summary=dict(snapshot_utc=utc(int(snapshot['header']['timestamp'],16)),block=int(snapshot['header']['number'],16),hash=snapshot['header']['hash'],addresses=rows,total_native_ETH=sum(x['ETH'] for x in rows),total_STANDARD=sum(x['STANDARD'] for x in rows),routed_purchase_USDG=route_usdg,routed_purchase_transaction=third['transaction']['hash'],routed_transaction_sender=third['transaction']['from'],route_contract=route,protocol_owners=sorted(owners),charter_738=dict(owner=s['charter738.owner'],branches=int(s['charter738.branchCountOf']),pending_STANDARD=int(s['charter738.pendingOf'])/1e18),full_target_token_balance_replay_reconciled=True,successful_receipts=len(c),direct_standard_transfers_to_or_from_known_protocol_wallets=direct,limitations='Native ETH funding history is not established: public explorer returned HTTP 403 and RPC trace_filter/debug_traceTransaction are unavailable. No beneficial ownership, shared private capital, other-chain assets, other token assets or customer claim on routing inventory is inferred. Zero present cash does not prevent replenishment or routed execution.')
 (p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
