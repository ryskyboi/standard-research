"""Inventory-constrained participant model initialized from observed addresses.

Decision clocks and ticket sizes are descriptive inputs. Reservation prices,
future arrival intensity, crowd expectations and execution remain assumptions.
This is not an equilibrium solution or a calibrated forecast of market prices.
"""
from dataclasses import dataclass,asdict
from collections import Counter
import json,copy
import numpy as np
import pandas as pd
from functools import lru_cache
from participant_flows import ROOT,read,utc
from participant_decisions import resolution_fee
from liquidity import ConcentratedPool
read=lru_cache(maxsize=32)(read)
@lru_cache(maxsize=12)
def csv(path):return pd.read_csv(path)

@dataclass
class Config:
    name:str='Observed clocks; cautious beliefs'
    hours:float=24
    dt_hours:float=.25
    prior_growth_day:float=-.03
    belief_dispersion:float=.08
    momentum_weight:float=.15
    reversion_share:float=.35
    new_capital_multiplier:float=1.
    seller_activation_multiplier:float=1.
    buyer_activity_multiplier:float=1.
    owner_review_hours:float=1.
    valuation_days:float=60.
    spec_holding_days:float=1.
    discount_day:float=.01
    expected_new_branches_day:float=100.
    expected_future_withdrawals_day:float=0.
    execute_buybacks:bool=False
    buyback_start_hours:float=0.
    buyback_tax_exempt:bool=False
    allow_game:bool=True
    allow_expansion:bool=True
    allow_retirement:bool=True
    waiting_enabled:bool=True
    prefund_enabled:bool=True
    wallet_first:bool=False

class Economy:
    def __init__(self,cfg=Config(),seed=1,root=ROOT):
        self.c=cfg;self.rng=np.random.default_rng(seed);self.root=root
        if not 0<cfg.hours<=48 or cfg.dt_hours<=0 or cfg.dt_hours>1:raise ValueError('Use a 0–48h horizon and a time step <=1h')
        e=root/'behavior-evidence';d=root/'behavior-results'
        self.s={x['label']:x.get('value') for x in read(e/'state.json')}
        if int(self.s['charter.chartersPerDay'])!=0:raise ValueError('ETH Charter auctions enabled: extend admission model before using this state')
        self.pin=int(read(e/'target.json')['header']['timestamp'],16);self.h=0.
        self.profile=read(e/'liquidity.json');self.pool=ConcentratedPool(self.profile,buy_tax=int(self.s['hook.buyTaxBps'])/10000,sell_tax=int(self.s['hook.sellTaxBps'])/10000)
        self.start_price=self.pool.price
        w=csv(d/'population.csv.gz');w=w[(w.wallet_tokens>1e-12)|(w.native_ETH_budget>1e-12)|(w.charter_count>0)].copy()
        self.address=w.address.to_list();self.index={a:i for i,a in enumerate(self.address)}
        self.cash=w.native_ETH_budget.to_numpy().copy();self.tokens=w.wallet_tokens.to_numpy().copy();self.group=w.strategy.to_numpy().copy()
        self.bias=self.rng.normal(cfg.prior_growth_day,cfg.belief_dispersion,len(w));self.revert=self.rng.random(len(w))<cfg.reversion_share
        self.initial_cash=self.cash.copy();self.owner_flag=w.charter_count.to_numpy()>0
        self.sell_rates=w.sell_event_rate_hour.to_numpy().copy();self.buy_rates=w.buy_event_rate_hour.to_numpy().copy()
        self.sale_fraction=w.sale_fraction_median.fillna(.95).to_numpy().copy();self.buy_ticket=w.buy_ticket_mean_ETH.fillna(.1).to_numpy().copy()
        charters=csv(d/'participants/charters.csv');self.ids=charters.charter_id.to_numpy();self.n=charters.branches.to_numpy().copy();self.ledger=charters.pending_tokens.to_numpy().copy();self.owner=np.array([self.index[a] for a in charters.owner])
        self.used=np.zeros(len(charters),int)
        lic=read(root/'empirical-evidence/events.json.gz')['logs']+read(root/'strategy-current/delta-events.json.gz')+read(e/'delta-events.json.gz')
        today=int(self.s['license.currentDay']);per_id=Counter()
        for x in lic:
            if x['event']=='LicensesPurchased' and int(x['decoded']['day'])==today:per_id[int(x['decoded']['charterId'])]+=int(x['decoded']['count'])
        self.used=np.array([per_id[i] for i in self.ids]);self.day=today;self.sold=int(self.s['license.soldToday'])
        self.day_open=int(self.s['license.dayStartPrice'])/1e18;self.floor=int(self.s['license.dayFloorPrice'])/1e18;self.last_sale=int(self.s['license.lastSalePrice'])/1e18;self.last_sale_day=int(self.s['license.lastSaleDay'])
        self.quota=int(self.s['license.licensesPerDay']);self.max_per=int(self.s['license.MAX_PER_CHARTER_PER_DAY']);self.max_branches=int(self.s['bank.MAX_BRANCHES'])
        self.anchor=int(self.s['license.auctionAnchor']);self.half_life=int(self.s['license.dayHalfLife'])/3600;self.floor_days=int(self.s['license.floorPaybackDays'])
        self.base_issue=int(self.s['bank.baseIssuancePerDay'])/1e18;self.multiplier=int(self.s['bank.multiplierWad'])/1e18;self.recycle_rate=int(self.s['bank.recycleRate'])/1e18*86400
        self.recycle_buffer=int(self.s['bank.recycleBuffer'])/1e18
        self.withdrawal_buckets={int(x['label'].split('.')[1]):int(x['value'])/1e18 for x in read(e/'withdrawals.json')}
        self.W=self.rolling_withdrawals(0.)
        self.vault=int(self.s['balance.contractionVault'])/1e18;self.expansion=int(self.s['balance.expansionVault'])/1e18;self.pol=int(self.s['balance.polManager'])/1e18;self.hook=int(self.s['balance.taxHook'])/1e18;self.team=0.
        self.vault_depth=int(self.s['vault.poolEthDepth'])/1e18;self.last_tick=-1e10 if int(self.s['vault.lastTickAt'])==0 else (int(self.s['vault.lastTickAt'])-self.pin)/3600
        self.cooldown=int(self.s['vault.tickCooldown'])/3600
        self.epoch_end=(int(self.s['bank.epochEnd'])-self.pin)/3600;self.epoch_days=int(self.s['bank.epochDays']);self.epoch_flow=int(self.s['hook.epochNetFlow'])/1e18;self.previous_flow=int(self.s['bank.previousEpochFlow'])/1e18;self.streak=int(self.s['bank.positiveSignalStreak'])
        self.lp_eth=self.lp_tokens=0.;self.minted=self.burned=self.new_cash=0.;self.issued=self.deposited=self.license_spent=self.gross_retired=0.
        self.outside_tokens=int(self.s['token.totalSupply'])/1e18-self.pool.real_tokens-self.tokens.sum()
        self.initial_pending=self.ledger.sum();self.initial_eth=self.total_eth();self.initial_tokens=self.total_tokens()
        self.obs=read(d/'observation-metadata.json');self.external_rate=self.obs['new_buyer_native_ETH_hour_last2h']*cfg.new_capital_multiplier
        self.rates=csv(d/'activity-calibration.csv').set_index(['strategy','side'])
        # Previously inactive wallets need a separate first-sale activation process.
        trades=csv(d/'classified-trades.csv.gz');first=trades[trades.side=='sell'].groupby('address').timestamp.min()
        onsets=int((first>=self.pin-7200).sum());inactive=max(1,int(((w.strategy=='inactive_holder')&(w.wallet_tokens>0)).sum()))
        self.activation_rate=onsets/(2*inactive)
        self.momentum=0.;self.path=[];self.events=[];self.errors=[];self.flow={};self.total_flow=Counter()
        self.record()

    def total_eth(self):return self.pool.available_eth+self.cash.sum()+self.vault+self.expansion+self.pol+self.hook+self.team+self.lp_eth
    def total_tokens(self):return self.pool.real_tokens+self.tokens.sum()+self.lp_tokens+self.outside_tokens
    def bank_day(self,hours):return int((self.pin+hours*3600-int(self.s['bank.genesisTime']))//86400)
    def rolling_withdrawals(self,hours):
        day=self.bank_day(hours)
        return sum(v for d,v in self.withdrawal_buckets.items() if day-6<=d<=day)
    @property
    def issuance(self):return self.base_issue*self.multiplier+self.recycle_rate
    def addflow(self,k,v):self.flow[k]=self.flow.get(k,0.)+v;self.total_flow[k]+=v

    def buy(self,amount,kind,exempt=False):
        tokens,tax=self.pool.buy(float(amount),exempt=exempt);self.hook+=tax;self.lp_eth+=(amount-tax)*self.pool.lp_fee;self.epoch_flow+=amount-tax
        self.addflow(kind,amount);self.addflow('buy_pool_ETH',amount-tax);return tokens
    def sell(self,quantity,kind):
        cash,tax,filled=self.pool.sell(float(quantity));self.hook+=tax;self.lp_tokens+=filled*self.pool.lp_fee;self.epoch_flow-=cash+tax
        self.addflow(kind,cash);self.addflow('sell_pool_ETH',cash+tax);self.addflow(kind+'_tokens',filled);return cash,filled

    def expected_price(self,owner,days):
        days=np.asarray(days);g=self.bias[owner]+self.c.momentum_weight*np.clip(self.momentum,-1.5,1.5)
        value=self.pool.price*np.exp(np.clip(np.asarray(g)[...,None]*days,-15,15))
        reversion=np.asarray(self.revert[owner])[...,None]*np.minimum(days,1.)*.5
        desired=value*(self.start_price/self.pool.price)**reversion
        budget=self.cash.sum()+self.external_rate*np.minimum(days*24,max(0,self.c.hours-self.h))+(self.vault if self.c.execute_buybacks else 0)
        cap=1/self.pool.curve.sqrt_from_eth(self.pool.available_eth+budget*(1-self.pool.buy_tax)*(1-self.pool.lp_fee))**2
        return np.minimum(desired,cap)

    def branch_value(self,n,ledger,owners,total=None,pending=None,W=None,include_now=True):
        n=np.atleast_1d(n);ledger=np.atleast_1d(ledger);owners=np.atleast_1d(owners)
        times=np.array([0,1/24,.125,.25,.5,1,2,4,7,14,30,60]);times=times[(times<=self.c.valuation_days)&((times>=0) if include_now else (times>0))]
        if not len(times):raise ValueError('Branch valuation horizon must include at least one hour')
        total=max(1,int(self.n.sum()) if total is None else total);pending=self.ledger.sum() if pending is None else pending;W=self.W if W is None else W
        growth=self.c.expected_new_branches_day;cap=max(total,self.max_branches*int((self.n>0).sum()))
        if growth:
            cutoff=max(0,(cap-total)/growth);u=np.minimum(times,cutoff)
            per_branch=self.issuance/growth*np.log1p(growth*u/total)+np.maximum(0,times-cutoff)*self.issuance/cap
        else:per_branch=self.issuance*times/total
        gross=ledger[:,None]+n[:,None]*per_branch
        futureW=np.array([self.rolling_withdrawals(self.h+t*24) for t in times])+max(0,W-self.W)*(times<7)+self.c.expected_future_withdrawals_day*np.minimum(times,7)
        futureD=np.maximum(gross,pending+self.issuance*times-self.c.expected_future_withdrawals_day*times)
        fee=.02+.58*np.minimum((futureW+gross)/np.maximum(futureD+futureW,1e7)/.1,1)**2
        prices=self.expected_price(owners,times)
        values=self.pool.curve.sell_quotes(1/np.sqrt(prices),gross*(1-fee),lp_fee=self.pool.lp_fee,sell_tax=self.pool.sell_tax)*np.exp(-self.c.discount_day*times)
        values[n<=0]=0;at=values.argmax(axis=1);return values[np.arange(len(n)),at],times[at]

    def withdrawal_value(self,tokens,owners):
        now=self.pool.curve.sell_quotes(self.pool.sqrt,tokens,lp_fee=self.pool.lp_fee,sell_tax=self.pool.sell_tax)
        future=self.expected_price(np.atleast_1d(owners),np.array([self.c.spec_holding_days]))[:,0]
        held=self.pool.curve.sell_quotes(1/np.sqrt(future),tokens,lp_fee=self.pool.lp_fee,sell_tax=self.pool.sell_tax)*np.exp(-self.c.discount_day*self.c.spec_holding_days)
        return np.maximum(now,held),held>now+1e-6

    def license_price(self):
        timestamp=self.pin+self.h*3600;day=int((timestamp-self.anchor)//86400)
        if day!=self.day:
            self.day=day;self.used[:]=0;self.sold=0;self.floor=self.floor_days*self.issuance/max(1,self.n.sum())
            self.day_open=2*self.last_sale if self.last_sale_day==day-1 else 2*self.floor
        elapsed=(timestamp-self.anchor-day*86400)/3600
        return self.floor+(self.day_open-self.floor)*2**(-elapsed/self.half_life)

    def game_decisions(self):
        if not self.c.allow_game:return
        cost=self.license_price();alive=np.flatnonzero(self.n>0)
        if not len(alive):return
        before,_=self.branch_value(self.n[alive],self.ledger[alive],self.owner[alive],include_now=False)
        if self.c.allow_retirement:
            # Evaluate every feasible partial retirement, retaining the rest's option value.
            best=before.copy();counts=np.zeros(len(alive),int)
            for k in range(1,self.max_branches+1):
                at=np.flatnonzero(self.n[alive]>=k)
                if not len(at):continue
                ids=alive[at];gross=self.ledger[ids]*k/self.n[ids]
                fee=resolution_fee(gross,self.W,self.ledger.sum());immediate,_=self.withdrawal_value(gross*(1-fee),self.owner[ids])
                remaining,_=self.branch_value(self.n[ids]-k,self.ledger[ids]-gross,self.owner[ids],total=max(1,self.n.sum()-k),include_now=False)
                choose=immediate+remaining>best[at]+1e-6
                best[at[choose]]=immediate[choose]+remaining[choose];counts[at[choose]]=k
            for j in self.rng.permutation(np.flatnonzero(counts)):
                i=alive[j];k=counts[j];gross=self.ledger[i]*k/self.n[i];fee=float(resolution_fee(gross,self.W,self.ledger.sum()))
                now,_=self.branch_value([self.n[i]],[self.ledger[i]],[self.owner[i]],include_now=False)
                proceeds,hold=self.withdrawal_value(np.array([gross*(1-fee)]),[self.owner[i]]);rest,_=self.branch_value([self.n[i]-k],[self.ledger[i]-gross],[self.owner[i]],total=max(1,self.n.sum()-k),pending=self.ledger.sum()-gross,W=self.W+gross,include_now=False)
                if proceeds[0]+rest[0]<=now[0]+1e-6:continue
                self.ledger[i]-=gross;self.n[i]-=k;self.W+=gross;self.gross_retired+=gross;self.recycle_buffer+=gross*fee/2
                day=self.bank_day(self.h);self.withdrawal_buckets[day]=self.withdrawal_buckets.get(day,0.)+gross
                minted=gross*(1-fee);self.minted+=minted
                if hold[0]:self.tokens[self.owner[i]]+=minted;self.addflow('branch_withdraw_held_tokens',minted)
                else:
                    cash,filled=self.sell(minted,'branch_withdraw_sell_ETH');self.cash[self.owner[i]]+=cash;self.tokens[self.owner[i]]+=minted-filled
                self.addflow('branches_retired',k);self.events.append(dict(hour=self.h,event='retire',charter_id=int(self.ids[i]),count=int(k),gross_tokens=gross,resolution_fee=fee))
        remaining=self.quota-self.sold
        if not self.c.allow_expansion:return
        if remaining<=0:return
        for _ in range(self.max_per):
            eligible=np.flatnonzero((self.n>0)&(self.n<self.max_branches)&(self.used<self.max_per))
            if not len(eligible) or remaining<=0:break
            internal=np.minimum(cost,self.ledger[eligible]);gap=cost-internal;own=self.owner[eligible];inventory=np.minimum(gap,self.tokens[own]);fresh=gap-inventory
            cash_cost=np.array([self.pool.quote_buy(x) for x in fresh]);opportunity=self.pool.curve.sell_quotes(self.pool.sqrt,inventory,lp_fee=self.pool.lp_fee,sell_tax=self.pool.sell_tax)
            before,_=self.branch_value(self.n[eligible],self.ledger[eligible],own)
            after,_=self.branch_value(self.n[eligible]+1,self.ledger[eligible]-internal,own,total=self.n.sum()+1)
            edge=after-before-cash_cost-opportunity
            if self.c.waiting_enabled:
                # Four-hour waiting option, discounted by an explicit quota-exhaustion belief.
                cheaper=self.floor+(cost-self.floor)*2**(-4/self.half_life)
                saving=(cost-cheaper)*self.pool.price*(1-self.pool.sell_tax)*(1-self.pool.lp_fee)
                missed=self.issuance/max(1,self.n.sum()+1)*4/24*self.pool.price
                stockout=1-np.exp(-self.c.expected_new_branches_day*4/24/max(1,remaining))
                edge-=np.maximum(0,(1-stockout)*saving-missed)
            edge[cash_cost>self.cash[own]+1e-9]=-np.inf
            chosen=eligible[np.argsort(-edge)]
            for i in chosen:
                j=int(np.where(eligible==i)[0][0])
                if edge[j]<=1e-6 or remaining<=0:break
                a=self.owner[i];inside=min(cost,self.ledger[i]);wallet=min(cost-inside,self.tokens[a]);need=cost-inside-wallet;spend=self.pool.quote_buy(need)
                if spend>self.cash[a]+1e-9:continue
                old_value,_=self.branch_value([self.n[i]],[self.ledger[i]],[a])
                new_value,_=self.branch_value([self.n[i]+1],[self.ledger[i]-inside],[a],total=self.n.sum()+1)
                if new_value[0]-old_value[0]-spend-self.pool.quote_sell(wallet)<=1e-6:continue
                # Shared wallet budget is consumed once across every owned Charter.
                self.cash[a]-=spend;received=self.buy(spend,'license_fresh_buy_ETH') if spend else 0.
                assert abs(received-need)<1e-5
                self.tokens[a]-=wallet;deposit=wallet+received;self.burned+=deposit;self.deposited+=deposit;self.ledger[i]+=deposit
                self.ledger[i]-=cost;self.license_spent+=cost;self.n[i]+=1;self.used[i]+=1;self.sold+=1;remaining-=1;self.last_sale=cost;self.last_sale_day=self.day
                for k,v in [('licenses',1),('license_internal_tokens',inside),('license_wallet_tokens',wallet),('license_fresh_tokens',received)]:self.addflow(k,v)
                self.events.append(dict(hour=self.h,event='license',charter_id=int(self.ids[i]),price_tokens=cost,internal_tokens=inside,wallet_tokens=wallet,fresh_tokens=received))

    def prefund_game(self):
        if not(self.c.allow_game and self.c.allow_expansion and self.c.prefund_enabled):return
        until=(self.anchor+(self.day+1)*86400-(self.pin+self.h*3600))/86400
        expected_cost=2*self.last_sale if self.last_sale_day==self.day else 2*self.floor
        # One prospective license per Charter; shared wallets updated after every purchase.
        reserved=0
        for i in np.flatnonzero((self.n>0)&(self.n<self.max_branches)):
            if reserved>=self.quota:break
            a=self.owner[i];ledger=self.ledger[i]+self.issuance*self.n[i]/max(1,self.n.sum())*until
            needed=max(0,expected_cost-ledger-self.tokens[a])
            if needed<=0 or self.cash[a]<=1e-8:continue
            future=float(self.expected_price(a,np.array([until]))[0])
            if future<=self.pool.price:continue
            spend=self.pool.quote_buy(needed)
            if spend>self.cash[a]:continue
            before,_=self.branch_value([self.n[i]],[self.ledger[i]],[a]);after,_=self.branch_value([self.n[i]+1],[max(0,self.ledger[i]-expected_cost)],[a],total=self.n.sum()+1)
            if after[0]-before[0]<=spend+self.pool.quote_sell(min(self.tokens[a],expected_cost)):continue
            self.cash[a]-=spend;self.tokens[a]+=self.buy(spend,'game_prefund_ETH');reserved+=1

    def wallet_decisions(self):
        dt=self.c.dt_hours
        count=self.rng.poisson(self.obs['new_buyer_addresses_hour_last2h']*dt*self.c.new_capital_multiplier)
        if count:
            # Bootstrap observed entry budgets. Capital arrival does not compel a buy.
            budgets=self.rng.choice(self.obs['observed_new_buyer_tickets_ETH'],count)
            self.address.extend(f'future-entry-{self.h}-{j}' for j in range(count));self.cash=np.append(self.cash,budgets);self.initial_cash=np.append(self.initial_cash,budgets);self.tokens=np.append(self.tokens,np.zeros(count));self.group=np.append(self.group,np.repeat('new_entrant',count));self.bias=np.append(self.bias,self.rng.normal(self.c.prior_growth_day,self.c.belief_dispersion,count));self.revert=np.append(self.revert,self.rng.random(count)<self.c.reversion_share);self.owner_flag=np.append(self.owner_flag,np.zeros(count,bool));self.new_cash+=budgets.sum();self.addflow('external_capital_ETH',budgets.sum())
            self.sell_rates=np.append(self.sell_rates,np.ones(count));self.buy_rates=np.append(self.buy_rates,np.ones(count));self.sale_fraction=np.append(self.sale_fraction,np.full(count,.95));self.buy_ticket=np.append(self.buy_ticket,budgets)
        for i in self.rng.permutation(len(self.cash)):
            group=self.group[i]
            if self.tokens[i]<1e-12 and self.cash[i]<1e-8:continue
            def rate(side):
                if group=='new_entrant':return 1.
                if side=='sell' and self.sell_rates[i]==0:return self.activation_rate
                return min(4.,self.sell_rates[i] if side=='sell' else self.buy_rates[i])
            sell_clock=self.rng.random()<1-np.exp(-rate('sell')*dt*self.c.seller_activation_multiplier)
            buy_clock=self.rng.random()<1-np.exp(-rate('buy')*dt*self.c.buyer_activity_multiplier)
            if not(sell_clock or buy_clock):continue
            future=float(self.expected_price(i,np.array([self.c.spec_holding_days]))[0])*np.exp(-self.c.discount_day*self.c.spec_holding_days)
            if sell_clock and self.tokens[i]>1e-10 and future<self.pool.price:
                frac=self.sale_fraction[i]
                qty=min(self.tokens[i],self.tokens[i]*max(.01,frac));cash,filled=self.sell(qty,'owner_spec_sell_ETH' if self.owner_flag[i] else 'spec_sell_ETH');self.cash[i]+=cash;self.tokens[i]-=filled
                if self.sell_rates[i]==0:
                    if not self.owner_flag[i]:self.group[i]='recent_seller'
                    self.sell_rates[i]=float(self.rates.loc[('recent_seller','sell'),'events_per_address_hour']);self.addflow('new_seller_activations',1)
            elif buy_clock and self.cash[i]>1e-8:
                ticket=self.buy_ticket[i]
                spend=min(self.cash[i],max(.001,ticket));trial=copy.copy(self.pool);got,_=trial.buy(spend)
                value=float(trial.curve.sell_quotes(1/np.sqrt(future),got,lp_fee=trial.lp_fee,sell_tax=trial.sell_tax))
                if value<=spend+1e-6:continue
                self.cash[i]-=spend;self.tokens[i]+=self.buy(spend,'owner_spec_buy_ETH' if self.owner_flag[i] else 'spec_buy_ETH')

    def protocol(self):
        if self.h>=self.epoch_end:
            signal=self.epoch_flow+self.previous_flow
            if signal<0:self.multiplier=max(.2,self.multiplier-.15);self.streak=0
            elif signal>0:
                self.streak+=1
                if self.streak>=2:self.multiplier=min(1.25,self.multiplier+.1)
            vault_share=1-int(self.s['splitter.teamShareBps'])/10000-int(self.s['splitter.polShareBps'])/10000
            if self.epoch_flow>0:self.expansion+=vault_share*self.hook
            else:self.vault+=vault_share*self.hook
            self.pol+=int(self.s['splitter.polShareBps'])/10000*self.hook;self.team+=int(self.s['splitter.teamShareBps'])/10000*self.hook;self.hook=0.
            self.previous_flow=self.epoch_flow;self.epoch_flow=0.;self.epoch_end+=24*self.epoch_days;self.recycle_rate=self.recycle_buffer/self.epoch_days;self.recycle_buffer=0.
        # Owner action is a scenario switch; there is no fictitious negative-flow gate.
        if self.c.execute_buybacks and self.h>=self.c.buyback_start_hours and self.h-self.last_tick>=self.cooldown-1e-9 and self.vault>0:
            depth=self.vault_depth*np.sqrt(self.pool.price/self.start_price)
            spend=min(self.vault*int(self.s['vault.tickVaultPctBps'])/10000,depth*int(self.s['vault.effectiveTickPoolPctBps'])/10000)
            self.vault-=spend;self.burned+=self.buy(spend,'buyback_ETH',self.c.buyback_tax_exempt);self.last_tick=self.h

    def check(self):
        err=dict(hour=self.h,ETH_error=self.total_eth()-self.initial_eth-self.new_cash,token_error=self.total_tokens()-self.initial_tokens-self.minted+self.burned,ledger_error=self.ledger.sum()-self.initial_pending-self.issued-self.deposited+self.license_spent+self.gross_retired)
        assert abs(err['ETH_error'])<1e-5 and abs(err['token_error'])<.03 and abs(err['ledger_error'])<1e-5,err
        assert min(self.cash.min(),self.tokens.min(),self.ledger.min(),self.vault)>=-1e-5
        assert np.all((self.n>=0)&(self.n<=self.max_branches)) and np.all(self.used<=self.max_per) and self.sold<=self.quota
        self.errors.append(err)

    def record(self):
        self.path.append(dict(hours=self.h,elapsed_days=self.h/24,timestamp_utc=utc(self.pin+self.h*3600),price_ETH=self.pool.price,price_return=self.pool.price/self.start_price-1,wallet_tokens=self.tokens.sum(),wallet_cash_ETH=self.cash.sum(),branches=int(self.n.sum()),bank_pending=self.ledger.sum(),vault_ETH=self.vault,hook_ETH=self.hook,epoch_flow_ETH=self.epoch_flow,**self.flow))

    def run(self):
        for step in range(int(round(self.c.hours/self.c.dt_hours))):
            self.flow={};self.h=step*self.c.dt_hours;before=self.pool.price
            self.W=self.rolling_withdrawals(self.h)
            self.license_price()
            if self.c.wallet_first:self.wallet_decisions()
            if step%max(1,round(self.c.owner_review_hours/self.c.dt_hours))==0:self.game_decisions();self.prefund_game()
            if not self.c.wallet_first:self.wallet_decisions()
            self.protocol()
            if self.n.sum()>0:
                issue=self.issuance*self.c.dt_hours/24;self.ledger+=issue*self.n/self.n.sum();self.issued+=issue
            realized=np.log(self.pool.price/before)/(self.c.dt_hours/24);alpha=1-np.exp(-self.c.dt_hours/2);self.momentum=(1-alpha)*self.momentum+alpha*realized
            self.h=(step+1)*self.c.dt_hours;self.check();self.record()
        return pd.DataFrame(self.path).fillna(0),pd.DataFrame(self.events),pd.DataFrame(self.errors)

def scenarios(hours=24):
    return [Config(hours=hours),Config(name='Stabilization; patient buyers',hours=hours,prior_growth_day=.02,momentum_weight=0,reversion_share=.65),Config(name='Speculative recovery',hours=hours,prior_growth_day=.15,momentum_weight=.1,new_capital_multiplier=2,buyer_activity_multiplier=1.5),Config(name='Replacement selling accelerates',hours=hours,prior_growth_day=-.15,seller_activation_multiplier=2,new_capital_multiplier=.5),Config(name='Owner executes buybacks',hours=hours,execute_buybacks=True),Config(name='Crowded bank-exit expectations',hours=hours,prior_growth_day=-.3,seller_activation_multiplier=1.5,expected_future_withdrawals_day=700000),Config(name='No branch expansion',hours=hours,allow_expansion=False),Config(name='No new outside capital',hours=hours,new_capital_multiplier=0)]

def simulate_job(args):
    case,c,seed,root=args;economy=Economy(c,1000+seed,root);p,e,a=economy.run();end=p.iloc[-1];peak=p.iloc[p.price_ETH.argmax()]
    if len(e):
        e['elapsed_days']=e.hour/24;e['timestamp_utc']=[utc(economy.pin+h*3600) for h in e.hour]
    summary=dict(case=c.name,seed=seed,ending_price_return=end.price_return,peak_return=peak.price_return,hindsight_peak_hours=peak.hours,hindsight_peak_utc=peak.timestamp_utc,branches_end=end.branches,licenses=economy.total_flow['licenses'],retired=economy.total_flow['branches_retired'],license_fresh_ETH=economy.total_flow['license_fresh_buy_ETH'],game_prefund_ETH=economy.total_flow['game_prefund_ETH'],spec_buy_ETH=economy.total_flow['spec_buy_ETH']+economy.total_flow['owner_spec_buy_ETH'],spec_sell_ETH=economy.total_flow['spec_sell_ETH']+economy.total_flow['owner_spec_sell_ETH'],buyback_ETH=economy.total_flow['buyback_ETH'],branch_sell_ETH=economy.total_flow['branch_withdraw_sell_ETH'],new_capital_ETH=economy.new_cash)
    return case,seed,p,e,a,summary,dict(case=c.name,seed=seed,**economy.total_flow)

def run(root=ROOT,paths=4,hours=24,workers=3):
    from concurrent.futures import ProcessPoolExecutor
    out=root/'behavior-results';summaries=[];allflows=[];allerrors=[];allpaths=[]
    jobs=[(case,c,seed,root) for case,c in enumerate(scenarios(hours)) for seed in range(paths)]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for case,seed,p,e,a,summary,flow in executor.map(simulate_job,jobs):
            summaries.append(summary);allflows.append(flow);a['case']=summary['case'];a['seed']=seed;allerrors.append(a)
            if seed==0:p.to_csv(out/f'case-{case+1}-path.csv',index=False);e.to_csv(out/f'case-{case+1}-events.csv',index=False)
            p['case']=summary['case'];p['seed']=seed;allpaths.append(p)
            print('Completed',summary['case'],'seed',seed,flush=True)
    pd.DataFrame(summaries).to_csv(out/'scenario-runs.csv',index=False);pd.DataFrame(allflows).fillna(0).to_csv(out/'scenario-flows.csv',index=False);pd.concat(allerrors).to_csv(out/'accounting.csv.gz',index=False)
    pd.concat(allpaths).fillna(0).to_csv(out/'scenario-paths.csv.gz',index=False)
    meta=dict(paths_per_case=paths,hours=hours,scenarios=[asdict(c) for c in scenarios(hours)],interpretation='Within-case dispersion comes from assumed decision clocks and heterogeneous beliefs. No probabilities are assigned across cases; quantiles are not calibrated market confidence intervals. Peak times are hindsight path statistics, not ex-ante optimal sales. POL remains idle; ETH Charter auctions remain disabled; external funding of another owner conveys no modeled right. TWAP failure and owner non-execution remain real limits on buyback cases.')
    (out/'model-metadata.json').write_text(json.dumps(meta,indent=2)+'\n');return pd.DataFrame(summaries)

if __name__=='__main__':run()
