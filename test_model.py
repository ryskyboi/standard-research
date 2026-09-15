import math
import unittest
import numpy as np
import model as m
from model import Pool, fee, snapshot, observed_flows, Scenario, simulate, strategies


class EconomicsTests(unittest.TestCase):
    def setUp(self):
        self.original_evidence=m.EVIDENCE
        m.EVIDENCE=m.ROOT/'evidence'  # older frozen regression fixture

    def tearDown(self):
        m.EVIDENCE=self.original_evidence

    def test_fee_includes_own_exit_and_matches_chain(self):
        s=snapshot()
        self.assertAlmostEqual(fee(0,s['pending'],s['withdrawn']),.020084525840868683,places=14)
        self.assertAlmostEqual(fee(100000,s['pending'],s['withdrawn']),.027284882762568811,places=14)
        self.assertEqual(fee(1_000_000,s['pending'],s['withdrawn']),.6)

    def test_round_trip_loses_to_fees_and_preserves_curve(self):
        p=Pool(100,10000,100)
        k=p.eth*p.token
        tokens,_=p.buy(10)
        cash,_,_=p.sell(tokens)
        self.assertLess(cash,10)
        self.assertAlmostEqual(p.eth*p.token,k,places=6)
        self.assertAlmostEqual(p.eth,p.available_eth,places=8)

    def test_finite_sell_has_impact(self):
        p=Pool(100,10000,100)
        self.assertLess(p.quote_sell(1000),1000*p.price*.99*.97)
        self.assertAlmostEqual(p.quote_sell(1000),100*.99*1000/(10000+.99*1000)*.97)

    def test_virtual_eth_not_available_for_exit(self):
        p=Pool(100,10000,2)
        cash,_,filled=p.sell(100000)
        self.assertAlmostEqual(cash,1.94)
        self.assertLess(filled,100000)
        self.assertAlmostEqual(p.available_eth,0)
        self.assertAlmostEqual(p.eth,98)

    def test_no_fee_flat_curve_trade_reversal(self):
        p=Pool(100,10000,100,0,0,0)
        tokens,_=p.buy(20)
        cash,_,_=p.sell(tokens)
        self.assertAlmostEqual(cash,20)
        self.assertAlmostEqual(p.eth,100)
        self.assertAlmostEqual(p.token,10000)

    def test_branch_stopping_time_analytic(self):
        # Check against a brute-force, independently constructed terminal cash curve.
        initial,earnings,decline=230.,636.,math.log(2)
        times=np.linspace(0,5,100001)
        proceeds=(initial+earnings*times)*np.exp(-decline*times)
        exact=1/decline-initial/earnings
        self.assertAlmostEqual(times[np.argmax(proceeds)],exact,places=4)

    def test_v4_direction_and_recent_reversal(self):
        f=observed_flows(snapshot())
        self.assertLess(f['full']['net_pool_eth_hour'],0)
        self.assertGreater(f['last_bin']['net_pool_eth_hour'],0)
        self.assertEqual(sum(x['count'] for x in f['bins']),1131)

    def test_flat_market_branch_harvest_increases(self):
        s=snapshot();s['float_tokens']=0;s['pending']=0;s['withdrawn']=0
        scenario=Scenario('flat',0,24,0,0,0,0)
        path=simulate(s,scenario,1,days=1)
        values=strategies(path,s)
        np.testing.assert_allclose(path[:,4],path[0,4])
        self.assertTrue(np.all(np.diff(values['own_one_branch'])>0))
        self.assertAlmostEqual(path[-1,5],700000/1099,places=8)

    def test_repeatable_and_nonnegative(self):
        s=snapshot();scenario=Scenario('stress',10,3,.8,.3,1,20)
        a=simulate(s,scenario,45,days=3);b=simulate(s,scenario,45,days=3)
        np.testing.assert_array_equal(a,b)
        self.assertTrue(np.all(a[:,1:]>=0))

    def test_waiting_owner_survives_crowd_exit(self):
        s=snapshot();scenario=Scenario('everyone_leaves',0,24,0,50,0,0)
        a=simulate(s,scenario,45,days=3,protected_branches=10)
        self.assertTrue(np.all(a[:,8]>=10))
        self.assertTrue(np.all(a[:,6]>=a[:,11]-1e-7))
        self.assertGreater(a[-1,11],a[0,11])

    def test_internal_reinvestment_spends_earnings_and_opens_branch(self):
        s=snapshot();scenario=Scenario('flat',0,24,0,0,0,0)
        a=simulate(s,scenario,45,days=4,expansion_cost=1273,internal_expansion=True)
        i=int(np.flatnonzero(a[:,13])[0])
        self.assertEqual(a[i,8]-a[i-1,8],1)
        self.assertLess(a[i,11],a[i-1,11])
        self.assertEqual(a[i,12],0)

    def test_external_expansion_pays_and_changes_market(self):
        s=snapshot();scenario=Scenario('flat',0,24,0,0,0,0)
        a=simulate(s,scenario,45,days=2,expansion_cost=1273)
        self.assertGreater(a[-1,12],0)
        self.assertEqual(a[-1,8],s['branches']+1)
        self.assertGreater(a[-1,4],a[0,4])

    def test_reject_invalid_behavior(self):
        with self.assertRaises(ValueError):Scenario('bad',1,0,.1,.1,.1,100)

    def test_our_wallet_tokens_are_not_also_sold_by_crowd(self):
        s=snapshot();scenario=Scenario('sell',0,24,1,0,0,0)
        a=simulate(s,scenario,1,days=1,protected_branches=0,owned_wallet_tokens=s['float_tokens'])
        np.testing.assert_allclose(a[:,4],a[0,4])

    def test_documented_epoch_policy_requires_two_positive_signals(self):
        s=snapshot();scenario=Scenario('inflow',1,96,0,0,0,0)
        a=simulate(s,scenario,1,days=7)
        self.assertEqual(a[96,9],1.)
        self.assertAlmostEqual(a[-1,9],1.1)


if __name__=='__main__':
    unittest.main()
