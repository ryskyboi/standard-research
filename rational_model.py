"""Profit-seeking STANDARD agents under explicit beliefs and budget constraints.

Not a Nash-equilibrium solver. Decisions optimize a finite set of withdrawal
horizons and feasible actions under forecasts; execution uses the known tick map.
No imposed decay of buying. All wallets, claims, fees and ETH sources are tracked.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import math
import numpy as np
import pandas as pd
import model as legacy
from liquidity import ConcentratedPool

ROOT=Path(__file__).resolve().parent

@dataclass
class Config:
    name: str='Adaptive beliefs; Charters closed'
    days: float=14
    dt_hours: float=1
    license_daily_cap: int=100
    per_charter_daily_cap: int=3
    max_branches: int=10
    floor_payback_days: float=2
    license_half_life_hours: float=4
    banker_cash_eth: float=2000
    speculator_cash_eth: float=10000
    prospective_charter_cash_eth: float=1000
    banker_token_fraction: float=.02
    protected_wallet_tokens: float=100000
    protect_representative_branch: bool=True
    speculator_groups: int=32
    mean_reverter_fraction: float=.35
    momentum_cohort_cash_share: float=.85
    momentum_cohort_token_share: float=.25
    start_from_observed_momentum: bool=True
    # These are beliefs, NOT fitted price forecasts.
    prior_growth_day: float=.02
    belief_dispersion_day: float=.04
    momentum_weight: float=.25
    momentum_memory_hours: float=12
    max_momentum_day: float=2
    discount_day: float=.01
    valuation_days: float=30
    speculator_holding_days: float=2
    # Trading capacities reflect participation/execution constraints, not orders.
    speculator_cash_turnover_day: float=.77
    speculator_token_turnover_day: float=.20
    fresh_capital_eth_day: float=0
    prefund_days: float=3
    allow_internal: bool=True
    allow_external: bool=True
    allow_retirement: bool=True
    charter_open_hour: float | None=None
    charter_daily_cap: int=10
    charter_floor_eth: float=.15
    charter_first_open_eth: float=.45
    charter_new_wallet_eth: float=1
    execute_buybacks: bool=False
    execute_pol: bool=False
    protocol_buy_tax_exempt: bool=False  # exemption is not established by docs
    buy_tax_override: float | None=None
    sell_tax_override: float | None=None
    minimum_edge_eth: float=1e-6

    def __post_init__(self):
        if not (0<self.dt_hours<=24 and self.days>0 and self.valuation_days>0):raise ValueError('Invalid time grid')
        if not (0<=self.license_daily_cap<=2000 and 0<=self.charter_daily_cap<=100):raise ValueError('Policy cap outside documented bounds')
        if not (0<=self.banker_token_fraction<=1 and 1<=self.max_branches<=10 and 0<=self.per_charter_daily_cap<=3):raise ValueError('Invalid branch/inventory limit')
        for x in ['banker_cash_eth','speculator_cash_eth','prospective_charter_cash_eth','belief_dispersion_day','discount_day','fresh_capital_eth_day','prefund_days','speculator_cash_turnover_day','speculator_token_turnover_day']:
            if getattr(self,x)<0:raise ValueError(x+' must be nonnegative')
        if self.momentum_memory_hours<=0 or self.license_half_life_hours<=0 or self.speculator_groups<1:raise ValueError('Invalid behavioral setting')
        for f in [self.mean_reverter_fraction,self.momentum_cohort_cash_share,self.momentum_cohort_token_share]:
            if not 0<=f<=1:raise ValueError('Invalid cohort fraction')
        for x in [self.buy_tax_override,self.sell_tax_override]:
            if x is not None and not 0<=x<=.10:raise ValueError('Manual trading taxes must be within 0–10%')


def trading_taxes(timestamp,schedule,buy_override=None,sell_override=None):
    """Documented exponential launch excess, floors at one hour; no launch replay."""
    elapsed=max(0,timestamp-int(schedule['taxDecayStart']))
    active=not schedule['taxOverridden'] and elapsed<int(schedule['taxDecayDuration'])
    result=[]
    for side,override in [('Buy',buy_override),('Sell',sell_override)]:
        if override is not None:rate=override
        elif active:
            floor=int(schedule[f'decayFloor{side}Bps'])/10000
            start=int(schedule[f'decayStart{side}Bps'])/10000
            rate=floor+(start-floor)*2**(-elapsed/int(schedule['taxHalfLife']))
        else:rate=int(schedule[f'{side.lower()}TaxBps'])/10000
        result.append(rate)
    return tuple(result)


def resolution_fee(gross,pending,withdrawn):
    return .02+.58*np.minimum((withdrawn+gross)/np.maximum(pending+withdrawn,10_000_000)/.1,1)**2


def load_population():
    records={}
    for row in legacy.read('charters.json'):
        ident,key=row['label'].split('.');records.setdefault(int(ident),{})[key]=row.get('value')
    owners=[(i,r) for i,r in sorted(records.items()) if r.get('ownerOf')]
    return (np.array([i for i,r in owners]),np.array([int(r['branchCountOf']) for i,r in owners]),
            np.array([int(r['pendingOf'])/1e18 for i,r in owners]))


class Economy:
    def __init__(self,config,seed=20260915,forecast=None):
        self.c=config;self.rng=np.random.default_rng(seed);self.s=legacy.snapshot()
        self.home=legacy.read('home.json')['snapshot'];self.forecast=forecast
        self.pool=ConcentratedPool(self.s['liquidity_profile'],self.s['lp_fee'],self.s['buy_tax'],self.s['sell_tax'])
        self.pool.buy_tax,self.pool.sell_tax=trading_taxes(self.s['timestamp'],self.home['tax'],config.buy_tax_override,config.sell_tax_override)
        self.ids,self.n,self.balance=load_population();self.initial_n=self.n.copy()
        count=len(self.n);self.initial_count=count
        self.cash=np.full(count,config.banker_cash_eth/count)
        self.inventory=np.full(count,self.s['float_tokens']*config.banker_token_fraction/count)
        self.bias=self.rng.normal(config.prior_growth_day,config.belief_dispersion_day,count)
        self.used=np.minimum(self.n-1,config.per_charter_daily_cap)
        groups=config.speculator_groups
        self.spec_cash=np.full(groups,config.speculator_cash_eth/groups)
        self.spec_tokens=np.full(groups,self.s['float_tokens']*(1-config.banker_token_fraction)/groups)
        self.spec_bias=self.rng.normal(config.prior_growth_day,config.belief_dispersion_day,groups)
        self.protected_wallet=config.protected_wallet_tokens
        if not 0<=self.protected_wallet<=self.spec_tokens.sum():raise ValueError('Protected wallet exceeds modeled float')
        self.spec_tokens-=self.protected_wallet/groups
        self.protected=np.zeros(count,dtype=bool)
        singles=np.flatnonzero(self.n==1)
        if config.protect_representative_branch and len(singles):
            self.protected[singles[np.argmin(abs(self.balance[singles]-self.s['own_pending']))]]=True
        reverters=int(round(groups*config.mean_reverter_fraction))
        self.spec_trend_weights=np.full(groups,config.momentum_weight)
        if 0<reverters<groups:
            followers=groups-reverters
            self.spec_trend_weights[followers:]=-config.momentum_weight
            self.spec_cash[:followers]=config.speculator_cash_eth*config.momentum_cohort_cash_share/followers
            self.spec_cash[followers:]=config.speculator_cash_eth*(1-config.momentum_cohort_cash_share)/reverters
            tokens=self.spec_tokens.sum()
            self.spec_tokens[:followers]=tokens*config.momentum_cohort_token_share/followers
            self.spec_tokens[followers:]=tokens*(1-config.momentum_cohort_token_share)/reverters
        elif reverters==groups:self.spec_trend_weights[:]=-config.momentum_weight
        self.initial_spec_cash=self.spec_cash.copy()
        self.prospective=config.prospective_charter_cash_eth
        self.license_day=int((self.s['timestamp']-self.s['auction_anchor'])//86400)
        la=self.home['licenseAuction']
        self.license_sold=int(la['soldToday']);self.day_floor=int(la['dayFloorPrice'])/1e18
        self.day_open=int(la['dayStartPrice'])/1e18;self.last_license=int(la['lastSalePrice'])/1e18
        self.last_license_sale_day=int(la['lastSaleDay'])
        self.charter_day=-1;self.charter_sold=0;self.charter_open=config.charter_first_open_eth
        self.last_charter=config.charter_floor_eth;self.last_charter_sale_day=-1
        self.hours=0.;self.multiplier=self.s['multiplier'];self.epoch_flow=self.s['epoch_flow']
        self.previous_flow=int(self.home['bank']['previousEpochFlow'])/1e18
        self.positive_streak=int(self.home['bank']['positiveSignalStreak'])
        self.epoch_end=(self.s['epoch_end']-self.s['timestamp'])/3600
        self.issued=int(self.home['bank']['cumulativeIssued'])/1e18
        self.issue_budget=int(self.home['bank']['ISSUANCE_BUDGET'])/1e18
        self.recycle_buffer=int(self.home['bank']['recycleBuffer'])/1e18
        self.recycled_day=int(self.home['bank']['recycleRate'])/1e18*86400
        day=int((self.s['timestamp']-self.s['genesis'])//86400)
        self.withdrawals={day:self.s['withdrawn']}
        self.vault=self.s['contraction_eth'];self.expansion=int(self.home['balances']['expansionVault'])/1e18
        self.fee_buffer=int(self.home['balances']['feeSplitter'])/1e18
        self.pol_eth=0.;self.pol_tokens=0.;self.team_eth=0.;self.lp_eth=0.;self.lp_tokens=0.
        self.minted=0.;self.physical_burned=0.;self.ledger_burned=0.;self.fresh_added=0.
        self.momentum=0.;self.last_price=self.pool.price
        if config.start_from_observed_momentum:
            logs=sorted(legacy.read('recent-swaps.json')['logs'],key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16)))
            headers=legacy.read('swap-time-headers.json');first_price=(2**96/int(logs[0]['decoded']['sqrtPriceX96']))**2
            elapsed=(int(headers[-1]['timestamp'],16)-int(headers[0]['timestamp'],16))/86400
            self.momentum=math.log(self.pool.price/first_price)/elapsed
        self.license_rate=100.;self.retire_rate=0.;self.gross_withdraw_rate=0.
        self.events=[];self.rows=[];self.daily_purchase_counts={};self.totals={}
        self.initial_eth=self.total_eth();self.initial_tokens=self.total_tokens()
        self.initial_pending=self.pending;self.credited_base=0.;self.credited_recycling=0.;self.gross_paid=0.;self.internal_spent=0.
        self.protocol_positions=[p for p in legacy.read('liquidity-positions.json')['positions'] if p['assumedPermanent']]
        self.initial_balances=self.balance.copy();self.initial_cash=self.cash.copy();self.initial_inventory=self.inventory.copy()
        self.owner_realized=np.zeros(count);self.owner_spent=np.zeros(count)
        self._reset_flows()

    def _reset_flows(self):
        self.flow={k:0. for k in ['pool_buy_eth','pool_sell_eth_gross','pol_added_eth','spec_buy_eth','spec_sell_eth','license_buy_eth','prefund_buy_eth','banker_inventory_sell_eth',
            'withdraw_sell_eth','buyback_eth','pol_buy_eth','charter_eth','new_capital_eth','licenses_internal','licenses_external',
            'license_tokens_internal','license_tokens_inventory','license_tokens_fresh','prefund_tokens','branches_retired',
            'charters_created','gross_withdrawn','resolution_fee_tokens','hook_tax_eth','lp_fee_eth','lp_fee_tokens','licenses_bought']}

    @property
    def total_branches(self):return int(self.n.sum())
    @property
    def pending(self):return float(self.balance.sum())
    @property
    def withdrawn(self):return sum(self.withdrawals.values())
    @property
    def issue_day(self):return self.s['base_per_day']*self.multiplier if self.issued<self.issue_budget else 0.
    @property
    def total_issue_day(self):return self.issue_day+self.recycled_day

    def total_eth(self):
        return self.pool.available_eth+self.cash.sum()+self.spec_cash.sum()+self.prospective+self.vault+self.expansion+self.fee_buffer+self.pol_eth+self.team_eth+self.lp_eth
    def total_tokens(self):
        return self.pool.real_tokens+self.inventory.sum()+self.spec_tokens.sum()+self.lp_tokens+self.pol_tokens+self.protected_wallet

    def buy(self,eth,category,protocol=False):
        if eth<=1e-12:return 0.
        exempt=protocol and self.c.protocol_buy_tax_exempt
        out,tax=self.pool.buy(float(eth),exempt=exempt)
        lp=(eth-tax)*self.pool.lp_fee
        self.lp_eth+=lp;self.fee_buffer+=tax;self.epoch_flow+=eth-tax
        self.flow[category]+=eth;self.flow['pool_buy_eth']+=eth-tax-lp;self.flow['hook_tax_eth']+=tax;self.flow['lp_fee_eth']+=lp
        return out

    def sell(self,tokens,category):
        if tokens<=1e-12:return 0.,0.
        cash,tax,filled=self.pool.sell(float(tokens))
        self.lp_tokens+=filled*self.pool.lp_fee;self.fee_buffer+=tax;self.epoch_flow-=cash+tax
        self.flow[category]+=cash;self.flow['pool_sell_eth_gross']+=cash+tax;self.flow['hook_tax_eth']+=tax;self.flow['lp_fee_tokens']+=filled*self.pool.lp_fee
        return cash,filled

    def available_growth_budget(self,t):
        # A price forecast cannot require more buying ETH than modeled available
        # capital, even before buyers' willingness to spend is considered.
        budget=float(self.cash[~self.protected].sum()+self.spec_cash.sum())+self.c.fresh_capital_eth_day*np.asarray(t)
        if self.c.execute_buybacks:budget=budget+self.vault
        return budget

    def expected_prices(self,bias,t,trend_weight=None):
        t=np.asarray(t,dtype=float);bias=np.atleast_1d(bias)
        if self.forecast is not None:
            price=np.interp(self.hours+t*24,self.forecast['hours'],self.forecast['price'])
            raw=np.broadcast_to(price,(len(bias),len(t))).copy()
        else:
            growth=bias+(self.c.momentum_weight if trend_weight is None else trend_weight)*np.clip(self.momentum,-self.c.max_momentum_day,self.c.max_momentum_day)
            raw=self.pool.price*np.exp(np.clip(growth[:,None]*t[None,:],-30,30))
        _,y=self.pool.curve.inventories(self.pool.sqrt)
        reachable=self.pool.curve.sqrt_from_eth(y+self.available_growth_budget(t)*(1-self.pool.buy_tax)*(1-self.pool.lp_fee)/self.pool.scale)
        cap=1/reachable**2
        raw=np.minimum(raw,cap[None,:])
        raw[:,t==0]=self.pool.price
        return raw

    def value_grid(self,n,balance,bias,total_branches=None,pending=None,withdrawn=None):
        n=np.atleast_1d(n).astype(float);balance=np.atleast_1d(balance).astype(float)
        # Common horizons, no assumed sale at the end of the simulation.
        t=np.unique(np.r_[0.,.25,.5,1.,2.,3.,5.,7.,10.,14.,21.,self.c.valuation_days])
        t=t[t<=self.c.valuation_days]
        total=self.total_branches if total_branches is None else total_branches
        pending=self.pending if pending is None else pending
        withdrawn=self.withdrawn if withdrawn is None else withdrawn
        if self.forecast is not None:
            future_total=np.interp(self.hours+t*24,self.forecast['hours'],self.forecast['branches'])
            others=np.maximum(0,future_total[None,:]-n[:,None])
        else:
            hazard=self.retire_rate/max(total,1)
            survivors=np.exp(-hazard*t)
            additions=self.license_rate*((1-survivors)/hazard if hazard>1e-9 else t)
            if self.c.charter_open_hour is not None:
                additions+=self.c.charter_daily_cap*np.maximum(0,t-max(0,self.c.charter_open_hour-self.hours)/24)
            capacity=self.c.max_branches*(int((self.n>0).sum())+1+self.c.charter_daily_cap*t*(self.c.charter_open_hour is not None))
            others=np.minimum(np.maximum(0,total-n)[:,None]*survivors[None,:]+additions[None,:],np.maximum(0,capacity[None,:]-n[:,None]))
        rates=self.total_issue_day*n[:,None]/np.maximum(1,n[:,None]+others)
        earned=np.cumsum(np.c_[np.zeros(len(n)),(rates[:,1:]+rates[:,:-1])*.5*np.diff(t)],axis=1)
        # Remaining base-issuance budget is a hard bound on any projected share.
        earned=np.minimum(earned,max(0,self.issue_budget-self.issued)+self.recycled_day*t)
        gross=balance[:,None]+earned
        future_pending=np.maximum(0,np.atleast_1d(pending)[:,None]+self.total_issue_day*t-self.gross_withdraw_rate*t)
        current_day=int((self.s['timestamp']+self.hours*3600-self.s['genesis'])//86400)
        future_day=np.floor((self.s['timestamp']+self.hours*3600-self.s['genesis'])/86400+t)
        known_w=sum((w*(d>future_day-7) for d,w in self.withdrawals.items()),np.zeros_like(t))
        proposed_extra=np.atleast_1d(withdrawn)[:,None]-self.withdrawn
        future_withdrawn=known_w[None,:]+proposed_extra*(current_day>future_day-7)[None,:]+self.gross_withdraw_rate*np.minimum(t,7)
        fees=resolution_fee(gross,np.maximum(gross,future_pending),future_withdrawn)
        prices=self.expected_prices(bias,t)
        value=self.pool.curve.sell_quotes(1/np.sqrt(prices),gross*(1-fees),self.pool.scale,self.pool.lp_fee,self.pool.sell_tax)
        value*=np.exp(-self.c.discount_day*t)[None,:]
        value[n<=0]=0
        return value,t

    def values(self,n,balance,bias,**kw):
        grid,t=self.value_grid(n,balance,bias,**kw)
        at=np.argmax(grid,axis=1)
        return grid[np.arange(len(at)),at],t[at]

    def quote_buys(self,tokens):
        tokens=np.maximum(0,np.asarray(tokens))
        x,y=self.pool.curve.inventories(self.pool.sqrt)
        end=self.pool.curve.sqrt_from_tokens(x-tokens/self.pool.scale)
        _,new_y=self.pool.curve.inventories(end)
        quoted=np.maximum(0,new_y-y)*self.pool.scale/(1-self.pool.buy_tax)/(1-self.pool.lp_fee)
        return np.where(tokens>=x*self.pool.scale,np.inf,quoted)

    def reset_auction(self):
        day=int((self.s['timestamp']+self.hours*3600-self.s['auction_anchor'])//86400)
        if day!=self.license_day:
            self.license_day=day;self.license_sold=0;self.used[:]=0
            self.day_floor=self.c.floor_payback_days*self.issue_day/max(self.total_branches,1)
            self.day_open=max(self.day_floor,2*self.last_license) if self.last_license_sale_day==day-1 else self.day_floor
        elapsed=((self.s['timestamp']+self.hours*3600-self.s['auction_anchor'])%86400)/3600
        return self.day_floor+(self.day_open-self.day_floor)*2**(-elapsed/self.c.license_half_life_hours)

    def license_surpluses(self,cost,indices=None,ignore_daily=False):
        idx=np.arange(len(self.n)) if indices is None else np.atleast_1d(indices)
        n,balance,bias=self.n[idx],self.balance[idx],self.bias[idx]
        before,_=self.values(n,balance,bias)
        after,_=self.values(n+1,balance,bias,total_branches=self.total_branches+1)
        inv=np.minimum(self.inventory[idx],cost);missing=cost-inv
        cash_cost=self.quote_buys(missing)
        future=self.expected_prices(bias,np.array([0.,self.c.speculator_holding_days]))
        opportunity=(future*np.exp(-self.c.discount_day*np.array([0.,self.c.speculator_holding_days]))).max(axis=1)
        inventory_cost=inv*opportunity*(1-self.pool.lp_fee)*(1-self.pool.sell_tax)
        external=after-before-cash_cost-inventory_cost
        external[(cash_cost>self.cash[idx]+1e-10)|(~np.isfinite(cash_cost))]=-np.inf
        if not self.c.allow_external:external[:]=-np.inf
        inside,_=self.values(n+1,np.maximum(0,balance-cost),bias,total_branches=self.total_branches+1,pending=max(0,self.pending-cost))
        internal=inside-before;internal[balance<cost]=-np.inf
        if not self.c.allow_internal:internal[:]=-np.inf
        eligible=(n>0)&(n<self.c.max_branches)&(~self.protected[idx])
        if not ignore_daily:eligible &= self.used[idx]<self.c.per_charter_daily_cap
        external[~eligible]=-np.inf;internal[~eligible]=-np.inf
        return external,internal,cash_cost

    def buy_licenses(self,cost):
        remaining=self.c.license_daily_cap-self.license_sold
        if remaining<=0 or cost<=0:return
        # Three passes permit up to three per Charter. Eligibility is recomputed
        # after each pass; execution rechecks the actual market cost and budget.
        for _ in range(self.c.per_charter_daily_cap):
            ext,inside,quoted=self.license_surpluses(cost)
            score=np.maximum(ext,inside)
            eligible=np.flatnonzero(score>self.c.minimum_edge_eth)
            if not len(eligible):break
            order=eligible[np.argsort(-(score[eligible]+self.rng.random(len(eligible))*1e-12))]
            for i in order[:remaining]:
                ex,ins,qu=self.license_surpluses(cost,[i])
                if max(ex[0],ins[0])<=self.c.minimum_edge_eth:continue
                use_internal=ins[0]>=ex[0]
                if use_internal:
                    if self.balance[i]+1e-9<cost:continue
                    self.balance[i]-=cost;self.ledger_burned+=cost;self.internal_spent+=cost
                    self.flow['licenses_internal']+=1;self.flow['license_tokens_internal']+=cost
                    eth=0.;inventory_used=0.
                else:
                    inventory_used=min(self.inventory[i],cost);missing=cost-inventory_used
                    eth=self.pool.quote_buy(missing) if missing>0 else 0.
                    # Price impact from earlier buyers may erase the expected edge.
                    if eth>self.cash[i]+1e-9 or ex[0]-(eth-qu[0])<=self.c.minimum_edge_eth:continue
                    self.inventory[i]-=inventory_used;self.cash[i]-=eth
                    received=self.buy(eth,'license_buy_eth')
                    if abs(received-missing)>1e-5:raise AssertionError('License market purchase mismatch')
                    self.physical_burned+=cost;self.owner_spent[i]+=eth
                    self.flow['licenses_external']+=1;self.flow['license_tokens_inventory']+=inventory_used;self.flow['license_tokens_fresh']+=missing
                self.n[i]+=1;self.used[i]+=1;self.license_sold+=1;remaining-=1
                self.last_license=cost;self.last_license_sale_day=self.license_day
                key=(self.license_day,int(self.ids[i]));self.daily_purchase_counts[key]=self.daily_purchase_counts.get(key,0)+1
                self.flow['licenses_bought']+=1
                self.events.append(dict(hour=self.hours,event='license',charter=int(self.ids[i]),count=1,price_tokens=cost,
                    funding='ledger' if use_internal else 'wallet/cash',eth=eth,inventory_tokens=inventory_used))
                if remaining==0:return

    def prebuy_inventory(self):
        if self.c.prefund_days<=0 or not self.c.allow_external:return
        floor=self.c.floor_payback_days*self.issue_day/max(self.total_branches,1)
        if floor<=0:return
        expected_license_cost=max(floor,self.last_license)
        ext,_,_=self.license_surpluses(expected_license_cost,ignore_daily=True)
        eligible=np.flatnonzero((ext>self.c.minimum_edge_eth)&(self.n<self.c.max_branches)&(self.n>0))
        if not len(eligible):return
        slots=np.minimum(self.c.max_branches-self.n[eligible],min(self.c.per_charter_daily_cap*self.c.prefund_days,
            self.c.license_daily_cap*self.c.prefund_days/len(eligible)))
        desired=np.maximum(0,slots*expected_license_cost-self.inventory[eligible])
        future=self.expected_prices(self.bias[eligible],np.array([self.c.prefund_days]))[:,0]*math.exp(-self.c.discount_day*self.c.prefund_days)
        for j,i in enumerate(eligible):
            if desired[j]<=0 or future[j]<=self.pool.price:continue
            # Current cash price vs expected later cash price for consumed tokens.
            cost=self.pool.quote_buy(desired[j])
            future_cost=desired[j]*future[j]/(1-self.pool.buy_tax)/(1-self.pool.lp_fee)
            if np.isfinite(cost) and cost<=self.cash[i] and future_cost>cost+self.c.minimum_edge_eth:
                self.cash[i]-=cost;tokens=self.buy(cost,'prefund_buy_eth');self.inventory[i]+=tokens
                self.owner_spent[i]+=cost;self.flow['prefund_tokens']+=tokens

    def trade_speculators(self):
        dt=self.c.dt_hours/24;t=self.c.speculator_holding_days
        future=self.expected_prices(self.spec_bias,np.array([t]),self.spec_trend_weights)[:,0]*math.exp(-self.c.discount_day*t)
        # Arrival capital is real additional ETH, explicitly accounted for.
        cap=self.c.fresh_capital_eth_day*dt
        self.spec_cash+=cap/len(self.spec_cash);self.fresh_added+=cap;self.flow['new_capital_eth']+=cap
        for i in self.rng.permutation(len(self.spec_cash)):
            # Optimal marginal reservation price, subject to wallet and participation limits.
            buy_limit=future[i]*(1-self.pool.sell_tax)*(1-self.pool.lp_fee)*(1-self.pool.buy_tax)*(1-self.pool.lp_fee)
            if buy_limit>self.pool.price:
                _,y=self.pool.curve.inventories(self.pool.sqrt)
                _,target_y=self.pool.curve.inventories(1/math.sqrt(buy_limit))
                target_cash=max(0,float(target_y-y))*self.pool.scale/(1-self.pool.buy_tax)/(1-self.pool.lp_fee)
                budget=min(self.spec_cash[i],max(self.initial_spec_cash[i],self.spec_cash[i])*self.c.speculator_cash_turnover_day*dt)
                spend=min(target_cash,budget)
                self.spec_cash[i]-=spend;self.spec_tokens[i]+=self.buy(spend,'spec_buy_eth')
            elif future[i]<self.pool.price:
                x,_=self.pool.curve.inventories(self.pool.sqrt)
                target_x,_=self.pool.curve.inventories(1/math.sqrt(max(future[i],1e-30)))
                desired=max(0,float(target_x-x))*self.pool.scale/(1-self.pool.lp_fee)
                quantity=min(desired,self.spec_tokens[i]*(1-math.exp(-self.c.speculator_token_turnover_day*dt)))
                cash,filled=self.sell(quantity,'spec_sell_eth');self.spec_tokens[i]-=filled;self.spec_cash[i]+=cash

    def retire_branches(self):
        if not self.c.allow_retirement:return
        alive=np.flatnonzero((self.n>0)&(self.balance>0)&(~self.protected))
        if not len(alive):return
        best,when=self.values(self.n[alive],self.balance[alive],self.bias[alive])
        counts=np.where(when==0,self.n[alive],0)
        advantages=np.where(when==0,1e-8,0.)
        # Partial retirement is a separate feasible action; the retained branch
        # balance and share remain in the continuation value.
        for j in range(1,int(self.n[alive].max())):
            at=np.flatnonzero(self.n[alive]>j)
            if not len(at):continue
            idx=alive[at];gross=self.balance[idx]*j/self.n[idx]
            fees=resolution_fee(gross,self.pending,self.withdrawn)
            cash=self.pool.curve.sell_quotes(self.pool.sqrt,gross*(1-fees),self.pool.scale,self.pool.lp_fee,self.pool.sell_tax)
            rest,_=self.values(self.n[idx]-j,self.balance[idx]-gross,self.bias[idx],total_branches=max(1,self.total_branches-j),pending=self.pending-gross,withdrawn=self.withdrawn+gross)
            advantage=cash+rest-best[at]
            choose=advantage>np.maximum(advantages[at],self.c.minimum_edge_eth)
            counts[at[choose]]=j;advantages[at[choose]]=advantage[choose]
        # Random order is a coordination assumption, not private transaction priority.
        for at in self.rng.permutation(np.flatnonzero(counts>0)):
            i=alive[at];count=int(counts[at])
            # Re-evaluate full retirement after earlier exits changed taxes and price.
            if count==self.n[i]:
                _,now=self.values([self.n[i]],[self.balance[i]],[self.bias[i]])
                if now[0]>0:continue
            else:
                baseline,_=self.values([self.n[i]],[self.balance[i]],[self.bias[i]])
                gross=self.balance[i]*count/self.n[i]
                f=float(resolution_fee(gross,self.pending,self.withdrawn))
                original_sqrt=self.pool.sqrt
                try:
                    immediate,_,_=self.pool.sell(gross*(1-f))
                    remainder,_=self.values([self.n[i]-count],[self.balance[i]-gross],[self.bias[i]],
                        total_branches=self.total_branches-count,pending=self.pending-gross,withdrawn=self.withdrawn+gross)
                finally:self.pool.sqrt=original_sqrt
                if immediate+remainder[0]<=baseline[0]+self.c.minimum_edge_eth:continue
            self.retire(int(i),count)

    def trade_banker_inventory(self):
        future=self.expected_prices(self.bias,np.array([self.c.speculator_holding_days]))[:,0]*math.exp(-self.c.discount_day*self.c.speculator_holding_days)
        for i in self.rng.permutation(np.flatnonzero((self.inventory>1e-8)&(~self.protected))):
            if future[i]<self.pool.price:
                cash,filled=self.sell(self.inventory[i],'banker_inventory_sell_eth')
                self.inventory[i]-=filled;self.cash[i]+=cash;self.owner_realized[i]+=cash

    def retire(self,i,count):
        if not 0<count<=self.n[i]:raise ValueError('Invalid retirement')
        gross=self.balance[i]*count/self.n[i];f=float(resolution_fee(gross,self.pending,self.withdrawn))
        self.balance[i]-=gross;self.n[i]-=count;self.gross_paid+=gross
        if self.n[i]==0:self.balance[i]=0.
        day=int((self.s['timestamp']+self.hours*3600-self.s['genesis'])//86400)
        self.withdrawals[day]=self.withdrawals.get(day,0)+gross
        self.recycle_buffer+=gross*f*.5;self.ledger_burned+=gross*f*.5
        tokens=gross*(1-f);self.minted+=tokens
        cash,filled=self.sell(tokens,'withdraw_sell_eth');self.inventory[i]+=tokens-filled
        self.cash[i]+=cash;self.owner_realized[i]+=cash
        self.flow['branches_retired']+=count;self.flow['gross_withdrawn']+=gross;self.flow['resolution_fee_tokens']+=gross*f
        self.events.append(dict(hour=self.hours,event='retire',charter=int(self.ids[i]),count=count,gross_tokens=gross,resolution_fee=f,net_eth=cash))

    def open_charters(self):
        c=self.c
        if c.charter_open_hour is None or self.hours<c.charter_open_hour or c.charter_daily_cap==0:return
        day=int((self.hours-c.charter_open_hour)//24)
        if day!=self.charter_day:
            self.charter_sold=0;self.charter_day=day
            self.charter_open=c.charter_first_open_eth if day==0 else max(c.charter_floor_eth,3*self.last_charter) if self.last_charter_sale_day==day-1 else c.charter_floor_eth
        elapsed=(self.hours-c.charter_open_hour)%24
        cost=c.charter_floor_eth+(self.charter_open-c.charter_floor_eth)*2**(-elapsed/4)
        for _ in range(c.charter_daily_cap-self.charter_sold):
            value,_=self.values([1],[0],[c.prior_growth_day],total_branches=self.total_branches+1)
            if value[0]<=cost+c.minimum_edge_eth or self.prospective<cost+c.charter_new_wallet_eth:break
            self.prospective-=cost+c.charter_new_wallet_eth;self.fee_buffer+=cost
            ident=int(self.ids.max())+1
            for key,extra in [('ids',ident),('n',1),('balance',0.),('cash',c.charter_new_wallet_eth),('inventory',0.),('bias',c.prior_growth_day),('used',0),('owner_realized',0.),('owner_spent',cost),('protected',False)]:
                setattr(self,key,np.append(getattr(self,key),extra))
            self.charter_sold+=1;self.last_charter=cost;self.last_charter_sale_day=day
            self.flow['charter_eth']+=cost;self.flow['charters_created']+=1
            self.events.append(dict(hour=self.hours,event='charter',charter=ident,count=1,eth=cost))

    def settle_epoch(self):
        if self.hours<self.epoch_end:return
        signal=self.epoch_flow+self.previous_flow
        if signal<0:self.multiplier=max(.2,self.multiplier-.15);self.positive_streak=0
        elif signal>0:
            self.positive_streak+=1
            if self.positive_streak>=2:self.multiplier=min(1.25,self.multiplier+.10)
        else:self.positive_streak=0
        if self.epoch_flow>0:self.expansion+=.70*self.fee_buffer
        else:self.vault+=.70*self.fee_buffer
        self.pol_eth+=.15*self.fee_buffer;self.team_eth+=.15*self.fee_buffer;self.fee_buffer=0.
        self.previous_flow=self.epoch_flow;self.epoch_flow=0.
        self.recycled_day=self.recycle_buffer/self.s['epoch_days'];self.recycle_buffer=0.
        self.epoch_end+=self.s['epoch_days']*24

    def protocol_depth(self):
        tick=math.log(self.pool.sqrt**2)/math.log(1.0001)
        original=sum(int(p['liquidity'])/1e18 for p in self.protocol_positions if p['tickLower']<=tick<p['tickUpper'])
        all_original=self.pool.curve.L[self.pool.curve.index(self.pool.sqrt)]
        return (original+(self.pool.scale-1)*all_original)/self.pool.sqrt

    def protocol_actions(self):
        # Execution is a scenario switch: authorization, keeper availability and
        # TWAP checks can prevent real execution. The active protocol virtual-depth
        # formula matches the pinned vault getter; execution uses actual ranges.
        if self.c.execute_buybacks and self.epoch_flow<0 and self.vault>0:
            spend=min(self.vault*(1-.9**self.c.dt_hours),.002*self.protocol_depth()*self.c.dt_hours)
            self.vault-=spend;out=self.buy(spend,'buyback_eth',protocol=True);self.physical_burned+=out
        if self.c.execute_pol and self.pol_eth>1e-8:
            amount=self.pol_eth*.5;self.pol_eth-=amount
            tokens=self.buy(amount,'pol_buy_eth',protocol=True);self.pol_tokens+=tokens
            before_eth=self.pool.available_eth;before_tokens=self.pool.real_tokens
            self.pool.add_proportional(self.pol_eth,self.pol_tokens)
            self.flow['pol_added_eth']+=self.pool.available_eth-before_eth
            self.pol_eth-=self.pool.available_eth-before_eth;self.pol_tokens-=self.pool.real_tokens-before_tokens
            self.pol_eth=max(0,self.pol_eth);self.pol_tokens=max(0,self.pol_tokens)

    def check(self):
        assert np.all((self.n>=0)&(self.n<=self.c.max_branches))
        assert np.all(self.used<=self.c.per_charter_daily_cap)
        assert min(self.cash.min(),self.inventory.min(),self.balance.min(),self.spec_cash.min(),self.spec_tokens.min(),self.vault,self.pol_eth,self.pol_tokens)>=-1e-5
        assert np.all(self.balance[self.n==0]==0)
        assert abs(self.total_eth()-self.initial_eth-self.fresh_added)<1e-5
        assert abs(self.total_tokens()-self.initial_tokens-self.minted+self.physical_burned)<.02
        assert abs(self.pending-self.initial_pending-self.credited_base-self.credited_recycling+self.gross_paid+self.internal_spent)<1e-5

    def record(self):
        for key,value in self.flow.items():self.totals[key]=self.totals.get(key,0)+value
        rec=dict(hour=self.hours,price=self.pool.price,eth_principal=self.pool.available_eth,token_principal=self.pool.real_tokens,
            sqrt=self.pool.sqrt,scale=self.pool.scale,branches=self.total_branches,charters=int((self.n>0).sum()),
            remaining_slots=int(np.where(self.n>0,self.c.max_branches-self.n,0).sum()),pending=self.pending,
            withdrawn_7d=self.withdrawn,protected_branch_balance=float(self.balance[self.protected].sum()),protected_branch_count=int(self.n[self.protected].sum()),resolution_fee_small=float(resolution_fee(1000,self.pending,self.withdrawn)),
            buy_tax=self.pool.buy_tax,sell_tax=self.pool.sell_tax,multiplier=self.multiplier,
            banker_cash=float(self.cash.sum()),speculator_cash=float(self.spec_cash.sum()),banker_inventory=float(self.inventory.sum()),
            speculator_inventory=float(self.spec_tokens.sum()),prospective_cash=self.prospective,
            contraction_eth=self.vault,expansion_eth=self.expansion,pol_eth=self.pol_eth,team_eth=self.team_eth,
            unallocated_hook_fees=self.fee_buffer,uncollected_lp_eth=self.lp_eth,uncollected_lp_tokens=self.lp_tokens,
            issued=self.issued,physical_burned=self.physical_burned,ledger_burned=self.ledger_burned,
            recycle_buffer=self.recycle_buffer,momentum_day=self.momentum,
            forecast_price_7d=float(self.expected_prices([self.c.prior_growth_day],np.array([7.]))[0,0]),
            eth_accounting_error=float(self.total_eth()-self.initial_eth-self.fresh_added),
            token_accounting_error=float(self.total_tokens()-self.initial_tokens-self.minted+self.physical_burned),
            ledger_accounting_error=float(self.pending-self.initial_pending-self.credited_base-self.credited_recycling+self.gross_paid+self.internal_spent),**self.flow)
        self.rows.append(rec)

    def step(self):
        self._reset_flows();dt=self.c.dt_hours/24
        base=min(self.issue_day*dt,max(0,self.issue_budget-self.issued)) if self.total_branches>0 else 0.
        self.issued+=base
        if self.total_branches>0:
            self.balance+=(base+self.recycled_day*dt)*self.n/self.total_branches
            self.credited_base+=base;self.credited_recycling+=self.recycled_day*dt
        self.hours+=self.c.dt_hours
        timestamp=self.s['timestamp']+self.hours*3600
        day=int((timestamp-self.s['genesis'])//86400)
        self.withdrawals={d:x for d,x in self.withdrawals.items() if d>day-7}
        self.pool.buy_tax,self.pool.sell_tax=trading_taxes(timestamp,self.home['tax'],self.c.buy_tax_override,self.c.sell_tax_override)
        self.settle_epoch()
        # Actions occur at this timestamp; accrual is advanced only afterwards.
        cost=self.reset_auction()
        self.trade_speculators();self.open_charters();self.buy_licenses(cost);self.prebuy_inventory();self.trade_banker_inventory();self.retire_branches();self.protocol_actions()
        self.license_rate=.9*self.license_rate+.1*self.flow['licenses_bought']/dt
        self.retire_rate=.9*self.retire_rate+.1*self.flow['branches_retired']/dt
        self.gross_withdraw_rate=.9*self.gross_withdraw_rate+.1*self.flow['gross_withdrawn']/dt
        new_momentum=math.log(self.pool.price/self.last_price)/dt
        alpha=1-math.exp(-self.c.dt_hours/self.c.momentum_memory_hours)
        self.momentum=(1-alpha)*self.momentum+alpha*new_momentum;self.last_price=self.pool.price
        self.check();self.record()

    def run(self):
        # An explicit pre-action observation makes hour zero a real sell-now quote.
        self.record()
        steps=round(self.c.days*24/self.c.dt_hours)
        for _ in range(steps):
            self.step()
        self.check()
        frame=pd.DataFrame(self.rows)
        frame['phase']=['initial']+['after_actions']*steps
        return dict(frame=frame,events=pd.DataFrame(self.events),totals=self.totals,
            final_population=pd.DataFrame(dict(charter=self.ids,branches=self.n,balance=self.balance,cash=self.cash,
                wallet_tokens=self.inventory,withdrawal_cash=self.owner_realized,external_spend=self.owner_spent)),
            config=asdict(self.c),initial_eth=self.initial_eth,initial_tokens=self.initial_tokens)


def simulate(config,seed=20260915,forecast=None):return Economy(config,seed,forecast).run()


def consistency_iteration(config,iterations=5,damping=.5,seed=20260915):
    """Damped forecast/realized-path diagnostic; convergence is not a Nash proof.

Beyond the simulated horizon the trial price/branch path is held flat, explicitly
making this a terminal-tail sensitivity experiment rather than a unique solution.
"""
    s=legacy.snapshot();hours=np.arange(0,config.days*24+config.dt_hours/2,config.dt_hours)
    trial=dict(hours=hours,price=np.full(len(hours),s['eth']/s['token']),branches=np.full(len(hours),s['branches'],dtype=float))
    history=[];last=None
    for i in range(iterations):
        last=simulate(config,seed,trial)
        frame=last['frame'].drop_duplicates('hour',keep='last')
        actual_price=np.interp(hours,frame.hour,frame.price);actual_branches=np.interp(hours,frame.hour,frame.branches)
        residual=float(np.max(np.abs(np.log(actual_price/trial['price']))))
        history.append(dict(iteration=i+1,max_abs_log_price_error=residual,peak_h=float(hours[np.argmax(actual_price)]),
            last_price_ratio=float(actual_price[-1]/(s['eth']/s['token']))))
        trial['price']=np.exp((1-damping)*np.log(trial['price'])+damping*np.log(actual_price))
        trial['branches']=(1-damping)*trial['branches']+damping*actual_branches
    return pd.DataFrame(history),last
