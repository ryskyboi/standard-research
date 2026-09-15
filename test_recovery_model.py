import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/standard-research-mpl')
from dataclasses import replace
import unittest
import numpy as np
import recovery_model as r


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = r.load_evidence()

    def test_pinned_depth_matches_contract(self):
        pool = r.pool_for(self.e)
        expected = int(self.e['policy']['vault.poolEthDepth']) / 1e18
        self.assertAlmostEqual(r.depth(pool, self.e['protocol_positions']), expected, places=6)
        self.assertLess(pool.available_eth, pool.eth)

    def test_recovery_cost_reaches_target(self):
        for row in r.thresholds(self.e).to_dict('records'):
            pool = r.pool_for(self.e)
            pool.buy(row['wallet_buy_eth_no_sellers'])
            self.assertAlmostEqual(pool.price / row['target_price_eth'], 1, places=10)

    def test_unwithdrawn_issuance_does_not_move_price(self):
        path = r.simulate(self.e, r.Scenario(hours=24, buy_multiple=0, sell_multiple=0))
        self.assertTrue(np.allclose(path.price_ratio, 1))
        self.assertGreater(path.iloc[-1].pending, path.iloc[0].pending)

    def test_internal_licenses_do_not_create_market_buys(self):
        path = r.simulate(self.e, r.Scenario(hours=12, buy_multiple=0, sell_multiple=0,
            license_fill=1, license_external_fraction=0, license_tokens_each=1400))
        self.assertEqual(path.iloc[-1].licenses, 100)
        self.assertEqual(path.iloc[-1].license_buy_eth, 0)
        self.assertTrue(np.allclose(path.price_ratio, 1))

    def test_vault_is_finite_and_disabled_by_default(self):
        config = r.Scenario(buy_multiple=0, sell_multiple=0)
        off = r.simulate(self.e, config)
        on = r.simulate(self.e, replace(config, buybacks=True))
        self.assertEqual(off.iloc[-1].buyback_eth, 0)
        self.assertGreater(on.iloc[-1].buyback_eth, 0)
        self.assertLess(on.iloc[-1].buyback_eth, on.iloc[0].vault_eth)
        self.assertGreaterEqual(on.vault_eth.min(), 0)

    def test_extreme_sales_cannot_create_tokens(self):
        path = r.simulate(self.e, r.Scenario(sell_multiple=100))
        self.assertGreater(path.iloc[-1].unsold_requested_tokens, 0)
        self.assertGreaterEqual(path.outside_pool_token_bound.min(), 100000 - .001)

    def test_all_scenarios_conserve_pool_assets(self):
        for c in r.default_scenarios():
            path = r.simulate(self.e, c)
            self.assertLess(path.eth_error.abs().max(), 1e-6)
            self.assertLess(path.token_error.abs().max(), .02)
            self.assertGreaterEqual(path.pending.min(), 0)

    def test_flow_extrapolation_not_double_counting(self):
        w = self.e['summary']['windows'][:2]
        expected = sum(x['buysETH'] for x in w) / (sum(x['durationSeconds'] for x in w) / 3600)
        self.assertAlmostEqual(self.e['buy_wallet_eth_hour'] * .98, expected)

    def test_unknown_epoch_policy_is_not_silently_extrapolated(self):
        with self.assertRaisesRegex(ValueError, 'epoch boundary'):
            r.simulate(self.e, r.Scenario(hours=72))

    def test_time_step_and_execution_order_sensitivity(self):
        c = r.Scenario(sell_half_life_hours=6)
        base = r.simulate(self.e, c).iloc[-1].price
        fine = r.simulate(self.e, replace(c, dt=.05)).iloc[-1].price
        reversed_order = r.simulate(self.e, replace(c, sell_first=True)).iloc[-1].price
        self.assertLess(abs(fine / base - 1), .01)
        self.assertLess(abs(reversed_order / base - 1), .01)


if __name__ == '__main__': unittest.main()
