"""Checks of the frozen update, its temporal split and scenario conservation."""
import unittest
import pandas as pd
import numpy as np
from participant_flows import ROOT,read

PACKET=ROOT/'behavior-updates/2026-09-16T054047Z'

class BehaviorUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=PACKET/'results';cls.s=read(cls.d/'update-summary.json')
        cls.t=read(PACKET/'evidence/target.json')

    def test_identity_and_replay(self):
        self.assertEqual(self.t['chainId'],4663)
        self.assertEqual(self.t['token'].lower(),'0x88ad8ddf1e3898412146a534538d418c6f8a9062')
        self.assertTrue(self.t['allWalletTokenBalancesReconciled'])
        self.assertEqual(self.t['header']['hash'],self.s['block_hash'])

    def test_funding_rebased_to_previous_snapshot(self):
        f=read(self.d/'interval-funding/followup-summary.json')
        self.assertEqual(f['from_snapshot_utc'],self.s['previous_snapshot_utc'])
        self.assertEqual(f['new_licenses'],46)
        sources=sum(v for k,v in f.items() if k.startswith('license_paid_from_'))
        self.assertAlmostEqual(sources,f['license_cost_tokens'],places=6)
        self.assertLess(abs(f['ledger_reconciliation_error_tokens']),1e-5)

    def test_fixed_group_accounts_for_replenishment(self):
        s=self.s
        self.assertAlmostEqual(s['previous_seller_group_current_tokens'],s['previous_seller_group_initial_tokens']+s['previous_seller_group_inflows']-s['previous_seller_group_outflows'],places=6)
        self.assertGreater(s['previous_seller_group_inflows'],0)
        self.assertGreater(s['six_hour_seller_remaining_tokens'],s['previous_seller_group_current_tokens'])

    def test_unattributed_volume_not_silently_zero(self):
        s=self.s
        self.assertLessEqual(s['attributed_buy_ETH'],s['buy_ETH']+1e-9)
        self.assertLessEqual(s['attributed_sell_ETH'],s['sell_ETH']+1e-9)
        self.assertGreaterEqual(s['latest20m_all_pool_sell_ETH'],s['latest20m_sell_ETH'])

    def test_same_assumptions_new_inputs(self):
        old=read(ROOT/'behavior-results/model-metadata.json');new=read(self.d/'model-metadata.json')
        self.assertEqual(new['scenarios'],old['scenarios'])
        paths=pd.read_csv(self.d/'scenario-paths.csv.gz')
        self.assertEqual(len(paths),32*97)
        self.assertTrue(np.isfinite(paths.select_dtypes('number')).all().all())
        for _,g in paths.groupby(['case','seed']):
            self.assertAlmostEqual(g.price_ETH.iloc[0],self.s['price_ETH'])
            self.assertEqual(pd.Timestamp(g.timestamp_utc.iloc[-1])-pd.Timestamp(g.timestamp_utc.iloc[0]),pd.Timedelta(days=1))

    def test_no_model_license_sale_before_reset(self):
        reset=(pd.Timestamp(self.s['next_license_reset_utc'])-pd.Timestamp(self.s['snapshot_utc'])).total_seconds()/3600
        for file in self.d.glob('case-*-events.csv'):
            g=pd.read_csv(file);licenses=g[g.event=='license']
            self.assertTrue((licenses.hour>=reset-1e-8).all())

    def test_asset_conservation(self):
        d=pd.read_csv(self.d/'accounting.csv.gz')
        self.assertLess(d.ETH_error.abs().max(),1e-5)
        self.assertLess(d.token_error.abs().max(),.03)
        self.assertLess(d.ledger_error.abs().max(),1e-5)

    def test_old_paths_are_checked_at_correct_elapsed_time(self):
        d=pd.read_csv(self.d/'previous-path-check.csv')
        self.assertEqual(len(d),32)
        self.assertTrue(np.allclose(d.hours,self.s['elapsed_hours']))
        self.assertTrue(np.allclose(d.observed_return,self.s['price_change_since_previous']))

    def test_buyback_spot_lift_is_not_round_trip_profit(self):
        d=pd.read_csv(self.d/'buyback-only-trade.csv')
        self.assertTrue((d.spot_change>0).all())
        self.assertTrue((d.one_ETH_entry_net_return<0).all())

    def test_final_check_keeps_its_own_timestamp_and_scope(self):
        t=read(PACKET/'tail-check.json')
        self.assertEqual(t['chainId'],4663)
        self.assertEqual(t['from_header']['hash'],self.t['header']['hash'])
        self.assertGreater(int(t['header']['number'],16),int(self.t['header']['number'],16))
        q=next(x['value'][0] for x in t['state'] if x['label']=='slot0')
        self.assertAlmostEqual(t['price_ETH'],2**192/int(q)**2)

if __name__=='__main__':unittest.main()
