"""Reproducible figures, findings and integrity manifest for participant research."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from participant_flows import ROOT,read


def table(df):
    def fmt(x):
        if isinstance(x,(float,np.floating)):return f'{x:,.3f}'
        return str(x)
    return '| '+' | '.join(df.columns)+' |\n|'+'|'.join(['---']*len(df.columns))+'|\n'+'\n'.join('| '+' | '.join(fmt(x) for x in row)+' |' for row in df.itertuples(index=False,name=None))

def build(root=ROOT):
    out=root/'participant-results';m=read(out/'metadata.json');d=read(out/'decision-metadata.json');f=read(out/'followup-summary.json')
    w=pd.read_csv(out/'wallets.csv.gz');co=pd.read_csv(out/'cohorts.csv');prov=pd.read_csv(out/'sell-provenance.csv');windows=pd.read_csv(out/'windows.csv');paths=pd.read_csv(out/'conditional-paths.csv');sc=pd.read_csv(out/'conditional-scenarios.csv');fund=pd.read_csv(out/'license-funding.csv');branch=pd.read_csv(out/'branch-hold-thresholds.csv')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    active=co[co.buy_eth_6h+co.sell_eth_6h>0];x=np.arange(len(active))
    axes[0].bar(x-.18,active.buy_eth_6h,.36,label='Buys',color='#168b79');axes[0].bar(x+.18,active.sell_eth_6h,.36,label='Sells',color='#cf563b');axes[0].set_xticks(x,active.cohort.str.replace('_','\n'));axes[0].set_ylabel('Canonical-pool ETH');axes[0].set_title('Who traded in the six hours before 00:44:57 UTC?');axes[0].legend()
    for name,g in paths.groupby('scenario'):axes[1].plot(g.hour,(g.price_ratio-1)*100,label=name.replace('_',' '),lw=2)
    axes[1].axhline(0,color='grey',lw=.7);axes[1].set_xlabel('Hours after Sep 16, 00:44:57 UTC (0–0.25 days)');axes[1].set_ylabel('Price change (%)');axes[1].set_title('Conditional six-hour paths; no probabilities');axes[1].legend(fontsize=8)
    fig.savefig(out/'participant-flows-and-paths.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    sources=['Prior bank balance','Issuance after snapshot','Prefunded wallet tokens','New canonical acquisition','Other post-snapshot custody']
    vals=[f['license_paid_from_'+k] for k in ['prior_bank_balance','new_issuance','prefunded_wallet_tokens','new_canonical_tokens','new_other_custody_tokens']]
    axes[0].barh(sources,np.array(vals)/1000,color=['#576b85','#576b85','#576b85','#168b79','#c4a44c']);axes[0].invert_yaxis();axes[0].set_xlabel('Thousands of tokens paid for licenses');axes[0].set_title(f"Actual funding of {f['new_licenses']} new licenses\nPro-rata ledger lineage; through {f['timestamp_utc'][11:19]} UTC")
    quiet=branch[branch.future_exit_pressure=='quiet'];axes[1].hist(quiet.one_day_max_price_fall*100,bins=25,color='#4776a6');axes[1].set_xlabel('One-day price fall offset by additional earnings (%)');axes[1].set_ylabel('Charters');axes[1].set_title('Current owners have very different exit incentives\nQuiet resolution fees; 100 added branches/day assumed')
    fig.savefig(out/'branch-funding-and-incentives.png');plt.close(fig)
    poolmarket=prov[(prov.window_hours==6)&prov.source.isin(['own_pool_buy','transferred_pool_buy','own_other_pool_buy','transferred_other_pool_buy'])].share_of_attributed_sold_tokens.sum()
    oldshare=(f['license_paid_from_prior_bank_balance']+f['license_paid_from_prefunded_wallet_tokens'])/f['license_cost_tokens']
    depold=f['deposit_existing_wallet_tokens']/f['bank_deposit_tokens']
    top=w.nlargest(8,'sell_pool_eth_6h')[['address','sell_pool_eth_6h','wallet_tokens','charter_count']].rename(columns={'sell_pool_eth_6h':'6h sell ETH','wallet_tokens':'Tokens left','charter_count':'Charters'})
    buyers=w.nlargest(6,'buy_pool_eth_6h')[['address','buy_pool_eth_6h','wallet_tokens','native_eth','charter_count']].rename(columns={'buy_pool_eth_6h':'6h buy ETH','wallet_tokens':'Tokens held','native_eth':'Native ETH held','charter_count':'Charters'})
    qs=sc[['scenario','end_price_ratio','actual_buy_ETH','actual_sell_tokens']].copy();qs['end_price_ratio']=(qs.end_price_ratio-1)*100;qs.columns=['Conditional scenario','6h change %','Buyer ETH spent','Tokens sold']
    initial=read(root/'strategy-current/target.json');follow=read(root/'strategy-current/followup.json.gz')
    remaining=f['remaining_licenses'];current_price=int(next(x['value'] for x in follow['state'] if x['label']=='currentPrice'))/1e18
    new_share=(f['license_paid_from_new_canonical_tokens']+f['license_paid_from_new_other_custody_tokens'])/f['license_cost_tokens']
    indicative=remaining*current_price*new_share*f['last_swap_price_ETH']/.98/.99
    text=f'''# STANDARD: who is trading, where tokens came from, and what branch buyers actually did

**Participant snapshot:** {m['snapshot_utc']} · block {m['block']:,}.

**Latest auction observation:** {f['timestamp_utc']} · block {f['block']:,}.

Robinhood chain 4663 · STANDARD `0x88ad8DdF1E3898412146a534538d418c6F8A9062`.

[Executed notebook](participant_analysis.ipynb) · [All participant tables](participant-results/) · [Pinned RPC evidence](strategy-current/) · [Reproduction and limitations](PARTICIPANT_METHOD.md)

## Findings

**This was primarily a market-inventory selloff, followed by an auction-period rebound that quickly weakened. It was not an observed bank run.** There was one branch withdrawal in the entire pre-snapshot history and **{f['new_withdrawals']} new withdrawals** in the follow-up. A Charter owner selling wallet tokens is not necessarily retiring a branch.

- In the six hours before the snapshot, the canonical pool processed **{windows.query("window_hours==6 and side=='buy'").all_pool_eth.iloc[0]:,.1f} ETH of buys and {windows.query("window_hours==6 and side=='sell'").all_pool_eth.iloc[0]:,.1f} ETH of sells**. We attribute **{windows.query("window_hours==6 and side=='buy'").attribution_fraction.iloc[0]:.2%} of buying and {windows.query("window_hours==6 and side=='sell'").attribution_fraction.iloc[0]:.2%} of selling** to token source/recipient addresses.
- **{poolmarket:.1%} of attributed sold tokens** trace to purchases on the canonical or two verified secondary pools, directly or through transfers. The rest remain other-custody/unresolved acquisition sources. Pro-rata lineage is an accounting convention; fungible tokens have no unique identity.
- **{d['recent_sellers_zero_balance']} of {d['recent_selling_addresses']} recent selling addresses were empty** at the snapshot. The group had **{d['recent_seller_remaining_tokens']/1e6:.3f} million tokens left**. Constantly extrapolating its earlier sale rate ignores inventory exhaustion.
- The inactive/unattributed cohort held **{d['inactive_inventory_tokens']/1e6:.2f} million tokens**. That is potential inventory, not an assumption that all those owners will sell. New sellers, rather than endlessly repeating exhausted sellers, are the main continuation risk.
- **{f['new_licenses']} licenses actually sold** after the reset, costing **{f['license_cost_tokens']/1e6:.3f} million tokens**, and total branches reached **{f['total_branches']:,}**. Expansion demand exists. Bank deposits were **{f['bank_deposit_tokens']/1e6:.3f} million tokens**; **{depold:.1%}** came from inventory already in wallets at the snapshot.
- Estimated actual license-payment sources were **{oldshare:.1%} prior bank balance or prefunded wallet inventory**, plus new issuance and post-snapshot acquisitions. Only **{f['license_paid_from_new_canonical_tokens']:,.0f} tokens** of license payments trace to new canonical-pool acquisitions after the snapshot.
- During the follow-up, license-buying addresses made **{f['buy_bought_license_in_window_ETH']:.1f} ETH of canonical buys** out of **{f['canonical_buy_ETH']:.1f} ETH total**. They also sold **{f['sell_bought_license_in_window_ETH']:.1f} ETH**. All Charter owners together bought **{f['buy_charter_owner_ETH']:.1f} ETH**. Wallet category establishes ownership/activity, not motive.

## The auction did not guarantee a sustained rally

At **01:09:32 UTC**, 50 licenses had sold, net canonical flow since 00:44:57 was **+111.5 ETH**, and price was **+6.4%**. By **{f['timestamp_utc'][11:19]} UTC**, only one more license had sold; renewed selling reduced cumulative net flow to **+{f['canonical_net_ETH']:.1f} ETH** and the price gain to **{f['price_change_since_snapshot']:.1%}**. These are observed checkpoints, not a successful model prediction or proof that licenses caused every purchase.

There were **{remaining} licenses left**. At the latest auction price, repeating the observed post-snapshot acquisition share would correspond to roughly **{indicative:.1f} ETH** of additional token buying for those licenses at the observed token price, before further price movement and route-specific costs. That is a conditional benchmark: different owners may use all old inventory or need much more new capital. A token burn is not the same quantity as an ETH market buy.

**Evidence-based assessment:** a tradable bounce has already occurred, but this evidence does not establish a renewed upward trend or a most-likely all-time top. Continued weakness requires additional holders choosing to exit; sustained recovery requires buyers absorbing that replacement selling after the auction burst. The immediately observed pattern is a fragile rebound, not automatic extinction of buy demand.

## Who sold?

Canonical-pool portions only, six hours ending 00:44:57 UTC. Addresses may be contracts or smart accounts; they are not identified people.

{table(top)}

The largest seller, `0x14b33822c8bc5689e4130b0d3fca676674fb6718`, previously acquired **988,797.54 tokens in attributed canonical purchases**. It sold **675,935.82** in four trades, each taking **25% of the then-remaining balance**, and retained **312,861.72**. Its attributed pool-side acquisition cost was **139.71 ETH**; the sold fraction had a weighted pool-side cost of **95.50 ETH**, versus **79.46 ETH gross pool proceeds**. Those figures exclude route costs, launch taxes and gas, so they are not a complete realized-P&L statement. They do not support calling this profit-taking at an exceptionally cheap basis.

[Transaction-level trades and sale provenance](participant-results/trades.csv.gz) retain full hashes, exact blocks, matched transaction senders where checked, route allocation and timestamp precision. A transaction's bundler/router sender is not substituted for the token-owning account.

## Who bought?

{table(buyers)}

Native ETH is only one funding asset. Wrapped ETH, stablecoins, new transfers, borrowing and cross-chain capital are not comprehensively measured. Missing ETH readings for older fully exited addresses remain missing. Zero native ETH does not prove inability to buy. Common funding and token transfers do not establish common beneficial ownership.

## Charter and branch decisions

At the participant snapshot, **{d['current_charters']} Charters belonged to {d['charter_owners']} addresses**, with **{d['branches']} branches**, **{d['bank_pending_tokens']/1e6:.3f} million tokens pending internally**, and **{d['charter_wallet_tokens']/1e6:.3f} million tokens in owner wallets**. Shared owner inventory is counted once across all its Charters.

A feasible allocation could fund all next-day 100 licenses using existing balances and wallet tokens with **zero compulsory new pool buying**. This is a feasibility result, not an optimal allocation or an expectation that those exact owners buy. Actual owner choices above show some new buying and substantial use of old inventory.

For the median existing Charter, another day of issuance can offset roughly **{branch.query("future_exit_pressure=='quiet'").one_day_max_price_fall.median():.1%}** of price decline in the one-day comparison, assuming quiet withdrawal fees and 100 added branches/day. A heavily prefunded Charter has much less percentage growth in its bank balance, so its exit incentive is different. Future mass withdrawals can raise resolution fees and reverse that comparison. The full owner-by-owner thresholds are in [branch-hold-thresholds.csv](participant-results/branch-hold-thresholds.csv).

At the next opening price, one additional branch cost about **{d['next_license_open_tokens']/(700000/d['branches']):.1f} days of its initial gross issuance share**, before dilution, withdrawal fees and price changes. Our 14-day full-retirement calculation is deliberately a **horizon sensitivity**, not a complete explanation of observed license buying: it omits the ongoing branch's terminal option value and partial-retirement paths. The actual 51 purchases show why those omissions/longer horizons matter. It is not valid to declare all buyers irrational or set future license demand to zero from that truncated calculation.

Ownership-history replay matches every live Charter. **All 158 pre-snapshot deposits came from the then-owner**, including the Charter later burned. No third-party funding strategy was observed in those deposits. Sending tokens to someone else's Charter creates no automatic payout right for the sender; a private agreement is outside the on-chain payoff model.

## Conditional flow paths

These six-hour **pre-auction snapshot stress paths** use actual remaining inventories, measured new-buyer activity, replacement-seller activity and native-ETH spending ceilings. They are not probabilities or a solved equilibrium. They exclude new bank withdrawals, license-specific incremental purchases and automatic vault execution. They must not be represented as a forecast incorporating the later auction outcome.

{table(qs)}

The central sensitivity replaces retiring sellers at the observed first-sale volume. “Renewed entry” sustains the stronger last-two-hour arrival rate. “Seller exhaustion” assumes no replacement sellers. Buyer spending stops above an explicitly assumed reservation value. The observed later auction/rebound is shown separately; we do not backfill it into the earlier calibration or claim the paths predicted it.

![Participant activity and conditional paths](participant-results/participant-flows-and-paths.png)

![Branch funding and incentives](participant-results/branch-funding-and-incentives.png)

## Liquidity, taxes and audit limits

The frozen curve contains **{d['pool_ETH_principal']:,.2f} ETH of actual principal** and every initialized tick. Locked protocol liquidity is kept safe in the model, as requested. Swaps can still extract ETH. Quoted trades include the **1% LP fee, 2% buy tax and 3% sell tax**; branch exits separately pay the resolution fee. Optional router fees and gas are not assumed to disappear from actual execution but are not included in these protocol-only scenario quotes.

Observed auction sales exactly match **halving the gap to the floor every four hours**. The whitepaper's displayed geometric-to-floor equation disagrees with its prose and those sales; this model uses the measured behavior. [Official whitepaper](https://www.standardreserve.xyz/whitepaper/).

We replayed **{m['transfer_logs']:,} token transfers**, **{m['canonical_swaps']:,} canonical swaps**, 1,001 Charter ownership transfers and secondary-pool acquisition records. Token supply reconciles with integer arithmetic; every collected wallet token balance matches pinned state. The later bank ledger also reconciles. Remaining limits: route ambiguity, approximate times between exact headers, fungible-token attribution convention, unmeasured external capital, address/person ambiguity, future policy and liquidity changes, and unobserved beliefs. These limit claims about a uniquely rational action or calibrated likelihood.
'''
    (root/'PARTICIPANTS.md').write_text(text)
    files=[]
    for directory in ['strategy-evidence','strategy-current','empirical-evidence']:
        files.extend(p for p in (root/directory).rglob('*') if p.is_file())
    sources=['participant_flows.py','participant_decisions.py','participant_followup.py','participant_publication.py','liquidity.py','test_participants.py','build_participant_notebook.py']
    manifest={'snapshot_block':m['block'],'snapshot_hash':m['block_hash'],'followup_block':f['block'],'followup_hash':f['block_hash'],'evidence_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return text
if __name__=='__main__':build()
