"""Offline, floating-point v4 principal curve with initialized tick crossings.

ETH is currency0, STANDARD currency1. Fees accrue outside principal. This is
scenario arithmetic, not an integer-exact router quote or transaction builder.
"""
import numpy as np
from bisect import bisect_right, bisect_left


class LiquidityCurve:
    def __init__(self, profile):
        rows=sorted(profile['ticks'],key=lambda x:x['tick'])
        self.bounds=np.array([1.0001**(x['tick']/2) for x in rows])
        # Accumulate as integers first: full-range tails must not inherit float dust.
        running=0; active=[]
        for row in rows:
            running+=int(row['liquidityNet']); active.append(running/1e18)
        if running!=0 or min(active)<0: raise ValueError('Unbalanced tick liquidity')
        self.L=np.array(active[:-1])
        self.a=self.bounds[:-1]; self.b=self.bounds[1:]
        self.x=np.r_[0.,np.cumsum(self.L*(self.b-self.a))]
        self.y=np.r_[np.cumsum((self.L*(1/self.a-1/self.b))[::-1])[::-1],0.]
        self._bounds=self.bounds.tolist(); self._x=self.x.tolist(); self._yr=self.y[::-1].tolist()
        self.initial_sqrt=int(profile['sqrtPriceX96'])/2**96

    def index(self,s):
        if np.isscalar(s): return min(max(bisect_right(self._bounds,s)-1,0),len(self.L)-1)
        return np.clip(np.searchsorted(self.bounds,s,side='right')-1,0,len(self.L)-1)

    def inventories(self,s):
        if np.isscalar(s):
            s=min(max(s,self._bounds[0]),self._bounds[-1]); i=self.index(s)
            return (self.x[i]+self.L[i]*(s-self.a[i]),self.y[i+1]+self.L[i]*(1/s-1/self.b[i]))
        s=np.clip(s,self.bounds[0],self.bounds[-1]); i=self.index(s)
        return (self.x[i]+self.L[i]*(s-self.a[i]),
                self.y[i+1]+self.L[i]*(1/s-1/self.b[i]))

    def sqrt_from_tokens(self,x):
        if np.isscalar(x):
            x=min(max(x,0),self._x[-1]); i=min(max(bisect_right(self._x,x)-1,0),len(self.L)-1)
            return self.a[i]+((x-self.x[i])/self.L[i] if self.L[i]>0 else 0)
        x=np.clip(x,0,self.x[-1])
        i=np.clip(np.searchsorted(self.x,x,side='right')-1,0,len(self.L)-1)
        return self.a[i]+np.divide(x-self.x[i],self.L[i],out=np.zeros_like(np.asarray(x,dtype=float)),where=self.L[i]>0)

    def sqrt_from_eth(self,y):
        if np.isscalar(y):
            y=min(max(y,0),self._yr[-1]); i=min(max(len(self.L)-bisect_left(self._yr,y),0),len(self.L)-1)
            return 1/(1/self.b[i]+((y-self.y[i+1])/self.L[i] if self.L[i]>0 else 0))
        y=np.clip(y,0,self.y[0])
        i=np.clip(len(self.L)-np.searchsorted(self.y[::-1],y,side='left'),0,len(self.L)-1)
        delta=np.divide(y-self.y[i+1],self.L[i],out=np.zeros_like(np.asarray(y,dtype=float)),where=self.L[i]>0)
        return 1/(1/self.b[i]+delta)

    def sell_quotes(self,s,quantity,scale=1.,lp_fee=.01,sell_tax=.03):
        x,y=self.inventories(s)
        q=np.maximum(quantity,0)*(1-lp_fee)/scale
        end=self.sqrt_from_tokens(x+q)
        _,remaining=self.inventories(end)
        return np.maximum(0,y-remaining)*scale*(1-sell_tax)


class ConcentratedPool:
    def __init__(self,profile,lp_fee=.01,buy_tax=.02,sell_tax=.03):
        self.curve=LiquidityCurve(profile); self.sqrt=self.curve.initial_sqrt
        self.scale=1.; self.lp_fee=lp_fee; self.buy_tax=buy_tax; self.sell_tax=sell_tax

    @property
    def price(self): return 1/self.sqrt**2
    @property
    def eth(self): return self.curve.L[self.curve.index(self.sqrt)]*self.scale/self.sqrt
    @property
    def token(self): return self.curve.L[self.curve.index(self.sqrt)]*self.scale*self.sqrt
    @property
    def available_eth(self): return float(self.curve.inventories(self.sqrt)[1])*self.scale
    @property
    def real_tokens(self): return float(self.curve.inventories(self.sqrt)[0])*self.scale

    def quote_sell(self,quantity):
        return float(self.curve.sell_quotes(self.sqrt,quantity,self.scale,self.lp_fee,self.sell_tax))

    def sell(self,quantity):
        x,y=self.curve.inventories(self.sqrt)
        effective=min(max(0,quantity)*(1-self.lp_fee)/self.scale,self.curve.x[-1]-x)
        end=self.curve.sqrt_from_tokens(x+effective)
        _,remaining=self.curve.inventories(end)
        gross=max(0,float(y-remaining))*self.scale; self.sqrt=float(end)
        return gross*(1-self.sell_tax),gross*self.sell_tax,effective*self.scale/(1-self.lp_fee)

    def buy(self,eth,exempt=False):
        if not np.isfinite(eth) or eth<0: raise ValueError('Invalid buy amount')
        tax=0 if exempt else self.buy_tax
        x,y=self.curve.inventories(self.sqrt)
        end=self.curve.sqrt_from_eth(y+eth*(1-tax)*(1-self.lp_fee)/self.scale)
        tokens,_=self.curve.inventories(end); self.sqrt=float(end)
        return max(0,float(x-tokens))*self.scale,eth*tax

    def quote_buy(self,tokens):
        x,y=self.curve.inventories(self.sqrt)
        if tokens>=x*self.scale: return float('inf')
        end=self.curve.sqrt_from_tokens(x-max(0,tokens)/self.scale)
        _,new_y=self.curve.inventories(end)
        return max(0,float(new_y-y))*self.scale/(1-self.buy_tax)/(1-self.lp_fee)

    def add_proportional(self,eth,tokens):
        # Scenario-only future LP: scale every existing range in the same ratio.
        # Unmatched assets stay out of the curve (conservative idle dust).
        fraction=min(eth/max(self.available_eth,1e-30),tokens/max(self.real_tokens,1e-30))
        self.scale*=1+fraction
