"""Evidence-conditioned flow scenarios, not fitted probabilities or equilibrium.

Uses a fresh complete tick map. Future turnover, exhaustion and auction funding
are explicit assumptions. No networking, keys, signing or transaction submission.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
from liquidity import ConcentratedPool
from time_display import with_utc

ROOT = Path(__file__).resolve().parent
OBSERVATION = '2026-09-15T22-45-57.336Z'


def read(path):
    return json.loads(Path(path).read_text())


def load_evidence(root=ROOT, observation=OBSERVATION):
    folder = root / 'live-observations' / observation
    summary = read(folder / 'summary.json')
    state = {x['label']: x['value'] for x in summary['state']}
    auctions = {x['label']: x['value'] for x in read(folder / 'recovery-auctions.json')['state']}
    support = read(folder / 'support-state.json')
    policy = {x['label']: x['value'] for x in support['state']}
    profile = read(folder / 'recovery-liquidity.json')
    assert profile['blockHash'] == summary['blockHash']
    assert support['block'] == summary['block']
    assert int(state['token.decimals']) == 18
    windows = summary['windows'][:2]  # adjacent; do not double-count last five minutes
    hours = sum(w['durationSeconds'] for w in windows) / 3600
    pool = ConcentratedPool(profile)
    observed = sum(w['buysETH'] for w in windows) / hours
    stamp = pd.Timestamp(summary['blockUTC'])
    anchor = int(auctions['license.auctionAnchor'])
    next_reset = anchor + (math.floor((stamp.timestamp() - anchor) / 86400) + 1) * 86400
    reference = read(root / 'live-observations/2026-09-15T13-40-35.886Z/summary.json')
    old_state = {x['label']: x['value'] for x in read(root / 'notebook-evidence/state.json')['values']}
    return dict(folder=folder, summary=summary, profile=profile, state=state, auctions=auctions,
        policy=policy, support=support, timestamp=stamp, price=pool.price,
        # Event buy amount0 is AFTER hook tax, BEFORE input LP fee.
        buy_wallet_eth_hour=observed / (1 - int(state['currentBuyBps']) / 10000),
        sell_tokens_hour=sum(w['tokensSold'] for w in windows) / hours,
        buy_pool_eth_hour=observed,
        sell_pool_eth_hour=sum(w['sellsETH'] for w in windows) / hours,
        reset_hour=(next_reset - stamp.timestamp()) / 3600,
        protocol_positions=read(folder / 'recovery-protocol-positions.json')['positions'],
        references={'10% bounce': pool.price * 1.1, '25% bounce': pool.price * 1.25,
            'Reclaim 13:40 UTC reference': reference['windows'][1]['endPriceETH'],
            'Reclaim 10:09 UTC reference': (2**96 / int(old_state['getSlot0'][0]))**2})


@dataclass
class Scenario:
    name: str = 'Observed turnover persists'
    hours: float = 48
    dt: float = .25
    buy_multiple: float = 1
    sell_multiple: float = 1
    sell_half_life_hours: float | None = None
    buy_half_life_hours: float | None = None
    buybacks: bool = False
    license_fill: float = 0
    license_external_fraction: float = 0
    license_tokens_each: float = 11888.34092914804
    license_delay_hours: float = 0
    withdrawal_fraction: float = 0
    withdrawal_hour: float = 6
    sell_first: bool = False

    def __post_init__(self):
        if self.hours <= 0 or not 0 < self.dt <= 1:
            raise ValueError('Invalid horizon or time step')
        for x in [self.buy_multiple, self.sell_multiple, self.license_tokens_each, self.license_delay_hours]:
            if x < 0: raise ValueError('Negative flow assumption')
        for x in [self.license_fill, self.license_external_fraction, self.withdrawal_fraction]:
            if not 0 <= x <= 1: raise ValueError('Fraction outside [0, 1]')
        for x in [self.buy_half_life_hours, self.sell_half_life_hours]:
            if x is not None and x <= 0: raise ValueError('Invalid half life')


def integrated_rate(rate, start, end, half_life):
    if half_life is None: return rate * (end - start)
    decay = math.log(2) / half_life
    return rate / decay * (math.exp(-decay * start) - math.exp(-decay * end))


def pool_for(evidence):
    s = evidence['state']
    return ConcentratedPool(evidence['profile'], int(s['getSlot0'][3]) / 1e6,
        int(s['currentBuyBps']) / 10000, int(s['currentSellBps']) / 10000)


def depth(pool, positions):
    tick = math.log(pool.sqrt) * 2 / math.log(1.0001)
    liquidity = sum(int(p['liquidity']) / 1e18 for p in positions
        if p['tickLower'] <= tick < p['tickUpper'])
    return liquidity / pool.sqrt


def simulate(e, c):
    pool = pool_for(e)
    s = e['state']; p = e['policy']
    if e['timestamp'].timestamp() + c.hours * 3600 >= int(p['bank.epochEnd']):
        raise ValueError('Projection reaches an unsettled epoch boundary; refresh policy state first')
    vault = int(e['support']['balancesWei']['contractionVault']) / 1e18
    pending = int(s['bank.totalPendingLive']) / 1e18
    withdrawn = sum(int(x['value']) for x in e['summary']['withdrawalWindow']) / 1e18
    branches = int(s['bank.totalBranches'])
    issuance_hour = int(s['bank.baseIssuancePerDay']) * int(s['bank.multiplierWad']) / 1e36 / 24
    # Upper bound, not a reconstructed spendable wallet census.
    stock = int(s['token.totalSupply']) / 1e18 - pool.real_tokens
    tokens_lp = burned = minted = 0.
    totals = dict(total_buy_spend_eth=0., speculative_buy_eth=0., pool_buy_principal_eth=0., pool_sell_eth=0.,
        buyback_eth=0., license_buy_eth=0., licenses=0, gross_withdrawn=0.,
        net_withdrawn_tokens=0., unsold_requested_tokens=0., buy_tax_eth=0., lp_buy_eth=0.)
    initial_eth = pool.available_eth
    next_license = e['reset_hour'] + c.license_delay_hours
    next_buyback = 0.
    exit_done = False
    records = []

    def buy(amount, kind):
        nonlocal stock
        qty, tax = pool.buy(amount)
        stock += qty
        totals['total_buy_spend_eth'] += amount
        totals['pool_buy_principal_eth'] += amount * (1 - pool.buy_tax) * (1 - pool.lp_fee)
        totals['buy_tax_eth'] += tax
        totals['lp_buy_eth'] += amount * (1 - pool.buy_tax) * pool.lp_fee
        totals[kind or 'speculative_buy_eth'] += amount
        return qty

    def sell(q):
        nonlocal stock, tokens_lp
        # Keep the illustrative 100k wallet out of crowd sales, as in the agent model.
        allowed = min(max(stock - 100000, 0), q)
        totals['unsold_requested_tokens'] += q - allowed
        net, tax, used = pool.sell(allowed)
        stock -= used
        tokens_lp += used * pool.lp_fee
        totals['pool_sell_eth'] += net + tax

    def record(h):
        token_error = (pool.real_tokens + stock + tokens_lp + burned
                       - (int(s['token.totalSupply']) / 1e18 + minted))
        eth_error = pool.available_eth - initial_eth - totals['pool_buy_principal_eth'] + totals['pool_sell_eth']
        records.append(dict(hour=h, price=pool.price, price_ratio=pool.price / e['price'],
            pool_principal_eth=pool.available_eth, wallet_100k_exit_eth=pool.quote_sell(100000),
            vault_eth=vault, pending=pending, branches=branches, outside_pool_token_bound=stock,
            eth_error=eth_error, token_error=token_error, **totals))

    record(0)
    for start in np.arange(0, c.hours - 1e-9, c.dt):
        end = min(c.hours, start + c.dt)
        pending += issuance_hour * (end - start) if branches else 0
        buy_amount = integrated_rate(e['buy_wallet_eth_hour'] * c.buy_multiple, start, end, c.buy_half_life_hours)
        sell_amount = integrated_rate(e['sell_tokens_hour'] * c.sell_multiple, start, end, c.sell_half_life_hours)
        if c.sell_first: sell(sell_amount); buy(buy_amount, None)
        else: buy(buy_amount, None); sell(sell_amount)
        if c.buybacks and start >= next_buyback - 1e-9:
            amount = min(vault * int(p['vault.tickVaultPctBps']) / 10000,
                         depth(pool, e['protocol_positions']) * int(p['vault.effectiveTickPoolPctBps']) / 10000)
            qty = buy(amount, 'buyback_eth')
            vault -= amount
            # Contraction purchase-and-burn; these tokens never become crowd inventory.
            stock -= qty; burned += qty
            next_buyback = start + int(p['vault.tickCooldown']) / 3600
        if c.license_fill and end >= next_license:
            count = math.floor(int(e['auctions']['license.licensesPerDay']) * c.license_fill)
            count = min(count, 999 * 10 - branches)  # frozen-cohort capacity upper bound
            fresh_qty = count * c.license_tokens_each * c.license_external_fraction
            internal_qty = count * c.license_tokens_each * (1 - c.license_external_fraction)
            if internal_qty > pending:
                # Refuse to spend nonexistent ledger balances. Aggregate feasibility only.
                count = math.floor(pending / max(c.license_tokens_each * (1 - c.license_external_fraction), 1e-30))
                fresh_qty = count * c.license_tokens_each * c.license_external_fraction
                internal_qty = count * c.license_tokens_each * (1 - c.license_external_fraction)
            cost = pool.quote_buy(fresh_qty)
            obtained = buy(cost, 'license_buy_eth') if fresh_qty else 0
            stock -= obtained; burned += obtained
            pending -= internal_qty
            branches += count; totals['licenses'] += count
            next_license += 24
        if c.withdrawal_fraction and not exit_done and end >= c.withdrawal_hour:
            # Aggregate proportional retirement stress; no cohort optimization claimed.
            retired = math.floor(branches * c.withdrawal_fraction)
            gross = pending * retired / branches if branches else 0
            rate = .02 + .58 * min((withdrawn + gross) / max(pending + withdrawn, 10e6) / .1, 1)**2
            net_tokens = gross * (1 - rate)
            pending -= gross; withdrawn += gross; branches -= retired
            stock += net_tokens; minted += net_tokens
            totals['gross_withdrawn'] += gross
            totals['net_withdrawn_tokens'] += net_tokens
            sell(net_tokens); exit_done = True
        record(end)
    result = with_utc(pd.DataFrame(records), e['timestamp'])
    if result.eth_error.abs().max() > 1e-6 or result.token_error.abs().max() > .02:
        raise AssertionError('Pool accounting failed')
    return result


def default_scenarios():
    return [Scenario(),
        Scenario('Selling halves every 6h', sell_half_life_hours=6),
        Scenario('Rapid seller exhaustion: 2h', sell_half_life_hours=2),
        Scenario('Demand fades too', sell_half_life_hours=6, buy_half_life_hours=6),
        Scenario('Buying triples; selling halves in 6h', buy_multiple=3, sell_half_life_hours=6),
        Scenario('6h selling decay + buybacks', sell_half_life_hours=6, buybacks=True),
        Scenario('6h decay + 100 licenses, 20% fresh-funded', sell_half_life_hours=6,
                 license_fill=1, license_external_fraction=.2),
        Scenario('6h decay + 100 licenses, fully fresh-funded', sell_half_life_hours=6,
                 license_fill=1, license_external_fraction=1),
        Scenario('6h decay + half of branches retire at +6h', sell_half_life_hours=6, withdrawal_fraction=.5)]


def thresholds(e):
    pool = pool_for(e); _, current = pool.curve.inventories(pool.sqrt)
    rows = []
    for label, target in e['references'].items():
        _, need = pool.curve.inventories(1 / math.sqrt(target))
        principal = max(0, need - current)
        rows.append(dict(target=label, target_price_eth=target, gain_pct=100 * (target / pool.price - 1),
            additional_pool_principal_eth=principal,
            wallet_buy_eth_no_sellers=principal / ((1 - pool.buy_tax) * (1 - pool.lp_fee))))
    return pd.DataFrame(rows)


def summarize(e, paths):
    rows = []
    for name, frame in paths.items():
        row = dict(scenario=name, low_ratio=frame.price_ratio.min(), low_h=float(frame.loc[frame.price.idxmin(), 'hour']))
        for h in [6, 12, 24, 48]:
            row[f'price_ratio_{h}h'] = float(frame.iloc[(frame.hour - h).abs().argmin()].price_ratio)
        for label, target in e['references'].items():
            hits = frame[frame.price >= target]
            row[label + '_h'] = float(hits.iloc[0].hour) if len(hits) else np.nan
        row.update({k: float(frame.iloc[-1][k]) for k in ['total_buy_spend_eth','speculative_buy_eth','license_buy_eth','buyback_eth','pool_sell_eth','unsold_requested_tokens']})
        rows.append(row)
    return with_utc(pd.DataFrame(rows), e['timestamp'])
