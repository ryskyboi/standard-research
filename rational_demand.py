"""Arithmetic constraints on branch demand; no price forecast or equilibrium claim."""
from pathlib import Path
import json,math
import model as m

root=Path(__file__).resolve().parent
s=m.snapshot();home=m.read('home.json')['snapshot'];pool=m.ConcentratedPool(s['liquidity_profile'])
max_branches=int(home['bank']['MAX_BRANCHES']);daily=int(home['licenseAuction']['dayCap'])
per_charter=int(home['licenseAuction']['MAX_PER_CHARTER_PER_DAY'])
income=s['base_per_day']*s['multiplier']/s['branches'];floor=2*income
capacity=s['active_charters']*max_branches;room=capacity-s['branches']
# Fixed 700k/day, all auctions filled at each day's illustrative floor, no
# retirements/new Charters/recycling/policy changes. NOT an upper spending bound.
n=float(s['branches']);total_floor_tokens=0.;days=0
while n<capacity:
    opened=min(daily,capacity-n)
    total_floor_tokens+=opened*2*s['base_per_day']*s['multiplier']/n
    n+=opened;days+=1
results=dict(snapshot_timestamp=s['timestamp'],branch_cap_evidence='branch-cap-evidence.json',
    active_charters=s['active_charters'],branches=s['branches'],max_per_charter=max_branches,
    new_branches_per_charter_day=per_charter,new_branches_system_day=daily,
    new_charters_per_day=int(home['charterAuction']['chartersPerDay']),
    cohort_capacity=capacity,remaining_slots=room,minimum_additional_auction_days=math.ceil(room/daily),
    current_income_per_branch_day=income,illustrative_next_floor=floor,
    floor_tokens_consumed_per_day=daily*floor,
    floor_consumption_fraction_of_issuance=daily*floor/(s['base_per_day']*s['multiplier']),
    marginal_ETH_day_all_external=daily*floor*pool.price/(1-pool.buy_tax)/(1-pool.lp_fee),
    marginal_ETH_day_25pct_external=.25*daily*floor*pool.price/(1-pool.buy_tax)/(1-pool.lp_fee),
    one_shot_ETH_for_full_daily_floor_demand=pool.quote_buy(daily*floor),
    implied_next_opening_tokens=2*s['last_license_price'],
    opening_days_of_current_gross_output=2*s['last_license_price']/income,
    floor_program_tokens_if_fixed_cohort=total_floor_tokens,
    floor_program_spot_ETH=total_floor_tokens*pool.price,
    floor_program_days=days,
    bounds='Daily license capacity is a consumption limit, not a limit on pool purchases. Prices, prefunding, reinvestment, retirement, and new Charter policy change cash demand.')
(root/'rational-demand-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
