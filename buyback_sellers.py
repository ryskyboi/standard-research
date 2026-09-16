"""Remaining recent-seller inventory and conditional buyback trade economics."""
from collections import defaultdict
import copy,json
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,key,ZERO,POOL,POL,SECONDARY,utc
from liquidity import ConcentratedPool
from reentry_model import buyback

def run(root=ROOT):
    e=root/'buyback-seller-evidence';out=root/'buyback-seller-results';out.mkdir(exist_ok=True)
    snapshot=read(e/'target.json');pin=int(snapshot['header']['timestamp'],16);end=int(snapshot['header']['number'],16)
    s={x['label']:x.get('value') for x in snapshot['state']}
    old=read(root/'reentry-evidence/target.json');start=int(old['header']['number'],16);starttime=int(old['header']['timestamp'],16)
    stamp=lambda b:starttime+(b-start)/(end-start)*(pin-starttime)
    balances=defaultdict(int)
    for row in read(root/'reentry-evidence/wallet-balances.json'):
        if row['label'].endswith('.token'):balances[row['label'][:-6]]=int(row['value'])
    transfers=read(e/'transfers.json.gz');events=read(e/'events.json.gz')
    nets=defaultdict(lambda:defaultdict(int));evs=defaultdict(list)
    for x in sorted(transfers,key=key):
        d=x['decoded'];a=d['from'].lower();b=d['to'].lower();q=int(d['value']);h=x['transactionHash']
        if a!=ZERO:balances[a]-=q
        if b!=ZERO:balances[b]+=q
        nets[h][a]-=q;nets[h][b]+=q
    assert min(balances.values())>=0
    assert sum(balances.values())==int(s['token.totalSupply'])
    for k,v in s.items():
        if k.startswith('custody.'):assert balances[k[8:]]==int(v)
    custody={a.lower() for a in read(root/'notebook-evidence/home.json')['contracts'].values()}|{ZERO,POOL,POL}|SECONDARY
    for x in events:evs[x['transactionHash']].append(x)
    rows=[];unresolved=[]
    for h,es in evs.items():
        swaps=[x for x in es if x['event']=='Swap']
        if not swaps:continue
        sides={'buy' if int(x['decoded']['amount1'])>0 else 'sell' for x in swaps}
        eth=sum(abs(int(x['decoded']['amount0'])) for x in swaps)/1e18
        if len(sides)!=1:unresolved.append(dict(tx=h,ETH=eth,reason='mixed_sides'));continue
        side=next(iter(sides));sign=1 if side=='buy' else -1
        q=sum(abs(int(x['decoded']['amount1'])) for x in swaps)
        actors={a:sign*v for a,v in nets[h].items() if a not in custody and sign*v>0}
        opposite={a:-sign*v for a,v in nets[h].items() if a not in custody and sign*v<0}
        lp=any(x['event']=='ModifyLiquidity' for x in es)
        accepted=bool(actors and not opposite and sum(actors.values())==q and not lp)
        if not accepted and len(actors)==1 and not lp and sum(actors.values())>=q:
            destinations={a for a,v in nets[h].items() if sign*v>0}
            if destinations==set(actors) and nets[h].get(POOL,0)==-sign*q:accepted=True;actors={next(iter(actors)):q}
        # Sell split routes need a unique source, rather than a unique destination.
        if not accepted and side=='sell' and len(actors)==1 and not lp and sum(actors.values())>=q:
            sources={a for a,v in nets[h].items() if v<0}
            if sources==set(actors) and nets[h].get(POOL,0)==q:accepted=True;actors={next(iter(actors)):q}
        if not accepted:unresolved.append(dict(tx=h,ETH=eth,reason='unresolved_route'));continue
        block=int(swaps[0]['blockNumber'],16)
        for a,qty in actors.items():rows.append(dict(address=a,side=side,tokens=qty/1e18,pool_eth=eth*qty/q,block=block,timestamp=stamp(block),tx=h))
    oldtrades=pd.read_csv(root/'reentry-results/participants/trades.csv.gz')
    trades=pd.concat([oldtrades,pd.DataFrame(rows)],ignore_index=True)
    trades.to_csv(out/'trades.csv.gz',index=False);pd.DataFrame(unresolved).to_csv(out/'new-unresolved.csv',index=False)
    # Window membership is approximate; integer final inventory is not interpolated.
    windows=[];sellers={}
    for hours in [1/3,2,6,24]:
        t=trades[(trades.timestamp>=pin-hours*3600)&(trades.side=='sell')]
        a=t.groupby('address').agg(sold_tokens=('tokens','sum'),sell_pool_ETH=('pool_eth','sum'))
        a['remaining_tokens']=[balances[x]/1e18 for x in a.index]
        a['currently_empty']=a.remaining_tokens<1e-9
        a=a.sort_values('remaining_tokens',ascending=False);a.to_csv(out/f'sellers-{hours:g}h.csv')
        p=ConcentratedPool(read(e/'liquidity.json'));before=p.price;proceeds,_,_=p.sell(a.remaining_tokens.sum())
        windows.append(dict(window_hours=hours,from_utc_approx=utc(pin-hours*3600),to_utc=utc(pin),selling_addresses=len(a),empty_addresses=int(a.currently_empty.sum()),remaining_tokens=a.remaining_tokens.sum(),sold_tokens=t.tokens.sum(),sell_pool_ETH=t.pool_eth.sum(),if_all_remaining_sold_net_ETH=proceeds,if_all_remaining_sold_price_change=p.price/before-1))
        sellers[hours]=a
    pd.DataFrame(windows).to_csv(out/'seller-windows.csv',index=False)
    profile=read(e/'liquidity.json');base=ConcentratedPool(profile)
    vault=int(s['ETH.vault'])/1e18;depth=int(s['vault.poolEthDepth'])/1e18;stock=sellers[6].remaining_tokens.sum()
    remaining_all=sum(q for a,q in balances.items() if a not in custody)/1e18
    # Investor buys first, protocol buys later, investor sells last. Includes own impact.
    def case(hours,fraction,budget=1.,extra=0.,exempt=False):
        p=ConcentratedPool(profile);tokens,_=p.buy(budget);reserve=vault;spent=0
        for step in range(hours):
            p.sell(stock*fraction/hours)
            p.buy(extra/hours)
            amount=min(.10*reserve,.002*depth*np.sqrt(p.price/base.price))
            p.buy(amount,exempt=exempt);reserve-=amount;spent+=amount
        price_before_exit=p.price;received=p.quote_sell(tokens)
        return dict(hours=hours,elapsed_days=hours/24,through_utc=utc(pin+hours*3600),fraction_recent_seller_inventory_sold=fraction,tokens_sold=stock*fraction,investor_entry_ETH=budget,other_buyer_ETH=extra,buyback_tax_exempt_assumed=exempt,buyback_ETH=spent,spot_return_before_investor_exit=price_before_exit/base.price-1,investor_exit_ETH=received,investor_net_return=received/budget-1)
    cases=[]
    for h in [1,6,24,48]:
        for frac in [0,.25,.5,1.]:cases.append(case(h,frac))
    for h in [6,24,48]:cases.append(case(h,0,exempt=True))
    pd.DataFrame(cases).to_csv(out/'buyback-vs-sellers.csv',index=False)
    # Extra external buying needed to make the illustrative 1 ETH round trip break even.
    hurdles=[]
    for h in [6,24]:
        for frac in [0,.25,.5,1.]:
            lo,hi=0.,2000.
            for _ in range(40):
                mid=(lo+hi)/2
                if case(h,frac,extra=mid)['investor_net_return']<0:lo=mid
                else:hi=mid
            hurdles.append(dict(hours=h,fraction_recent_seller_inventory_sold=frac,extra_external_buyer_ETH=(lo+hi)/2))
    pd.DataFrame(hurdles).to_csv(out/'break-even-external-buying.csv',index=False)
    support=[]
    for h in [1,6,24,48]:
        p=copy.deepcopy(base);q0=p.real_tokens;spent=buyback(p,vault,depth,base.price,h)
        support.append(dict(hours=h,buyback_ETH=spent,tokens_bought_and_burned=q0-p.real_tokens,share_of_recent_seller_inventory=(q0-p.real_tokens)/stock,spot_return=p.price/base.price-1))
    pd.DataFrame(support).to_csv(out/'buyback-absorption.csv',index=False)
    # A standalone all-current-vault purchase is a ceiling, not an immediately executable action.
    full=copy.deepcopy(base);tokens,_=full.buy(vault)
    meta=dict(snapshot_utc=utc(pin),block=end,price_ETH=base.price,actual_pool_ETH=base.available_eth,total_minted=int(s['token.totalSupply'])/1e18,holder_side_tokens=remaining_all,recent_seller_inventory=stock,other_holder_inventory=remaining_all-stock,recent_seller_top5_inventory=sellers[6].remaining_tokens.head(5).sum(),recent_seller_top10_inventory=sellers[6].remaining_tokens.head(10).sum(),current_vault_ETH=vault,entire_vault_tokens_bought=tokens,entire_vault_no_seller_price_return=full.price/base.price-1,current_tick_ETH=min(.1*vault,.002*depth),new_delta_unresolved_transactions=len(unresolved),new_delta_canonical_ETH=sum(abs(int(x['decoded']['amount0']))/1e18 for x in events if x['event']=='Swap'),new_delta_unattributed_ETH=sum(x['ETH'] for x in unresolved),integer_total_supply_reconciled=True,known_custody_balances_reconciled=True,limitations='Recent means addresses attributed to canonical-pool sells in the chosen trailing window, not all potential sellers. Other-venue-only or unresolved sellers may be missing. Remaining balances replay all STANDARD transfers from the prior individually reconciled snapshot, including new buys/transfers; inventory does not imply intention. Future paths assume successful hourly owner execution, fixed liquidity/taxes, no replenishment or additional branch withdrawals, and modeled counterparty selling spread evenly. The 48h case crosses epoch settlement but deliberately excludes any replenishment.')
    (out/'summary.json').write_text(json.dumps(meta,indent=2,default=lambda x:x.item())+'\n')
    print(json.dumps(meta,indent=2,default=lambda x:x.item()));print(pd.DataFrame(windows).to_string(index=False));print(pd.DataFrame(cases).to_string(index=False))
    return meta

if __name__=='__main__':run()
