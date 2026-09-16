import unittest
import numpy as np
import pandas as pd
from participant_flows import ROOT,read

class SellerOriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=ROOT/'seller-origin-results';cls.s=read(cls.d/'summary.json')

    def test_exact_inventory_bridge(self):
        s=self.s
        self.assertAlmostEqual(s['initial_fixed_tokens']+s['gross_external_incoming']-s['gross_external_outgoing'],s['remaining_fixed_tokens'],places=6)
        self.assertTrue(s['all_token_balances_reconciled'] and s['total_supply_reconciled'])

    def test_every_incoming_token_is_allocated_once(self):
        r=pd.read_csv(self.d/'incoming-economic-sources.csv.gz');i=pd.read_csv(self.d/'incoming-transfers.csv')
        a=r.groupby(['tx','recipient']).tokens.sum();b=i.groupby(['tx','recipient']).tokens.sum()
        self.assertEqual(set(a.index),set(b.index))
        self.assertTrue(np.allclose(a.sort_index(),b.sort_index(),rtol=0,atol=1e-7))
        self.assertAlmostEqual(r.tokens.sum(),self.s['gross_external_incoming'],places=6)

    def test_relay_does_not_replace_underlying_pool_sources(self):
        r=pd.read_csv(self.d/'incoming-economic-sources.csv.gz');g=r[r.tx=='0xf79546cce3882ce33bd77f569955387fd435f2da62c7cd48a8797b57db8833a1'].groupby('source').tokens.sum()
        self.assertAlmostEqual(g['canonical_swap_output'],10999.11684802309,places=6)
        self.assertAlmostEqual(g['verified_secondary_swap_output'],2000.6631825680347,places=6)
        self.assertAlmostEqual(g['other_custody_output'],7003.664907517414,places=6)
        self.assertNotIn('outside_wallet_inventory',g)

    def test_recent_seller_membership_is_not_fixed_inventory(self):
        m={r['membership']:r for r in self.s['cohort_membership']}
        expected=self.s['remaining_fixed_tokens']-m['aged_out_of_rolling_group']['current_tokens']+m['newly_in_rolling_group']['current_tokens']
        self.assertAlmostEqual(expected,self.s['rolling_inventory'],places=6)

    def test_rebuy_and_complete_sale_match_for_example(self):
        w=pd.read_csv(self.d/'replenished-wallets.csv').set_index('address');a=w.loc['0x4ff25ae1b4bf1cee786d5458b43f116d3203d374']
        self.assertEqual(a.initial_tokens,0);self.assertEqual(a.current_tokens,0)
        self.assertAlmostEqual(a.bought_canonical_tokens,a.sold_canonical_tokens,places=6)

    def test_origin_totals_and_no_invented_branch_source(self):
        s=self.s
        self.assertAlmostEqual(sum(s['sale_origins'].values()),s['attributed_sold_tokens'],places=6)
        self.assertAlmostEqual(sum(s['inventory_origins'].values()),s['rolling_inventory'],places=6)
        self.assertEqual(s['sale_origins']['branch_withdrawal']+s['sale_origins']['transferred_branch_withdrawal'],0)

    def test_example_receipts_and_headers_match_saved_transfer_edges(self):
        e=read(ROOT/'seller-origin-evidence/checks.json');g=pd.read_csv(self.d/'interval-transfer-graph.csv.gz')
        self.assertEqual(e['chainId'],4663);self.assertEqual(len(e['receipts']),7)
        for r in e['receipts']:
            self.assertEqual(r['receipt']['status'],'0x1')
            self.assertEqual(r['receipt']['blockHash'],r['header']['hash'])
            self.assertIn(r['receipt']['transactionHash'],set(g.tx))

if __name__=='__main__':unittest.main()
