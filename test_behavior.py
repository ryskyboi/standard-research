"""Accounting and decision regressions; synthetic mutations are offline only."""
import copy
import unittest
import numpy as np
import pandas as pd
from behavior_model import Economy,Config
from participant_flows import ROOT,read

class BehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.base=Economy(Config(hours=1),123)
    def setUp(self):self.e=copy.deepcopy(self.base)

    def test_market_round_trip_conserves_assets_and_pays_fees(self):
        e=self.e;a=int(np.argmax(e.cash));start=e.cash[a]
        e.cash[a]-=1;got=e.buy(1,'test_buy');e.tokens[a]+=got;e.check()
        cash,filled=e.sell(got,'test_sell');e.tokens[a]-=filled;e.cash[a]+=cash;e.check()
        self.assertLess(e.cash[a],start);self.assertGreater(e.hook,self.base.hook)
        self.assertEqual(e.new_cash,0)

    def test_internal_license_spend_does_not_create_market_buy(self):
        e=self.e;e.c.allow_retirement=False;e.c.prefund_enabled=False;e.c.waiting_enabled=False
        e.c.expected_new_branches_day=0;e.c.discount_day=0;e.bias[:]=0;e.revert[:]=False
        # Synthetic sufficient ledger at every Charter, with reconciled initial claim total.
        e.ledger[:]=e.license_price()*2;e.initial_pending=e.ledger.sum()
        e.game_decisions();e.check()
        self.assertGreater(e.total_flow['licenses'],0)
        self.assertEqual(e.total_flow['license_fresh_buy_ETH'],0)
        self.assertEqual(e.deposited,0)

    def test_full_retirement_available_when_waiting_has_no_value(self):
        e=self.e;e.c.allow_expansion=False;e.c.prefund_enabled=False
        e.base_issue=0;e.recycle_rate=0;e.bias[:]=-20;e.revert[:]=False
        initial=int(e.n.sum());e.game_decisions();e.check()
        self.assertGreater(e.total_flow['branches_retired'],0)
        self.assertLess(e.n.sum(),initial)
        self.assertGreater(e.minted,0)
        self.assertGreater(e.total_flow['branch_withdraw_sell_ETH'],0)

    def test_owner_cash_is_not_duplicated_per_charter(self):
        e=self.e;owners,counts=np.unique(e.owner,return_counts=True)
        self.assertGreater(counts.max(),1)
        self.assertEqual(len(e.address),len(set(e.address)))
        w=pd.read_csv(ROOT/'behavior-results/population.csv.gz')
        self.assertAlmostEqual(e.cash.sum(),w.native_ETH_budget.sum(),places=7)

    def test_daily_and_per_charter_limits_block_expansion(self):
        e=self.e;e.c.allow_retirement=False;e.sold=e.quota
        old=e.n.copy();e.game_decisions();np.testing.assert_array_equal(e.n,old)
        e.sold=0;e.used[:]=e.max_per;e.game_decisions();np.testing.assert_array_equal(e.n,old)

    def test_buyback_requires_explicit_execution_assumption(self):
        e=self.e;old=e.vault;e.protocol();self.assertEqual(e.vault,old)
        e.c.execute_buybacks=True;e.protocol();e.check()
        self.assertGreater(e.burned,0);self.assertLess(e.vault,old)
        spent=old-e.vault;e.protocol();self.assertAlmostEqual(old-e.vault,spent)

    def test_first_sale_activation_and_capital_are_separate(self):
        e=self.e;e.c.allow_game=False;e.c.new_capital_multiplier=0
        e.c.seller_activation_multiplier=1e7;e.activation_rate=1
        e.bias[:]=-20;e.revert[:]=False;cash_before=e.cash.sum()
        e.wallet_decisions();e.check()
        self.assertEqual(e.new_cash,0);self.assertGreater(e.total_flow['new_seller_activations'],0)
        self.assertGreater(e.cash.sum(),cash_before)

    def test_old_withdrawal_pressure_expires(self):
        e=self.e;self.assertGreater(e.rolling_withdrawals(0),0)
        self.assertEqual(e.rolling_withdrawals(8*24),0)

    def test_known_future_capital_bounds_subjective_price(self):
        e=self.e;e.bias[:]=20
        cap=1/e.pool.curve.sqrt_from_eth(e.pool.available_eth+(e.cash.sum()+e.external_rate*e.c.hours)*(1-e.pool.buy_tax)*(1-e.pool.lp_fee))**2
        self.assertLessEqual(e.expected_price(0,np.array([60]))[0],cap*(1+1e-12))

    def test_seed_reproduces_accounting_and_decisions(self):
        a=copy.deepcopy(self.e);b=copy.deepcopy(self.e)
        pa,ea,aa=a.run();pb,eb,ab=b.run()
        pd.testing.assert_frame_equal(pa,pb);pd.testing.assert_frame_equal(ea,eb)
        self.assertLess(aa.ETH_error.abs().max(),1e-5)

    def test_evidence_identity_and_exact_balance_reconciliation(self):
        t=read(ROOT/'behavior-evidence/target.json')
        self.assertEqual(t['chainId'],4663)
        self.assertEqual(t['token'].lower(),'0x88ad8ddf1e3898412146a534538d418c6f8a9062')
        self.assertTrue(t['allWalletTokenBalancesReconciled'])
        m=read(ROOT/'behavior-results/funding/followup-summary.json')
        self.assertAlmostEqual(m['ledger_reconciliation_error_tokens'],0,places=5)

if __name__=='__main__':unittest.main()
