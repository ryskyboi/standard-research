import json
import unittest
from pathlib import Path
import numpy as np
from liquidity import ConcentratedPool, LiquidityCurve
import model as m

ROOT=Path(__file__).resolve().parent
PROFILE=json.loads((ROOT/'notebook-evidence/liquidity-ticks.json').read_text())

def synthetic():
    # Two disjoint ranges deliberately force a zero-liquidity gap crossing.
    return dict(sqrtPriceX96=str(int(1.0001**500*2**96)),ticks=[
        dict(tick=0,liquidityNet=str(1000*10**18)),
        dict(tick=2000,liquidityNet=str(-1000*10**18)),
        dict(tick=4000,liquidityNet=str(2000*10**18)),
        dict(tick=6000,liquidityNet=str(-2000*10**18))])

class LiquidityTests(unittest.TestCase):
    def test_principal_reconciles_independent_positions(self):
        evidence=json.loads((ROOT/'notebook-evidence/liquidity-positions.json').read_text())
        pool=ConcentratedPool(PROFILE)
        self.assertAlmostEqual(pool.available_eth,evidence['totalEthPrincipal'],places=8)
        self.assertAlmostEqual(pool.real_tokens,evidence['totalTokenPrincipal'],places=6)
        # Replayed positions reconstruct every liquidity-net tick, not just totals.
        net={}
        for p in evidence['positions']:
            for tick,sign in [(p['tickLower'],1),(p['tickUpper'],-1)]:
                net[tick]=net.get(tick,0)+sign*int(p['liquidity'])
        for t in PROFILE['ticks']:self.assertEqual(net[t['tick']],int(t['liquidityNet']))

    def test_buy_sell_reversal_across_ticks_and_gap(self):
        p=ConcentratedPool(synthetic(),0,0,0)
        start=p.sqrt; available=p.available_eth
        out,_,filled=p.sell(100)
        self.assertEqual(filled,100)
        self.assertGreater(p.sqrt,1.0001**2000)
        bought,_=p.buy(out)
        self.assertAlmostEqual(bought,100,places=9)
        self.assertAlmostEqual(p.sqrt,start,places=12)
        self.assertAlmostEqual(p.available_eth,available,places=10)

    def test_finite_ranges_stop_and_return_partial_fill(self):
        p=ConcentratedPool(synthetic(),0,0,0);available=p.available_eth
        out,_,filled=p.sell(1e8)
        self.assertLess(filled,1e8)
        self.assertAlmostEqual(out,available,places=10)
        self.assertAlmostEqual(p.available_eth,0,places=10)
        self.assertAlmostEqual(p.sell(100)[0],0,places=10)

    def test_quotes_and_roundtrip_with_fees(self):
        for q in [100,100_000,1_000_000,10_000_000]:
            p=ConcentratedPool(PROFILE);quote=p.quote_buy(q)
            tokens,_=p.buy(quote)
            self.assertAlmostEqual(tokens/q,1,places=9)
            cash,_,_=p.sell(tokens)
            self.assertLess(cash,quote)
            self.assertLess(p.sqrt,int(PROFILE['sqrtPriceX96'])/2**96)  # sell-side LP fee stays outside principal

    def test_historical_swaps_match_recorded_price_and_output(self):
        logs=json.loads((ROOT/'notebook-evidence/recent-swaps.json').read_text())['logs']
        logs.sort(key=lambda x:(int(x['blockNumber'],16),int(x['logIndex'],16)))
        for before,trade in zip(logs[-6:-1],logs[-5:]):
            p=ConcentratedPool(PROFILE);p.sqrt=int(before['decoded']['sqrtPriceX96'])/2**96
            a=trade['decoded'];eth=int(a['amount0'])/1e18;token=int(a['amount1'])/1e18
            if eth<0:out=p.buy(-eth,exempt=True)[0];expected=token
            else:out=p.sell(-token)[0]/(1-p.sell_tax);expected=eth
            self.assertAlmostEqual(out,expected,places=7)
            self.assertAlmostEqual(p.sqrt/(int(a['sqrtPriceX96'])/2**96),1,places=12)

    def test_vectorized_exit_matches_independent_pool_trades(self):
        curve=LiquidityCurve(PROFILE)
        prices=np.geomspace(.05,3,50)
        sqrts=curve.initial_sqrt/np.sqrt(prices)
        quotes=curve.sell_quotes(sqrts,1_000_000)
        for s,q in zip(sqrts,quotes):
            pool=ConcentratedPool(PROFILE);pool.sqrt=s
            self.assertAlmostEqual(pool.sell(1_000_000)[0],q,places=8)

    def test_model_preserves_protected_branches_with_exact_liquidity(self):
        old=m.EVIDENCE
        try:
            m.EVIDENCE=ROOT/'notebook-evidence';state=m.snapshot()
            scenario=m.Scenario('stress',200,6,.3,.3,1.,60,coordinated_exit_hour=12)
            path=m.simulate(state,scenario,55,days=3,protected_branches=10)
            self.assertTrue(np.isfinite(path).all());self.assertTrue((path[:,8]>=10).all())
            self.assertTrue((path[:,3]>=0).all())
            quote=m.liquidate(path,path[:,11],liquidity_profile=PROFILE)
            self.assertTrue((quote>=0).all());self.assertTrue((quote<=path[:,3]).all())
        finally:m.EVIDENCE=old

if __name__=='__main__':unittest.main()
