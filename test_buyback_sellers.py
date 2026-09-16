import unittest
import pandas as pd
from participant_flows import ROOT,read

class BuybackSellerTests(unittest.TestCase):
    def test_inventory_windows_are_overlapping_subsets(self):
        x=pd.read_csv(ROOT/'buyback-seller-results/seller-windows.csv')
        self.assertTrue((x.remaining_tokens.diff().dropna()>=0).all())
        self.assertTrue((x.empty_addresses<=x.selling_addresses).all())
        m=read(ROOT/'buyback-seller-results/summary.json')
        self.assertAlmostEqual(m['recent_seller_inventory']+m['other_holder_inventory'],m['holder_side_tokens'])

    def test_token_replay_reconciled_to_fresh_supply(self):
        m=read(ROOT/'buyback-seller-results/summary.json')
        self.assertTrue(m['integer_total_supply_reconciled'])
        self.assertTrue(m['known_custody_balances_reconciled'])
        self.assertLess(m['new_delta_unattributed_ETH']/m['new_delta_canonical_ETH'],.01)

    def test_buyback_only_spot_profit_is_not_investor_profit(self):
        x=pd.read_csv(ROOT/'buyback-seller-results/buyback-vs-sellers.csv')
        no_sellers=x[x.fraction_recent_seller_inventory_sold==0]
        self.assertTrue((no_sellers.spot_return_before_investor_exit>0).all())
        self.assertTrue((no_sellers.investor_net_return<0).all())
        self.assertTrue((x.buyback_ETH<111.719).all())

    def test_more_sellers_require_more_external_buying(self):
        x=pd.read_csv(ROOT/'buyback-seller-results/break-even-external-buying.csv')
        for _,g in x.groupby('hours'):
            self.assertTrue((g.sort_values('fraction_recent_seller_inventory_sold').extra_external_buyer_ETH.diff().dropna()>0).all())

if __name__=='__main__':unittest.main()
