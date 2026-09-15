"""Conditional STANDARD exit model. Offline numerical experiment, never an executor.

Market state is observed; behavior is assumed. Maximizes a precommitted exit time
on each scenario's mean proceeds curve, NOT the mean of hindsight path maxima.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from liquidity import ConcentratedPool, LiquidityCurve

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'notebook-evidence'
WAD = 1e18

def read(name):
    return json.loads((EVIDENCE / name).read_text())

def fee(gross, pending, withdrawn):
    # The user's own proposed exit contributes to congestion. D+W is unchanged
    # by moving the proposed gross amount from ledger debt to withdrawals.
    pressure = (withdrawn + gross) / max(pending + withdrawn, 10_000_000)
    return .02 + .58 * min(pressure / .10, 1.0)**2

@dataclass
class Pool:
    eth: float
    token: float
    available_eth: float
    lp_fee: float = .01
    buy_tax: float = .02
    sell_tax: float = .03

    @property
    def price(self):
        return self.eth / self.token

    def quote_sell(self, quantity):
        effective = max(0., quantity) * (1-self.lp_fee)
        gross = self.eth * effective / (self.token+effective)
        return min(gross, self.available_eth) * (1-self.sell_tax)

    def sell(self, quantity):
        effective = max(0., quantity) * (1-self.lp_fee)
        gross = self.eth * effective / (self.token+effective)
        if gross > self.available_eth:
            # Stop at the modeled real-ETH boundary; no negative reserve or
            # invented withdrawal of virtual backing. Unfilled tokens remain held.
            gross = self.available_eth
            effective = self.token*gross/max(self.eth-gross, 1e-12)
            quantity = effective/(1-self.lp_fee)
        self.eth -= gross
        self.token += effective
        self.available_eth -= gross
        return gross*(1-self.sell_tax), gross*self.sell_tax, quantity

    def buy(self, eth, exempt=False):
        tax = 0 if exempt else self.buy_tax
        effective = eth*(1-tax)*(1-self.lp_fee)
        out = self.token*effective/(self.eth+effective)
        self.eth += effective
        self.token -= out
        self.available_eth += effective
        return out, eth*tax

    def quote_buy(self, tokens):
        if tokens >= self.token:
            return math.inf
        return self.eth*tokens/(self.token-tokens)/(1-self.buy_tax)/(1-self.lp_fee)

def snapshot():
    home = read('home.json')['snapshot']
    state = {x['label']:x.get('value') for x in read('state.json')['values']}
    q = int(state['getSlot0'][0])/2**96
    liquidity = int(state['getLiquidity'])/WAD
    owners = {}
    for x in read('charters.json'):
        id_, key = x['label'].split('.')
        owners.setdefault(id_, {})[key] = x.get('value')
    active = [x for x in owners.values() if x.get('ownerOf')]
    simple = [int(x['pendingOf'])/WAD for x in active if int(x['branchCountOf']) == 1]
    s = dict(
        timestamp=int(home['blockTimestamp']), genesis=int(home['bank']['genesisTime']),
        eth=liquidity/q, token=liquidity*q,
        available_eth=int(state['vault.poolEthDepth'])/WAD,
        float_tokens=int(state['token.totalSupply'])/WAD-liquidity*q,
        pending=int(state['bank.totalPendingLive'])/WAD,
        branches=int(state['bank.totalBranches']), active_charters=len(active),
        own_pending=float(np.median(simple)),
        base_per_day=int(state['bank.baseIssuancePerDay'])/WAD,
        multiplier=int(state['bank.multiplierWad'])/WAD,
        withdrawn=sum(int(x)/WAD for x in home['withdrawnByDay']),
        contraction_eth=int(home['balances']['contractionVault'])/WAD,
        epoch_flow=int(home['tax']['epochNetFlow'])/WAD,
        epoch_end=int(state['bank.epochEnd']), epoch_days=int(state['bank.epochDays']),
        auction_anchor=int(state['license.auctionAnchor']),
        last_license_price=int(state['license.lastSalePrice'])/WAD,
        next_auction_hours=(int(state['license.auctionAnchor'])+86400-int(home['blockTimestamp']))/3600,
        buy_tax=int(home['tax']['buyTaxNowBps'])/10000,
        sell_tax=int(home['tax']['sellTaxNowBps'])/10000,
        lp_fee=state['getSlot0'][3]/1e6,
    )
    assert sum(int(x['branchCountOf']) for x in active)==s['branches']
    assert abs(sum(int(x['pendingOf'])/WAD for x in active)-s['pending'])<.001
    assert s['eth']>=s['available_eth']>0 and s['float_tokens']>0
    if (EVIDENCE/'liquidity-ticks.json').exists():
        profile=read('liquidity-ticks.json')
        assert profile['blockHash']==read('home.json')['blockHash']
        pool=ConcentratedPool(profile,s['lp_fee'],s['buy_tax'],s['sell_tax'])
        s['protocol_depth_getter']=s['available_eth']
        s['available_eth']=pool.available_eth
        s['pool_token_principal']=pool.real_tokens
        s['float_tokens']=int(state['token.totalSupply'])/WAD-pool.real_tokens
        s['liquidity_profile']=profile
    return s

def observed_flows(s):
    headers=read('swap-time-headers.json')
    logs=read('recent-swaps.json')['logs']
    rows=[]
    for a,b in zip(headers,headers[1:]):
        lo,hi=int(a['number'],16),int(b['number'],16)
        trades=[x['decoded'] for x in logs if lo<=int(x['blockNumber'],16)<hi or (b==headers[-1] and int(x['blockNumber'],16)==hi)]
        # v4 Swap BalanceDelta is from the caller's perspective:
        # negative amount0 = ETH paid into the pool, positive = ETH received.
        buy=sum(max(0,-int(x['amount0']))/WAD for x in trades)
        sell=sum(max(0,int(x['amount0']))/WAD for x in trades)
        sell_tokens=sum(max(0,-int(x['amount1']))/WAD for x in trades)
        rows.append(dict(start=int(a['timestamp'],16),end=int(b['timestamp'],16),buys_eth=buy,sells_eth=sell,sell_tokens=sell_tokens,count=len(trades)))
    def rate(window):
        duration=sum(x['end']-x['start'] for x in window)/3600
        return dict(hours=duration,
                    buy_eth_hour=sum(x['buys_eth'] for x in window)/duration/(1-s['buy_tax']),
                    sell_tokens_day=sum(x['sell_tokens'] for x in window)/duration*24,
                    net_pool_eth_hour=sum(x['buys_eth']-x['sells_eth'] for x in window)/duration)
    return dict(bins=rows,full=rate(rows),recent=rate(rows[-4:]),last_bin=rate(rows[-1:]))

@dataclass
class Scenario:
    name: str
    buy_eth_hour: float
    demand_half_life_hours: float
    sell_hazard_day: float
    exit_hazard_day: float
    exit_drawdown_sensitivity: float
    license_demand_day: float
    external_license_fraction: float = .25
    returned_sell_fraction: float = .90
    buybacks_enabled: bool = False
    coordinated_exit_hour: float | None = None
    coordinated_exit_fraction: float = .5

    def __post_init__(self):
        if self.demand_half_life_hours<=0:raise ValueError('Demand half-life must be positive')
        if min(self.buy_eth_hour,self.sell_hazard_day,self.exit_hazard_day,self.exit_drawdown_sensitivity,self.license_demand_day)<0:
            raise ValueError('Rates must be nonnegative')
        for fraction in [self.external_license_fraction,self.returned_sell_fraction,self.coordinated_exit_fraction]:
            if not 0<=fraction<=1:raise ValueError('Fractions must lie in [0,1]')

def simulate(s, scenario, seed, days=14, dt_hours=1, protected_branches=1,
             expansion_cost=None, internal_expansion=False,owned_wallet_tokens=0):
    rng=np.random.default_rng(seed)
    steps=round(days*24/dt_hours)
    dt=dt_hours/24
    pool=(ConcentratedPool(s['liquidity_profile'],s['lp_fee'],s['buy_tax'],s['sell_tax'])
          if 'liquidity_profile' in s else Pool(s['eth'],s['token'],s['available_eth'],s['lp_fee'],s['buy_tax'],s['sell_tax']))
    held=max(0,s['float_tokens']-owned_wallet_tokens); pending=s['pending']; branches=float(s['branches'])
    protected_pending=s['own_pending']*protected_branches
    pending=max(pending,protected_pending)
    expanded=False; external_cost_eth=0.; wave_done=False
    multiplier=s['multiplier']; daily=s['base_per_day']
    ledger_per_branch=0.; recycled_per_day=0.; recycle_buffer=0.
    vault=s['contraction_eth']; fee_buffer=0.; pol_buffer=0.; flow=s['epoch_flow']; previous_flow=0.
    positive_streak=0
    epoch_end=(s['epoch_end']-s['timestamp'])/3600
    withdrawals={int((s['timestamp']-s['genesis'])//86400):s['withdrawn']}
    peak=pool.price; initial_price=peak
    previous_sale=s['last_license_price']; auction_day=0; auction_sold=100.
    floor_price=2*daily*multiplier/branches; opening=2*previous_sale
    buy_level=scenario.buy_eth_hour*rng.lognormal(-.5*.3**2,.3)
    half_life=scenario.demand_half_life_hours*rng.lognormal(-.5*.3**2,.3)
    sell_hazard=scenario.sell_hazard_day*rng.lognormal(-.5*.25**2,.25)
    exit_hazard=scenario.exit_hazard_day*rng.lognormal(-.5*.35**2,.35)
    sentiment=0.; records=[]
    for i in range(steps+1):
        hours=i*dt_hours; time=s['timestamp']+hours*3600
        day=int((time-s['genesis'])//86400)
        withdrawals={d:v for d,v in withdrawals.items() if d>day-7}
        withdrawn=sum(withdrawals.values())
        records.append((hours,pool.eth,pool.token,pool.available_eth,pool.price,
                        ledger_per_branch,pending,withdrawn,branches,multiplier,vault,
                        protected_pending,external_cost_eth,float(expanded),
                        pool.sqrt if isinstance(pool,ConcentratedPool) else math.sqrt(pool.token/pool.eth),getattr(pool,'scale',1.)))
        if i==steps:break
        if expansion_cost is not None and not expanded and hours>=s['next_auction_hours']:
            if not internal_expansion or protected_pending>=expansion_cost:
                if internal_expansion:
                    protected_pending-=expansion_cost;pending-=expansion_cost
                else:
                    external_cost_eth=pool.quote_buy(expansion_cost)
                    _,tax=pool.buy(external_cost_eth)
                    fee_buffer+=tax;flow+=external_cost_eth*(1-pool.buy_tax)
                branches+=1;protected_branches+=1;expanded=True
        if hours>=epoch_end:
            signal=flow+previous_flow
            # Documented rule: previous completed flow is zero at genesis;
            # cuts act on a negative signal, raises need consecutive positives.
            if signal<0:multiplier=max(.2,multiplier-.15);positive_streak=0
            elif signal>0:
                positive_streak+=1
                if positive_streak>=2:multiplier=min(1.25,multiplier+.10)
            else:positive_streak=0
            if flow<=0:vault+=.70*fee_buffer
            pol_buffer+=.15*fee_buffer
            # Expansion reserves and team allocation leave modeled trading capital.
            fee_buffer=0.; previous_flow=flow; flow=0.
            recycled_per_day=recycle_buffer/s['epoch_days'];recycle_buffer=0.
            epoch_end+=s['epoch_days']*24
        if branches>0:
            earnings=(daily*multiplier+recycled_per_day)*dt
            pending+=earnings; ledger_per_branch+=earnings/branches
            protected_pending+=earnings/branches*protected_branches
        sentiment=.85*sentiment+rng.normal(0,.22)
        spend=buy_level*math.exp(-math.log(2)*hours/half_life)*math.exp(sentiment-.09)*dt_hours
        out,tax=pool.buy(spend);held+=out;fee_buffer+=tax
        flow+=spend*(1-pool.buy_tax)
        this_auction=int((time-s['auction_anchor'])//86400)
        if this_auction>auction_day:
            auction_day=this_auction;auction_sold=0.
            floor_price=2*daily*multiplier/max(branches,1.)
            opening=max(floor_price,2*previous_sale)
        if this_auction>=1 and auction_sold<100 and branches<9990:
            hour_in_day=((time-s['auction_anchor'])%86400)/3600
            cost=floor_price+(opening-floor_price)*2**(-hour_in_day/4)
            # Population expectation, not a simulation of 1,000 independent owners.
            wanted=min(100-auction_sold,scenario.license_demand_day*dt,9990-branches)
            internal=1-scenario.external_license_fraction
            count=min(wanted,max(0,pending-protected_pending)/max(cost*internal,1e-9))
            pending-=count*cost*internal
            cash_tokens=count*cost*(1-internal)
            if cash_tokens>0:
                purchase=pool.quote_buy(cash_tokens)
                _,tax=pool.buy(purchase);fee_buffer+=tax;flow+=purchase*(1-pool.buy_tax)
            if count>0:previous_sale=cost
            branches+=count;auction_sold+=count
        drawdown=max(0.,1-pool.price/peak)
        exit_rate=exit_hazard+scenario.exit_drawdown_sensitivity*drawdown
        fraction=1-math.exp(-exit_rate*dt)
        if scenario.coordinated_exit_hour is not None and hours>=scenario.coordinated_exit_hour and not wave_done:
            fraction=1-(1-fraction)*(1-scenario.coordinated_exit_fraction)
            wave_done=True
        gross=max(0,pending-protected_pending)*fraction
        resolution=fee(gross,pending,withdrawn)
        pending-=gross;branches=protected_branches+(branches-protected_branches)*(1-fraction)
        withdrawals[day]=withdrawals.get(day,0)+gross
        recycle_buffer+=gross*resolution*.5
        minted=gross*(1-resolution)
        returns_sold=minted*scenario.returned_sell_fraction
        spec_sold=held*(1-math.exp(-sell_hazard*dt))
        held=held-spec_sold+minted-returns_sold
        _,tax,filled=pool.sell(spec_sold+returns_sold)
        held+=spec_sold+returns_sold-filled
        fee_buffer+=tax;flow-=tax/max(pool.sell_tax,1e-9)
        if scenario.buybacks_enabled and flow<0 and vault>0:
            spend=min(.10*vault,.002*pool.available_eth)
            pool.buy(spend,exempt=True);vault-=spend;flow+=spend
        if scenario.buybacks_enabled and pol_buffer>0:
            # An explicit optimistic execution case. Adds proportional virtual and
            # real reserves after spending half the ETH on tokens.
            amount=pol_buffer*.5;tokens,_=pool.buy(amount,exempt=True)
            if isinstance(pool,ConcentratedPool):pool.add_proportional(amount,tokens)
            else:pool.eth+=amount;pool.token+=tokens;pool.available_eth+=amount
            pol_buffer=0.
        peak=max(peak,pool.price)
        assert held>=-1e-6 and pending>=protected_pending-1e-6 and branches>=protected_branches
    return np.array(records)

def liquidate(path, gross, charter=True,lp_fee=.01,sell_tax=.03,liquidity_profile=None):
    gross=np.asarray(gross)
    fees=.02+.58*np.minimum((path[:,7]+gross)/np.maximum(path[:,6]+path[:,7],10_000_000)/.1,1)**2 if charter else np.zeros(len(path))
    tokens=gross*(1-fees)
    if liquidity_profile is not None:
        return LiquidityCurve(liquidity_profile).sell_quotes(path[:,14],tokens,path[:,15],lp_fee,sell_tax)
    effective=tokens*(1-lp_fee)
    return np.minimum(path[:,1]*effective/(path[:,2]+effective),path[:,3])*(1-sell_tax)

def strategies(path,s):
    reward=path[:,5];base=s['own_pending']+reward
    quote=lambda gross,charter=True:liquidate(path,gross,charter,s['lp_fee'],s['sell_tax'],s.get('liquidity_profile'))
    result={
        'wallet_100k':quote(100_000,charter=False),
        'wallet_1m':quote(1_000_000,charter=False),
        'own_one_branch':quote(base),
        'own_ten_branches':quote(10*base),
    }
    return result

def analytic_grid(s):
    rows=[]
    accrual=s['base_per_day']*s['multiplier']/s['branches']
    for half_life in [.25,.5,1,2,4,7,14]:
        decline=math.log(2)/half_life
        optimum=max(0.,1/decline-s['own_pending']/accrual)
        # This is an analytic sensitivity benchmark, not a fitted price forecast.
        rows.append(dict(price_half_life_days=half_life,one_branch_best_hours=24*optimum,
                         max_license_tokens_constant_fee=.98*accrual/(decline*math.e)))
    return rows
