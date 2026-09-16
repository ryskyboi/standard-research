"""Accounting and decision constraints for the fresh re-entry scenarios."""
import copy,unittest
import numpy as np
import pandas as pd
from participant_flows import ROOT,read
from reentry_model import allocate,price_buy_cost,buyback,branch_payback
from liquidity import ConcentratedPool

class ReentryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile=read(ROOT/'reentry-evidence/liquidity.json')
        cls.pool=ConcentratedPool(cls.profile)

    def test_target_reached_after_inventory_sale(self):
        p=copy.deepcopy(self.pool);p.sell(3e6);target=self.pool.price*1.25
        cost=price_buy_cost(p,target);p.buy(cost)
        self.assertAlmostEqual(p.price/target,1,places=10)

    def test_shared_wallet_not_reused_and_daily_cap_respected(self):
        c=pd.DataFrame([dict(charter_id=1,owner='a',branches=8,pending_tokens=0.),dict(charter_id=2,owner='a',branches=1,pending_tokens=0.)])
        w=pd.DataFrame([dict(address='a',wallet_tokens=15.)])
        a=allocate(c,w,10.,6,{1:2,2:0})
        self.assertEqual(len(a),4)
        self.assertEqual((a.charter_id==1).sum(),1)
        self.assertEqual(a.wallet_used.sum(),15)
        self.assertEqual(a.new_tokens_needed.sum(),25)

    def test_zero_mandatory_buy_allocation_accounts_for_all_tokens(self):
        a=pd.read_csv(ROOT/'reentry-results/remaining-license-allocation.csv')
        m=read(ROOT/'reentry-results/summary.json')
        self.assertEqual(len(a),m['remaining_licenses'])
        self.assertAlmostEqual(a.new_tokens_needed.sum(),0)
        self.assertAlmostEqual(a.ledger_used.sum()+a.wallet_used.sum(),m['remaining_licenses']*m['license_price_tokens'],places=6)

    def test_buyback_cannot_spend_entire_vault_in_first_tick(self):
        p=copy.deepcopy(self.pool)
        spent=buyback(p,111.7,3296.,p.price,1)
        self.assertAlmostEqual(spent,6.592)
        p=copy.deepcopy(self.pool)
        self.assertLess(buyback(p,111.7,3296.,p.price,48),111.7)

    def test_dilution_delays_payback(self):
        flat=branch_payback(21000,1152,700000,0,9990)
        mid=branch_payback(21000,1152,700000,50,9990)
        fast=branch_payback(21000,1152,700000,100,9990)
        self.assertAlmostEqual(flat,21000*1152/700000)
        self.assertLess(flat,mid);self.assertLess(mid,fast)

    def test_branch_and_funding_ledger_reconcile(self):
        m=read(ROOT/'reentry-results/summary.json');f=read(ROOT/'reentry-results/funding/followup-summary.json')
        self.assertTrue(m['pending_sum_reconciled'])
        self.assertLess(abs(f['ledger_reconciliation_error_tokens']),1e-5)
        self.assertAlmostEqual(sum(v for k,v in f.items() if k.startswith('license_paid_from_')),f['license_cost_tokens'],places=6)

    def test_public_execution_failure_distinct_from_owner(self):
        checks=read(ROOT/'reentry-evidence/buyback-execution.json')['checks']
        self.assertEqual(checks[0]['decoded']['errorName'],'NotExecutor')
        self.assertIn('result',checks[1]['result'])
        self.assertFalse(any(e['event']=='BuybackExecuted' for e in read(ROOT/'reentry-evidence/vault-events.json')))

    def test_all_cases_respect_finite_inventory(self):
        m=read(ROOT/'reentry-results/summary.json');df=pd.read_csv(ROOT/'reentry-results/six-hour-cases.csv')
        expected=df.active_inventory_fraction_sold*m['recent_seller_inventory']+df.dormant_inventory_fraction_sold*m['inactive_inventory']
        np.testing.assert_allclose(expected,df.tokens_sold)
        self.assertTrue((df.tokens_sold<=m['recent_seller_inventory']+m['inactive_inventory']).all())

    def test_hook_balance_has_exact_fee_provenance(self):
        f=read(ROOT/'reentry-results/fee-reconciliation.json')
        self.assertEqual(int(f['trading_tax_wei'])+int(f['lp_eth_tax_wei'])-int(f['forwarded_wei']),int(f['observed_balance_wei']))
        self.assertEqual(f['unexplained_difference_wei'],'0')

if __name__=='__main__':unittest.main()
