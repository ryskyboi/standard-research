"""Evidence-conditioned decisions and finite-inventory flow scenarios.

The scenarios are conditional tests, not fitted probabilities or a Nash equilibrium.
Activity persistence is estimated from observed participants. Unobserved beliefs,
new capital and dormant-holder activation remain visible scenario assumptions.
"""
from pathlib import Path
import json,copy
import numpy as np
import pandas as pd
from liquidity import ConcentratedPool
from participant_flows import ROOT,read,utc,load


def inputs(root=ROOT):
    out=root/'participant-results';w=pd.read_csv(out/'wallets.csv.gz');c=pd.read_csv(out/'charters.csv');t=pd.read_csv(out/'trades.csv.gz')
    state={x['label']:x.get('value') for x in read(root/'strategy-current/state.json')}
    target=read(root/'strategy-current/target.json');stamp=int(target['header']['timestamp'],16)
    return w,c,t,state,stamp,ConcentratedPool(read(root/'strategy-current/liquidity.json'))

def funding_allocation(c,w,price,count=100,use_wallet=True):
    """Feasible greedy allocation, not an equilibrium or a proven minimum-cost solver.

    Shared wallet inventory is consumed once across every Charter it owns.
    Cash-shortfall first, then ledger-shortfall tie-break; no cash pooling by owner.
    """
    c=c.reset_index(drop=True);pending=c.pending_tokens.to_numpy().copy();inv=w.set_index('address').wallet_tokens.to_dict();used=np.zeros(len(c),int);rows=[]
    for _ in range(count):
        candidates=[]
        for j,x in enumerate(c.itertuples()):
            if used[j]>=3 or x.branches+used[j]>=10:continue
            gap=max(0,price-pending[j]);wallet=min(gap,inv[x.owner]) if use_wallet else 0
            candidates.append((gap-wallet,gap,j,wallet))
        if not candidates:break
        short,gap,j,wallet=min(candidates);x=c.iloc[j]
        ledger=min(price,pending[j]);pending[j]-=ledger;inv[x.owner]-=wallet;used[j]+=1
        rows.append({'charter_id':int(x.charter_id),'owner':x.owner,'price_tokens':price,'ledger_used':ledger,'wallet_used':wallet,'new_tokens_needed':short})
    assert min(inv.values())>=-1e-6 and pending.min()>=-1e-6
    return pd.DataFrame(rows)

def resolution_fee(gross,W,D):
    return .02+.58*np.minimum((W+gross)/max(D+W,10_000_000)/.1,1)**2

def future_yield(days,n,N,new_branches_day=100,issuance=700_000):
    days=np.asarray(days)
    if new_branches_day==0:return issuance*n*days/N
    return issuance*n/new_branches_day*np.log1p(new_branches_day*days/N)

def terminal_value(pool,n,b,N,g,W,D,horizon_days=14,entry_day=100):
    """Full-retirement optimal stopping, price-taking beliefs, own exit slippage.

    Keeping a branch beyond the last grid point has no salvage value here:
    an optimum at the last point is right-censored, not a predicted exit.
    """
    days=np.linspace(0,horizon_days,int(horizon_days*24)+1)
    gross=b+future_yield(days,n,N,entry_day)
    net=gross*(1-resolution_fee(gross,W,D))
    sqrt=pool.sqrt/np.sqrt(np.exp(g*days))
    values=pool.curve.sell_quotes(sqrt,net,lp_fee=pool.lp_fee,sell_tax=pool.sell_tax)
    i=int(np.argmax(values));return float(values[i]),float(days[i]),i==len(days)-1

def run(root=ROOT):
    w,c,t,s,stamp,pool=inputs(root);out=root/'participant-results'
    N=int(s['bank.totalBranches']);D=int(s['bank.totalPendingLive'])/1e18
    W=sum(int(x['value'])/1e18 for x in read(root/'strategy-current/withdrawals.json'))
    anchor=int(s['license.auctionAnchor']);reset=anchor+(int(s['license.currentDay'])+1)*86400
    opening=2*int(s['license.lastSalePrice'])/1e18;floor=2*700000/N
    reset_c=c.copy();reset_c.pending_tokens+=(reset-stamp)/86400*700000/N*reset_c.branches
    funding=[]
    for hours in [0,4,8,12,20,24]:
        # Official prose and observed sales support a four-hour half-life of the GAP.
        price=floor+(opening-floor)*2**(-hours/4) if hours<24 else floor
        at=reset_c.copy();at.pending_tokens+=hours/24*700000/N*at.branches
        for use_wallet in [False,True]:
            allocation=funding_allocation(at,w,price,use_wallet=use_wallet)
            needed=allocation.new_tokens_needed.sum()
            funding.append({'hours_after_reset':hours,'elapsed_days':(reset-stamp)/86400+hours/24,'timestamp_utc':utc(reset+hours*3600),'unit_price_tokens':price,'use_existing_wallet_inventory':use_wallet,'licenses_funded':len(allocation),'entirely_internal_licenses':int((allocation.ledger_used>=price-1e-7).sum()),'wallet_tokens_used':allocation.wallet_used.sum(),'fresh_tokens_needed':needed,'fresh_ETH_if_shortfall_bought_now':pool.quote_buy(needed)})
            if hours==0 and use_wallet:allocation.to_csv(out/'next-auction-feasible-allocation.csv',index=False)
    pd.DataFrame(funding).to_csv(out/'license-funding.csv',index=False)
    # One-day break-even: exact quote at today's curve vs the projected curve state.
    branch_rows=[]
    for x in c.itertuples():
        a=x.pending_tokens;n=x.branches;now=pool.quote_sell(a*(1-resolution_fee(a,W,D)))
        later=a+future_yield(1,n,N)
        for label,extra_W in [('quiet',0),('1m_gross_bank_exits',1e6)]:
            fee=resolution_fee(later,W+extra_W,D)
            lo,hi=.001,10.
            for _ in range(45):
                ratio=(lo+hi)/2
                value=float(pool.curve.sell_quotes(pool.sqrt/np.sqrt(ratio),later*(1-fee),lp_fee=pool.lp_fee,sell_tax=pool.sell_tax))
                if value<now:lo=ratio
                else:hi=ratio
            branch_rows.append({'charter_id':x.charter_id,'owner':x.owner,'branches':n,'pending_tokens':a,'daily_tokens_now':700000*n/N,'net_exit_ETH_now':now,'future_exit_pressure':label,'one_day_break_even_price_ratio':(lo+hi)/2,'one_day_max_price_fall':1-(lo+hi)/2,'future_resolution_fee':fee,'elapsed_days':1,'timestamp_utc':utc(stamp+86400)})
    pd.DataFrame(branch_rows).to_csv(out/'branch-hold-thresholds.csv',index=False)
    # Existing branch vs one added branch: internal ledger first, owner inventory next.
    # Each row is a unilateral opportunity, so funding is not simultaneously allocated.
    decisions=[]
    ws=w.set_index('address')
    for fall in [-.10,0,.05,.15,.30,.50]:
        g=np.log1p(-fall)
        for x in c.itertuples():
            base,day,censored=terminal_value(pool,x.branches,x.pending_tokens,N,g,W,D)
            row={'charter_id':x.charter_id,'owner':x.owner,'assumed_daily_price_fall':fall,'optimal_full_exit_day_within_14d':day,'optimal_full_exit_utc':utc(stamp+day*86400),'exit_horizon_censored':censored,'optimal_net_ETH':base,'current_full_exit_ETH':pool.quote_sell(x.pending_tokens*(1-resolution_fee(x.pending_tokens,W,D)))}
            for tag,price in [('next_open',opening),('floor_price_today_counterfactual',floor)]:
                extra=max(0,price-x.pending_tokens);inventory=min(extra,ws.loc[x.owner,'wallet_tokens']);fresh=extra-inventory
                # Inventory has the opportunity value of its executable sale today.
                cost=pool.quote_sell(inventory)+pool.quote_buy(fresh)
                after,_,_=terminal_value(pool,x.branches+1,max(0,x.pending_tokens-price),N+1,g,W,D)
                row[tag+'_incremental_ETH']=after-base-cost
                row[tag+'_cash_feasible']=pool.quote_buy(fresh)<=ws.loc[x.owner,'native_eth']
            decisions.append(row)
    decision=pd.DataFrame(decisions);decision.to_csv(out/'branch-decisions.csv',index=False)
    # Liquidity buying hurdles at today's exact initialized tick profile.
    hurdles=[]
    for ratio in [1.05,1.10,1.25,1.5,.00019197904484326013/pool.price]:
        target_sqrt=pool.sqrt/np.sqrt(ratio);_,target_eth=pool.curve.inventories(target_sqrt)
        need=(target_eth-pool.available_eth)/((1-pool.buy_tax)*(1-pool.lp_fee))
        hurdles.append({'target_price_ratio':ratio,'target_ETH_per_token':pool.price*ratio,'fresh_buy_ETH_no_sellers':need})
    pd.DataFrame(hurdles).to_csv(out/'recovery-hurdles.csv',index=False)
    # Six-hour paths: continuation stock, replacement sellers, and measured entry.
    recent=t[t.timestamp>=stamp-6*3600];r2=t[t.timestamp>=stamp-2*3600]
    active=w[w.sell_tokens_6h>0];remaining=active.wallet_tokens.sum();sold=active.sell_tokens_6h.sum()
    sell_fraction=sold/(sold+remaining) # survival approximation, disclosed below
    inactive=w[(w.cohort=='inactive_or_unattributed')&(w.wallet_tokens>0)]
    firstsell=t[t.side=='sell'].groupby('address').timestamp.min()
    new_sellers=set(firstsell[firstsell>=stamp-6*3600].index)
    new_seller_tokens=recent[(recent.side=='sell')&recent.address.isin(new_sellers)].tokens.sum()
    replacement_fraction=min(new_seller_tokens/max(inactive.wallet_tokens.sum(),1),1)
    firstbuy=t[t.side=='buy'].groupby('address').timestamp.min()
    fresh6=recent[(recent.side=='buy')&(recent.address.map(firstbuy)>=stamp-6*3600)].pool_eth.sum()/6/.98
    fresh2=r2[(r2.side=='buy')&(r2.address.map(firstbuy)>=stamp-2*3600)].pool_eth.sum()/2/.98
    # Returning wallets are capped by observed native balance AND prior six-hour spending.
    repeat_budget=np.minimum(w.native_eth.fillna(0),w.buy_pool_eth_6h/.98).sum()
    vals=recent[recent.side=='buy'].copy();vals['unit_ETH']=vals.pool_eth/.98/vals.tokens
    buyer_reservation=float(vals.unit_ETH.median()) # point assumption at a revealed-preference lower bound
    paths=[];summaries=[];scenario_specs=[
        ('seller_exhaustion',0.,fresh6),
        ('observed_replacement',replacement_fraction,fresh6),
        ('renewed_entry',replacement_fraction,fresh2),
        ('broader_holder_exit',min(2*replacement_fraction,1),fresh6),
    ]
    for name,wake,new_per_hour in scenario_specs:
        p=copy.deepcopy(pool);start_eth=p.available_eth;start_tokens=p.real_tokens
        seller_inventory=remaining;dormant_inventory=inactive.wallet_tokens.sum();repeat_cash=repeat_budget
        sold_total=bought_total=buy_eth=sell_eth=taxes=lp_fees_eth=lp_fees_token=0.
        planned_remaining=remaining*sell_fraction;planned_dormant=dormant_inventory*wake
        for hour in range(7):
            if hour:
                # A disclosed conditional action: these owners choose exit over continuation.
                q=min(seller_inventory,planned_remaining/6);seller_inventory-=q
                q2=min(dormant_inventory,planned_dormant/6);dormant_inventory-=q2;q+=q2
                net,tax,fill=p.sell(q);assert abs(fill-q)<1e-6
                sold_total+=q;sell_eth+=net;taxes+=tax;lp_fees_token+=q*p.lp_fee
                budget=repeat_budget/6+new_per_hour
                # Rational purchase gate: do not pay above the assumed reservation value.
                # Price already includes impact through bisection; expected resale belief is
                # high enough to justify this value, not inferred uniquely from transactions.
                lo,hi=0.,budget
                for _ in range(35):
                    mid=(lo+hi)/2;test=copy.deepcopy(p);tokens,_=test.buy(mid)
                    if tokens>0 and mid/tokens<=buyer_reservation:lo=mid
                    else:hi=mid
                spend=lo;tokens,tax=p.buy(spend);bought_total+=tokens;buy_eth+=spend;taxes+=tax
                lp_fees_eth+=spend*(1-p.buy_tax)*p.lp_fee
                # Returner spending share is limited by its finite measured budget.
                repeated=min(repeat_cash,spend*repeat_budget/6/budget) if budget else 0
                repeat_cash-=repeated
            eth_error=p.available_eth+sell_eth+taxes+lp_fees_eth-start_eth-buy_eth
            token_error=p.real_tokens+bought_total+lp_fees_token-start_tokens-sold_total
            assert abs(eth_error)<1e-6 and abs(token_error)<.001
            paths.append({'scenario':name,'hour':hour,'elapsed_days':hour/24,'timestamp_utc':utc(stamp+hour*3600),'price_ETH':p.price,'price_ratio':p.price/pool.price,'cumulative_buy_ETH':buy_eth,'cumulative_sell_tokens':sold_total,'remaining_recent_seller_tokens':seller_inventory,'remaining_dormant_tokens':dormant_inventory,'remaining_repeat_cash_budget':repeat_cash,'ETH_error':eth_error,'token_error':token_error})
        summaries.append({'scenario':name,'hours':6,'end_utc':utc(stamp+21600),'end_price_ratio':p.price/pool.price,'recent_seller_tokens_sold':planned_remaining,'replacement_seller_tokens_sold':planned_dormant,'inactive_inventory_sale_fraction':wake,'new_buyer_capacity_ETH_hour':new_per_hour,'repeat_buyer_capacity_ETH_6h':repeat_budget,'actual_buy_ETH':buy_eth,'actual_sell_tokens':sold_total})
    pd.DataFrame(paths).to_csv(out/'conditional-paths.csv',index=False);pd.DataFrame(summaries).to_csv(out/'conditional-scenarios.csv',index=False)
    observed={'snapshot_utc':utc(stamp),'price_ETH':pool.price,'pool_ETH_principal':pool.available_eth,'recent_selling_addresses':len(active),'recent_sellers_zero_balance':int((active.wallet_tokens<1e-9).sum()),'recent_seller_remaining_tokens':remaining,'inactive_inventory_tokens':inactive.wallet_tokens.sum(),'estimated_recent_seller_six_hour_sale_fraction':sell_fraction,'new_seller_tokens_last_6h':new_seller_tokens,'replacement_inventory_fraction':replacement_fraction,'new_buyer_ETH_per_hour_6h':fresh6,'new_buyer_ETH_per_hour_2h':fresh2,'repeat_buyer_budget_ETH':repeat_budget,'buyer_reservation_ETH_per_token_assumed':buyer_reservation,'next_license_reset_utc':utc(reset),'next_license_open_tokens':opening,'current_charters':len(c),'charter_owners':c.owner.nunique(),'branches':N,'bank_pending_tokens':D,'charter_wallet_tokens':w.loc[w.charter_count>0,'wallet_tokens'].sum(),'native_ETH_missing_treated_as_available':False,'calibrated_probabilities':False,'path_scope':'Six-hour conditional cohort flows with real inventory, measured spending ceilings and a reservation-price gate. Scenario ranking/probabilities are not statistically identified. Bank run risk and license value are analyzed separately; no assumed automatic vault buying, new licenses, bank exits, or third-party LP removal are injected into these paths. No out-of-sample validation of paths.'}
    (out/'decision-metadata.json').write_text(json.dumps(observed,indent=2)+'\n')
    print(json.dumps(observed,indent=2));print(pd.DataFrame(summaries).to_string(index=False))
    return observed
if __name__=='__main__':run()
