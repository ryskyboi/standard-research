import unittest
import numpy as np
import pandas as pd
from participant_flows import ROOT,read
from analyze_trade_tape import runs,actor_for,POOL

class TradeTapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=pd.read_csv(ROOT/'tape-results/transactions.csv.gz').fillna('')

    def test_transactions_are_unique_and_amounts_reconcile(self):
        f=self.f;s=read(ROOT/'tape-results/summary.json')
        self.assertEqual(f.tx.nunique(),len(f))
        self.assertAlmostEqual(f.buy_eth.sum()+f.sell_eth.sum(),s['gross_eth'])
        fresh=read(ROOT/'tape-evidence/tape.json');g=f[f.block>int(fresh['from_header']['number'],16)]
        self.assertAlmostEqual(g.buy_eth.sum(),fresh['buy_ETH'])
        self.assertAlmostEqual(g.sell_eth.sum(),fresh['sell_ETH'])

    def test_runs_partition_all_included_transactions(self):
        for threshold in [0,.1,1]:
            r=runs(self.f,threshold);g=self.f[self.f.gross_eth>=threshold]
            self.assertEqual(r.transactions.sum(),len(g))
            self.assertAlmostEqual(r.eth.sum(),g.gross_eth.sum())

    def test_router_net_zero_is_not_an_actor(self):
        es=[{'event':'Swap','decoded':{'amount1':'100'}}]
        ts=[{'decoded':{'from':POOL,'to':'router','value':'100'}},
            {'decoded':{'from':'router','to':'buyer','value':'100'}}]
        self.assertEqual(actor_for(es,ts,{POOL}),'buyer')
        es.append({'event':'ModifyLiquidity'})
        self.assertEqual(actor_for(es,ts,{POOL}),'')

    def test_synchronized_fraction_matches_pretrade_inventory(self):
        g=pd.read_csv(ROOT/'tape-results/synchronized-sells.csv')
        expected=np.where(g.block==64214560,.03,.05)
        self.assertTrue(np.allclose(g.tokens/g.wallet_tokens_before,expected,atol=1e-14,rtol=0))
        self.assertEqual(g.actor.nunique(),20)
        self.assertTrue(g.exact_header.all())

    def test_collected_transaction_envelopes_match_saved_logs(self):
        fresh=read(ROOT/'tape-evidence/tape.json')
        old=read(ROOT/'behavior-updates/2026-09-16T054047Z/evidence/delta-events.json.gz')
        hashes={e['transactionHash']:e['blockHash'] for e in old+fresh['events']}
        for x in read(ROOT/'tape-evidence/details.json'):
            if x['request']['method']=='eth_getTransactionByHash':
                t=x['response']['result'];self.assertEqual(t['blockHash'],hashes[t['hash']])

if __name__=='__main__':unittest.main()
