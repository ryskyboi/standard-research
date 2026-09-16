"""Fresh, finite-inventory re-entry cases; conditional arithmetic, not fitted odds.

All amounts are ETH or STANDARD unless explicitly marked USDG. The AMM is the
archived initialized-tick curve. Locked liquidity remains in place by assumption.
"""
from collections import Counter,defaultdict
from pathlib import Path
import copy,json
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,load,utc
from participant_decisions import resolution_fee,future_yield
from liquidity import ConcentratedPool

def price_buy_cost(pool,target):
    """Wallet ETH needed to reach an absolute price, after any preceding trades."""
    if target<=pool.price:return 0.
    _,y=pool.curve.inventories(1/np.sqrt(target))
    return float((y*pool.scale-pool.available_eth)/((1-pool.buy_tax)*(1-pool.lp_fee)))

def allocate(c,w,price,count,used_today,use_wallet=True):
    """Feasible allocation respecting shared wallets and remaining daily capacity.

    Zero fresh tokens is a constructive feasibility result, not predicted demand.
    Greedy allocation is not a proof of positive minimum required buying.
    """
    rows=[];c=c.reset_index(drop=True);ledger=c.pending_tokens.to_numpy().copy()
    inventory=w.set_index('address').wallet_tokens.to_dict();taken=Counter()
    for _ in range(count):
        options=[]
        for j,x in enumerate(c.itertuples()):
            if taken[x.charter_id]+used_today.get(x.charter_id,0)>=3 or x.branches+taken[x.charter_id]>=10:continue
            gap=max(0,price-ledger[j]);wallet=min(gap,inventory[x.owner]) if use_wallet else 0
            options.append((gap-wallet,gap,j,wallet))
        if not options:break
        short,gap,j,wallet=min(options);x=c.iloc[j];internal=min(price,ledger[j])
        ledger[j]-=internal;inventory[x.owner]-=wallet;taken[x.charter_id]+=1
        rows.append(dict(charter_id=int(x.charter_id),owner=x.owner,ledger_used=internal,wallet_used=wallet,new_tokens_needed=short))
    assert min(inventory.values())>=-1e-6 and ledger.min()>=-1e-6
    return pd.DataFrame(rows)

def buyback(pool,vault,depth0,p0,hours,exempt=False):
    """Hourly ticks starting now, no replenishment, conditional successful execution.

    First tick uses exact protocol depth. Later depth scales with sqrt(price),
    assuming unchanged protocol position range. Price-oracle stops are ignored:
    this is an execution upper case, not an execution forecast.
    """
    spent=0
    for _ in range(hours):
        amount=min(.10*vault,.002*depth0*np.sqrt(pool.price/p0))
        pool.buy(amount,exempt=exempt);vault-=amount;spent+=amount
    return spent

def branch_payback(cost,initial_branches,issuance,added_per_day,cap):
    """Token-only gross payback with a fixed issuance budget and finite branch cap."""
    def earned(days):
        if not added_per_day:return issuance*days/initial_branches
        until_cap=max(0,(cap-initial_branches)/added_per_day)
        growth=min(days,until_cap)
        return issuance/added_per_day*np.log1p(added_per_day*growth/initial_branches)+max(0,days-until_cap)*issuance/cap
    lo,hi=0.,max(3650.,cost*cap/issuance)
    for _ in range(60):
        mid=(lo+hi)/2
        if earned(mid)<cost:lo=mid
        else:hi=mid
    return (lo+hi)/2

def run(root=ROOT):
    evidence=root/'reentry-evidence';out=root/'reentry-results';out.mkdir(exist_ok=True)
    target=read(evidence/'target.json');stamp=int(target['header']['timestamp'],16)
    s={x['label']:x.get('value') for x in read(evidence/'state.json')}
    fee_events=read(evidence/'fee-events.json.gz')
    trade_tax=sum(int(e['decoded']['amount']) for e in fee_events if e['event']=='TaxCollected')
    lp_tax=sum(int(e['decoded']['ethAmount']) for e in fee_events if e['event']=='LpTaxCollected')
    forwarded=sum(int(e['decoded']['amount']) for e in fee_events if e['event']=='TaxesForwarded')
    fee_balance=int(s['balance.taxHook'])
    assert trade_tax+lp_tax-forwarded==fee_balance,'Unexplained hook ETH'
    (out/'fee-reconciliation.json').write_text(json.dumps(dict(trading_tax_wei=str(trade_tax),lp_eth_tax_wei=str(lp_tax),forwarded_wei=str(forwarded),observed_balance_wei=str(fee_balance),unexplained_difference_wei='0',event_counts=dict(Counter(e['event'] for e in fee_events))),indent=2)+'\n')
    w=pd.read_csv(out/'participants/wallets.csv.gz');c=pd.read_csv(out/'participants/charters.csv')
    t=pd.read_csv(out/'participants/trades.csv.gz');windows=pd.read_csv(out/'participants/windows.csv')
    profile=read(evidence/'liquidity.json');pool=ConcentratedPool(profile)
    N=int(s['bank.totalBranches']);D=int(s['bank.totalPendingLive'])/1e18
    issuance=int(s['bank.baseIssuancePerDay'])/1e18*int(s['bank.multiplierWad'])/1e18
    _,_,old_events=load(root);delta=read(evidence/'delta-events.json.gz');events=old_events+delta
    withdrawals=[e for e in events if e['event']=='Withdrawn']
    W=sum(int(x['value'])/1e18 for x in read(evidence/'withdrawals.json'))
    # Asset metadata is observed: the collector's 'wrapped' label is actually USDG.
    assets=defaultdict(dict)
    for x in read(evidence/'wallet-balances.json'):
        a,k=x['label'].rsplit('.',1);assets[a][k]=int(x['value'])/(1e6 if k=='wrapped' else 1e18)
    w['weth']=w.address.map(lambda a:assets.get(a,{}).get('routed',np.nan))
    w['usdg']=w.address.map(lambda a:assets.get(a,{}).get('wrapped',np.nan))
    # No invented ETH/USD exchange rate and no assumption that cash is committed.
    w.to_csv(out/'wallet-capital.csv.gz',index=False)
    capitals=w.groupby('cohort').agg(addresses=('address','count'),tokens=('wallet_tokens','sum'),native_ETH=('native_eth','sum'),WETH=('weth','sum'),USDG=('usdg','sum'),cash_observations=('weth','count'))
    capitals.to_csv(out/'capital-by-cohort.csv')
    day=int(s['license.currentDay']);used=Counter()
    license_events=[e for e in events if e['event']=='LicensesPurchased']
    for e in license_events:
        d=e['decoded']
        if int(d['day'])==day:used[int(d['charterId'])]+=int(d['count'])
    price=int(s['license.currentPrice'])/1e18;remaining=int(s['license.remainingToday'])
    allocation=allocate(c,w,price,remaining,used);allocation.to_csv(out/'remaining-license-allocation.csv',index=False)
    ledger_only=allocate(c,w,price,remaining,used,False)
    capacity={int(x.charter_id):min(3-used[x.charter_id],10-x.branches) for x in c.itertuples()}
    owner_capacity=defaultdict(int)
    for x in c.itertuples():owner_capacity[x.owner]+=max(0,capacity[x.charter_id])
    cumulative=np.cumsum(sorted(owner_capacity.values(),reverse=True))
    minowners=int(np.searchsorted(cumulative,remaining)+1)
    wallet_by_owner=w.set_index('address').wallet_tokens
    unilateral=c.copy();unilateral['capacity_today']=unilateral.charter_id.map(capacity)
    unilateral['can_fund_one_from_ledger']=(unilateral.pending_tokens>=price)&(unilateral.capacity_today>0)
    unilateral['can_fund_one_from_ledger_and_wallet']=(unilateral.pending_tokens+unilateral.owner.map(wallet_by_owner)>=price)&(unilateral.capacity_today>0)
    unilateral.to_csv(out/'charter-license-options.csv',index=False)
    wait=[];anchor=int(s['license.auctionAnchor'])+day*86400
    for h in [0,2,4,8,12]:
        elapsed=stamp+h*3600-anchor
        p=int(s['license.dayFloorPrice'])/1e18+(int(s['license.dayStartPrice'])-int(s['license.dayFloorPrice']))/1e18*2**(-elapsed/int(s['license.dayHalfLife']))
        a=c.copy();a.pending_tokens+=h/24*issuance/N*a.branches
        alloc=allocate(a,w,p,remaining,used)
        wait.append(dict(elapsed_days=h/24,timestamp_utc=utc(stamp+h*3600),hours_wait=h,license_price=p,foregone_issuance_one_branch=h/24*issuance/N,all_remaining_licenses_tokens=p*remaining,all_fresh_ETH_at_snapshot_curve=pool.quote_buy(p*remaining),feasible_fresh_tokens=alloc.new_tokens_needed.sum(),fully_internal_licenses=int((alloc.ledger_used>=p-1e-6).sum())))
    pd.DataFrame(wait).to_csv(out/'license-waiting.csv',index=False)
    # Exact current curve; price target totals include offsetting the stated sales.
    hurdle=[];peak=.00019197904484326013
    for sold in [0,1e6,3e6,5e6]:
        p=copy.deepcopy(pool);p.sell(sold)
        for ratio in [1.05,1.10,1.25,1.5,peak/pool.price]:
            hurdle.append(dict(sold_tokens_first=sold,target_return=ratio-1,target_price_ETH=pool.price*ratio,fresh_wallet_ETH=price_buy_cost(p,pool.price*ratio)))
    pd.DataFrame(hurdle).to_csv(out/'price-hurdles.csv',index=False)
    vault=int(s['balance.contractionVault'])/1e18;depth=int(s['vault.poolEthDepth'])/1e18
    buybacks=[]
    for hours in [1,6,24,48]:
        for exempt in [False,True]:
            p=copy.deepcopy(pool);spend=buyback(p,vault,depth,pool.price,hours,exempt)
            buybacks.append(dict(hours=hours,elapsed_days=hours/24,through_utc=utc(stamp+hours*3600),buy_tax_exemption_assumed=exempt,ETH_spent=spend,vault_remaining=vault-spend,price_return=p.price/pool.price-1))
    pd.DataFrame(buybacks).to_csv(out/'buyback-cases.csv',index=False)
    support=[]
    for name,eth in [('whole_current_buyback_balance_eventually',vault),('current_POL_balance_half_swap_only',int(s['balance.polManager'])/2e18),('all_remaining_licenses_fresh_bought_now',pool.quote_buy(remaining*price))]:
        p=copy.deepcopy(pool);p.buy(eth)
        support.append(dict(case=name,buy_wallet_ETH=eth,no_seller_price_return=p.price/pool.price-1))
    pd.DataFrame(support).to_csv(out/'isolated-support-cases.csv',index=False)
    # Withdrawals are OPTIONAL, fee-sensitive internal liabilities, not calendar unlocks.
    branch=[]
    for days in [0,1,2]:
        available=D+days*issuance
        for fraction in [.10,.25,.50,1.]:
            gross=available*fraction
            # Integrate the crowd's sequential exits; early vs late fee differs.
            cumulative=0.;net=0
            for _ in range(1000):
                chunk=gross/1000;fee=resolution_fee(chunk,W+cumulative,available-cumulative)
                net+=chunk*(1-fee);cumulative+=chunk
            p=copy.deepcopy(pool);proceeds,_,_=p.sell(net)
            branch.append(dict(elapsed_days=days,timestamp_utc=utc(stamp+days*86400),fraction_of_ledger_withdrawn=fraction,gross_ledger= gross,net_tokens_minted=net,weighted_resolution_fee=1-net/gross,net_ETH_to_sellers=proceeds,price_return_without_buys=p.price/pool.price-1))
    pd.DataFrame(branch).to_csv(out/'optional-bank-exits.csv',index=False)
    active=w[w.sell_tokens_6h>0];inactive=w[w.cohort=='inactive_or_unattributed']
    active_stock=active.wallet_tokens.sum();dormant=inactive.wallet_tokens.sum()
    a6=windows[(windows.window_hours==6)&(windows.side=='buy')].iloc[0].all_pool_eth/.98
    a20=windows[(windows.window_hours<.34)&(windows.side=='buy')].iloc[0].all_pool_eth/.98*18
    scenarios=[];paths=[]
    cases=[('weak_entry_replenished_sellers',a20,.75,.05,False),('recent_6h_buying_returns',a6,.75,.05,False),('seller_exhaustion_rebound',a6,.25,.01,False),('buyers_plus_executed_buybacks',a6*1.5,.50,.02,True),('dormant_holder_exit_wave',a6,.90,.15,True)]
    for name,buys,active_fraction,dormant_fraction,execute in cases:
        p=copy.deepcopy(pool);stock_sell=active_stock*active_fraction+dormant*dormant_fraction
        reserve=vault;spent=0
        for step in range(24):
            p.sell(stock_sell/24);p.buy(buys/24)
            if execute and step%4==0:
                amount=min(.1*reserve,.002*depth*np.sqrt(p.price/pool.price));p.buy(amount);reserve-=amount;spent+=amount
            paths.append(dict(case=name,elapsed_days=(step+1)/96,timestamp_utc=utc(stamp+(step+1)*900),price_ETH=p.price,price_return=p.price/pool.price-1))
        scenarios.append(dict(case=name,horizon_hours=6,through_utc=utc(stamp+21600),ordinary_buyer_ETH=buys,active_inventory_fraction_sold=active_fraction,dormant_inventory_fraction_sold=dormant_fraction,tokens_sold=stock_sell,buyback_ETH=spent,ending_price_return=p.price/pool.price-1))
    pd.DataFrame(scenarios).to_csv(out/'six-hour-cases.csv',index=False);pd.DataFrame(paths).to_csv(out/'six-hour-paths.csv',index=False)
    # Price-flat flow absorption, no need to predict external buyers' valuations.
    emissions=[]
    for fraction in [.25,.5,1.]:
        net=issuance*fraction*.98
        emissions.append(dict(fraction_daily_issuance_withdrawn=fraction,STANDARD_sellable_before_AMM=net,buyer_ETH_at_spot_to_absorb=net*pool.price/(.98),note='Small-flow approximation; assumes quiet 2% resolution fee. Issuance remains internal until retirement.'))
    pd.DataFrame(emissions).to_csv(out/'issuance-absorption.csv',index=False)
    payoff=[]
    for added in [0,50,100]:
        days=branch_payback(price,N+1,issuance,added,len(c)*10)
        payoff.append(dict(new_branches_per_day=added,gross_token_payback_days=days,payback_utc=utc(stamp+days*86400),branch_cap=len(c)*10,assumption='Constant issuance and token price; no fees, no retirements, no ETH Charters. Not a return forecast.'))
    pd.DataFrame(payoff).to_csv(out/'branch-payback.csv',index=False)
    tick=min(.1*vault,.002*depth)
    live_owners=c.owner.nunique();pending_reconciled=abs(c.pending_tokens.sum()-D)<1e-6
    assert pending_reconciled and c.branches.sum()==N
    totals=Counter(e['event'] for e in events)
    # Address counts are never labeled people or independent capital owners.
    recent=t[t.timestamp>=stamp-6*3600];first_buy=t[t.side=='buy'].groupby('address').timestamp.min()
    new=recent[(recent.side=='buy')&(recent.address.map(first_buy)>=stamp-21600)]
    bybuyer=new.groupby('address').pool_eth.sum()
    meta=dict(snapshot_utc=utc(stamp),block=int(target['header']['number'],16),block_hash=target['header']['hash'],price_ETH=pool.price,actual_pool_ETH=pool.available_eth,active_virtual_ETH=pool.eth,protocol_buyback_depth_ETH=depth,live_charters=len(c),owners=live_owners,branches=N,branches_retired_lifetime=1000+sum(int(e['decoded']['count']) for e in license_events)-N,charters_dissolved_lifetime=1000-len(c),withdrawal_events_lifetime=len(withdrawals),withdrawal_gross_lifetime=W,bank_pending_tokens=D,branch_issuance_daily=issuance,one_branch_daily=issuance/N,license_price_tokens=price,license_gross_payback_days=price/(issuance/N),remaining_licenses=remaining,minimum_addresses_to_fill_quota_from_capacity=minowners,capacity_eligible_charters=sum(v>0 for v in capacity.values()),capacity_eligible_owners=sum(v>0 for v in owner_capacity.values()),charters_can_fund_one_internally=int(unilateral.can_fund_one_from_ledger.sum()),charters_can_fund_one_with_wallet=int(unilateral.can_fund_one_from_ledger_and_wallet.sum()),feasible_remaining_license_new_tokens=allocation.new_tokens_needed.sum(),feasible_remaining_license_wallet_tokens=allocation.wallet_used.sum(),feasible_remaining_license_ledger_tokens=allocation.ledger_used.sum(),internal_only_fresh_tokens=ledger_only.new_tokens_needed.sum(),max_license_fresh_tokens_now=remaining*price,max_license_fresh_ETH_now=pool.quote_buy(remaining*price),current_buyback_ETH=vault,current_tick_ETH=tick,hook_balance_ETH=int(s['balance.taxHook'])/1e18,pol_idle_ETH=int(s['balance.polManager'])/1e18,expansion_vault_ETH=int(s['balance.expansionVault'])/1e18,epoch_net_flow_ETH=int(s['hook.epochNetFlow'])/1e18,epoch_end_utc=utc(int(s['bank.epochEnd'])),next_license_reset_utc=utc(anchor+86400),recent_seller_addresses=len(active),recent_sellers_empty=int((active.wallet_tokens<1e-9).sum()),recent_seller_inventory=active_stock,inactive_inventory=dormant,all_non_protocol_wallet_tokens=w.wallet_tokens.sum(),new_buyer_addresses_6h=len(bybuyer),new_buyer_median_pool_ETH=float(bybuyer.median()),new_buyer_mean_pool_ETH=float(bybuyer.mean()),pool_ETH_per_1m_tokens_at_spot=pool.price*1e6,pending_sum_reconciled=pending_reconciled,withdrawals=withdrawals)
    (out/'summary.json').write_text(json.dumps(meta,indent=2,default=lambda x:x.item())+'\n')
    print(json.dumps({k:v for k,v in meta.items() if k!='withdrawals'},indent=2,default=lambda x:x.item()));return meta

if __name__=='__main__':run()
