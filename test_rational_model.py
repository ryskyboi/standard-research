import unittest
import numpy as np
import rational_model as r

class RationalEconomicsTests(unittest.TestCase):
    def test_tax_schedule_and_override_bounds(self):
        tax=r.legacy.read('home.json')['snapshot']['tax'];start=int(tax['taxDecayStart'])
        np.testing.assert_allclose(r.trading_taxes(start,tax),[.9,.9])
        np.testing.assert_allclose(r.trading_taxes(start+240,tax),[.46,.465])
        np.testing.assert_allclose(r.trading_taxes(start+3600,tax),[.02,.03])
        np.testing.assert_allclose(r.trading_taxes(start+3600,tax,.1,.08),[.1,.08])
        with self.assertRaises(ValueError):r.Config(buy_tax_override=.11)

    def test_flat_price_no_profitable_speculative_roundtrip(self):
        c=r.Config(days=.25,prior_growth_day=0,belief_dispersion_day=0,momentum_weight=0,discount_day=0,
            allow_internal=False,allow_external=False,allow_retirement=False,prefund_days=0,banker_token_fraction=0)
        out=r.simulate(c)
        self.assertEqual(out['totals']['spec_buy_eth'],0)
        self.assertEqual(out['totals']['spec_sell_eth'],0)
        np.testing.assert_allclose(out['frame'].price,out['frame'].price.iloc[0])
        np.testing.assert_allclose(out['frame'].hour,np.arange(7))

    def test_external_license_spends_inventory_then_cash_and_burns_tokens(self):
        e=r.Economy(r.Config(license_daily_cap=1,allow_internal=False))
        i=int(np.flatnonzero((e.n==1)&(~e.protected))[0]);e.used[:]=3;e.used[i]=0;e.license_sold=0
        before=(e.cash[i],e.inventory[i],e.total_eth(),e.total_tokens(),e.n[i],e.pending)
        cost=2000.;e.buy_licenses(cost)
        self.assertEqual(e.n[i],before[4]+1)
        self.assertAlmostEqual(e.inventory[i],0,places=7)
        self.assertLess(e.cash[i],before[0])
        self.assertAlmostEqual(e.total_tokens(),before[3]-cost,places=6)
        self.assertAlmostEqual(e.total_eth(),before[2],places=8)
        self.assertAlmostEqual(e.pending,before[5],places=7)
        self.assertEqual(e.flow['licenses_external'],1)
        self.assertGreater(e.flow['license_tokens_fresh'],0)
        self.assertGreater(e.flow['license_tokens_inventory'],0)
        e.check()

    def test_internal_license_is_not_fresh_ETH_or_physical_token_burn(self):
        e=r.Economy(r.Config(license_daily_cap=1,allow_external=False))
        i=int(np.flatnonzero((e.n<10)&(e.balance>100)&(~e.protected))[0]);e.used[:]=3;e.used[i]=0;e.license_sold=0
        before=(e.pending,e.total_eth(),e.total_tokens(),e.n[i])
        e.buy_licenses(100)
        self.assertEqual(e.n[i],before[3]+1)
        self.assertAlmostEqual(e.pending,before[0]-100,places=7)
        self.assertAlmostEqual(e.total_tokens(),before[2],places=7)
        self.assertAlmostEqual(e.total_eth(),before[1],places=8)
        self.assertEqual(e.flow['license_buy_eth'],0)
        self.assertEqual(e.flow['licenses_internal'],1)
        e.check()

    def test_partial_exit_fee_includes_own_gross_and_preserves_remaining_claim(self):
        e=r.Economy(r.Config());i=int(np.flatnonzero(e.n==4)[0])
        before_balance=e.balance[i];before_n=e.total_branches;pending=e.pending;w=e.withdrawn
        gross=before_balance/4;expected=float(r.resolution_fee(gross,pending,w))
        e.retire(i,1)
        self.assertEqual(e.n[i],3);self.assertEqual(e.total_branches,before_n-1)
        self.assertAlmostEqual(e.balance[i],before_balance*.75,places=8)
        self.assertAlmostEqual(e.events[-1]['resolution_fee'],expected,places=12)
        e.retire(i,3)
        self.assertEqual(e.n[i],0);self.assertEqual(e.balance[i],0)
        ext,internal,_=e.license_surpluses(1,[i],ignore_daily=True)
        self.assertTrue(np.isneginf(ext[0]) and np.isneginf(internal[0]))
        e.check()

    def test_congestion_fee_matches_pinned_preview(self):
        state={x['label']:x.get('value') for x in r.legacy.read('state.json')['values']}
        s=r.legacy.snapshot()
        for q in [0,1000,100000,1000000]:
            self.assertAlmostEqual(float(r.resolution_fee(q,s['pending'],s['withdrawn'])),int(state[f'exitFee.{q}'])/1e18,places=12)

    def test_optimism_cannot_forecast_unfunded_pool_ETH(self):
        e=r.Economy(r.Config(banker_cash_eth=0,speculator_cash_eth=0,prospective_charter_cash_eth=0))
        prices=e.expected_prices([10.],np.array([1.,7.,30.]))
        self.assertTrue(np.all(prices<=e.pool.price*(1+1e-12)))

    def test_no_new_charters_or_cash_licenses_without_budget(self):
        c=r.Config(days=1.5,banker_cash_eth=0,speculator_cash_eth=0,prospective_charter_cash_eth=0,
            banker_token_fraction=0,allow_internal=False,allow_retirement=False,charter_open_hour=1)
        out=r.simulate(c)
        self.assertEqual(out['totals']['charters_created'],0)
        self.assertEqual(out['totals']['licenses_bought'],0)
        self.assertTrue((out['frame'].branches==out['frame'].branches.iloc[0]).all())

    def test_actual_caps_and_cash_conservation_with_charters_and_protocol_execution(self):
        c=r.Config(days=3,charter_open_hour=24,charter_daily_cap=4,execute_buybacks=True,execute_pol=True,fresh_capital_eth_day=100)
        e=r.Economy(c);out=e.run();f=out['frame'];events=out['events']
        self.assertLess(f.eth_accounting_error.abs().max(),1e-5)
        self.assertLess(f.token_accounting_error.abs().max(),.02)
        self.assertLess(f.ledger_accounting_error.abs().max(),1e-5)
        np.testing.assert_allclose(f.eth_principal.diff().iloc[1:],(f.pool_buy_eth-f.pool_sell_eth_gross+f.pol_added_eth).iloc[1:],atol=1e-7)
        self.assertTrue((f.protected_branch_count==1).all())
        self.assertTrue((e.n<=10).all());self.assertTrue((e.used<=3).all())
        self.assertTrue(all(x<=3 for x in e.daily_purchase_counts.values()))
        licenses=events[events.event=='license'].copy()
        if len(licenses):
            licenses['day']=((e.s['timestamp']+licenses.hour*3600-e.s['auction_anchor'])//86400).astype(int)
            self.assertTrue((licenses.groupby('day')['count'].sum()<=100).all())
        self.assertGreater(out['totals']['charters_created'],0)
        self.assertGreater(out['totals']['charter_eth'],0)
        self.assertGreater(out['totals']['pol_buy_eth'],0)
        self.assertAlmostEqual(e.fresh_added,300,places=7)
        self.assertTrue((f.remaining_slots==f.charters*10-f.branches).all())

if __name__=='__main__':unittest.main()
