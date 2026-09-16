import unittest
from pathlib import Path
import pandas as pd
from participant_flows import ROOT,read
from seller_monitor import inventory_bridge

class MonitorTests(unittest.TestCase):
    def test_transfers_inside_fixed_cohort_do_not_deplete_it(self):
        def log(a,b,n,block=12):return dict(blockNumber=hex(block),decoded={'from':a,'to':b,'value':str(n*10**18)})
        rows=[log('a','b',10),log('a','c',3),log('c','b',2),log('a','c',100,9)]
        self.assertEqual(inventory_bridge(rows,{'a','b'},10),(2.,3.))

    def test_frozen_cohort_inventory_bridge(self):
        latest=read(ROOT/'seller-monitor/latest.json');m=read(ROOT/latest['snapshot']/'analysis/summary.json')
        self.assertAlmostEqual(m['fixed_cohort_initial_tokens']+m['fixed_cohort_incoming_tokens']-m['fixed_cohort_outgoing_tokens'],m['fixed_cohort_remaining_tokens'],places=6)

    def test_remaining_inventory_source_and_entry_cohort_conservation(self):
        latest=read(ROOT/'seller-monitor/latest.json');out=ROOT/latest['snapshot']/'analysis';m=read(out/'summary.json')
        self.assertTrue(m['total_supply_reconciled']);self.assertTrue(m['source_inventory_reconciled'])
        self.assertAlmostEqual(sum(m['inventory_sources'].values()),m['recent_seller_inventory'],places=5)
        self.assertAlmostEqual(sum(x['remaining_tokens'] for x in m['entry_cohorts']),m['recent_seller_inventory'],places=6)
        df=pd.read_csv(out/'sellers.csv')
        # No numerical countdown when an address is not actively reducing holdings by trades.
        self.assertTrue(df.loc[df.net_sale_pace_tokens_hour_20m<=0,'constant_net_sale_pace_hours_to_empty'].isna().all())

if __name__=='__main__':unittest.main()
