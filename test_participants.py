"""Independent public-evidence checks for participant attribution and decisions."""
import unittest
from collections import defaultdict
import numpy as np
import pandas as pd
from participant_flows import ROOT,read,load,ZERO,POOL,KINDS,transferred
from participant_decisions import inputs,funding_allocation,resolution_fee

class ParticipantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=ROOT/'participant-results';cls.target,cls.transfers,cls.events=load()
        cls.w,cls.c,cls.t,cls.s,cls.stamp,cls.pool=inputs()
    def test_integer_replay_matches_every_read_balance_and_supply(self):
        balances=defaultdict(int)
        for x in self.transfers:
            d=x['decoded'];q=int(d['value']);balances[d['from'].lower()]-=q;balances[d['to'].lower()]+=q
        balances.pop(ZERO,None)
        self.assertTrue(all(x>=0 for x in balances.values()))
        self.assertEqual(sum(balances.values()),int(self.s['token.totalSupply']))
        for row in read(ROOT/'strategy-current/wallet-balances.json'):
            if row['label'].endswith('.token'):self.assertEqual(balances[row['label'][:-6]],int(row['value']))
    def test_attributed_token_and_eth_legs_match_swaps(self):
        raw=defaultdict(lambda:np.zeros(2))
        for e in self.events:
            if e['event']=='Swap':raw[e['transactionHash']]+=np.array([abs(int(e['decoded']['amount1'])),abs(int(e['decoded']['amount0']))],dtype=float)/1e18
        for tx,x in self.t.groupby('tx'):
            np.testing.assert_allclose([x.tokens.sum(),x.pool_eth.sum()],raw[tx],rtol=1e-12,atol=1e-7)
    def test_pool_totals_include_transactions_without_token_transfers(self):
        m=read(self.out/'metadata.json')
        for side in ['buy','sell']:
            value=sum(abs(int(e['decoded']['amount0']))/1e18 for e in self.events if e['event']=='Swap' and ('buy' if int(e['decoded']['amount1'])>0 else 'sell')==side)
            self.assertAlmostEqual(value,m['all_pool_eth'][side],places=7)
    def test_sale_provenance_conserves_tokens(self):
        sold=self.t[self.t.side=='sell']
        np.testing.assert_allclose(sold[KINDS].sum(axis=1),sold.tokens,rtol=1e-11,atol=1e-6)
        self.assertGreaterEqual(sold[KINDS].min().min(),-1e-8)
        np.testing.assert_allclose(self.w[['inventory_'+k for k in KINDS]].sum(axis=1),self.w.wallet_tokens,rtol=1e-10,atol=1e-6)
    def test_transfer_lineage_reclassifies_without_destroying_inventory(self):
        x=np.arange(1,10,dtype=float);y=transferred(x)
        self.assertEqual(y.sum(),x.sum());self.assertEqual(y[0],0);self.assertEqual(y[1],3)
        self.assertEqual(y[3],7);self.assertEqual(y[5],11)
    def test_charter_balances_and_ownership_reconcile(self):
        self.assertEqual(self.c.branches.sum(),int(self.s['bank.totalBranches']))
        self.assertAlmostEqual(self.c.pending_tokens.sum(),int(self.s['bank.totalPendingLive'])/1e18,places=6)
        self.assertEqual(self.c.owner.nunique(),int(self.w[self.w.charter_count>0].shape[0]))
        deposits=pd.read_csv(self.out/'bank-deposits.csv')
        self.assertTrue(deposits.owner_deposit.all())
    def test_license_allocation_uses_each_owner_budget_once(self):
        a=pd.read_csv(self.out/'next-auction-feasible-allocation.csv')
        self.assertEqual(len(a),100);self.assertLessEqual(a.groupby('charter_id').size().max(),3)
        holdings=self.w.set_index('address').wallet_tokens
        for owner,q in a.groupby('owner').wallet_used.sum().items():self.assertLessEqual(q,holdings[owner]+1e-6)
        self.assertLess(a.new_tokens_needed.sum(),1e-6)
        np.testing.assert_allclose(a.ledger_used+a.wallet_used+a.new_tokens_needed,a.price_tokens,atol=1e-7)
    def test_observed_auction_prices_choose_gap_half_life(self):
        details=read(ROOT/'strategy-current/details.json')
        heads={int(x['response']['result']['number'],16):int(x['response']['result']['timestamp'],16) for x in details if x['request']['method']=='eth_getBlockByNumber'}
        checked=0
        for e in self.events:
            if e['event']!='LicensesPurchased' or int(e['blockNumber'],16) not in heads:continue
            secs=heads[int(e['blockNumber'],16)]-int(self.s['license.auctionAnchor'])
            expected=1400+10600*2**(-secs/14400)
            self.assertAlmostEqual(int(e['decoded']['unitPrice'])/1e18,expected,places=7);checked+=1
        self.assertGreaterEqual(checked,4)
    def test_conditioned_paths_conserve_assets_and_finite_inventories(self):
        x=pd.read_csv(self.out/'conditional-paths.csv')
        self.assertLess(x.ETH_error.abs().max(),1e-6);self.assertLess(x.token_error.abs().max(),.001)
        for col in ['remaining_recent_seller_tokens','remaining_dormant_tokens','remaining_repeat_cash_budget']:self.assertGreaterEqual(x[col].min(),-1e-6)
        for _,p in x.groupby('scenario'):
            self.assertEqual(len(p),7)
            self.assertTrue(pd.to_datetime(p.timestamp_utc,utc=True).equals(pd.to_datetime(self.stamp+p.hour*3600,unit='s',utc=True)))
    def test_followup_deposit_and_license_lineage_conserves_tokens(self):
        dep=pd.read_csv(self.out/'followup-deposits.csv')
        np.testing.assert_allclose(dep[['pre_snapshot_wallet_inventory','new_canonical_acquisition','new_other_custody_or_mint']].sum(axis=1),dep.tokens,atol=1e-6)
        paid=pd.read_csv(self.out/'followup-license-funding.csv')
        np.testing.assert_allclose(paid[['prior_bank_balance','new_issuance','prefunded_wallet_tokens','new_canonical_tokens','new_other_custody_tokens']].sum(axis=1),paid.cost_tokens,atol=1e-6)
        f=read(self.out/'followup-summary.json')
        self.assertLess(abs(f['ledger_reconciliation_error_tokens']),1e-5)
        self.assertEqual(f['total_branches'],int(self.s['bank.totalBranches'])+f['new_licenses'])
    def test_followup_does_not_rewrite_initial_calibration(self):
        f=read(self.out/'followup-summary.json');m=read(self.out/'metadata.json')
        self.assertGreater(f['block'],m['block'])
        self.assertEqual(f['from_snapshot_utc'],m['snapshot_utc'])
    def test_resolution_cost_rises_with_gross_exit_pressure(self):
        self.assertLess(resolution_fee(1000,0,1e6),resolution_fee(1000,500000,1e6))
        self.assertEqual(resolution_fee(1e6,0,1e6),.6)

if __name__=='__main__':unittest.main()
