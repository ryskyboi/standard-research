"""UTC presentation helpers; elapsed model time and numerical results stay intact."""
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator


def utc_at(snapshot, hours=0, fmt='%Y-%m-%d %H:%M:%S UTC'):
    anchor = pd.Timestamp(snapshot)
    anchor = anchor.tz_localize('UTC') if anchor.tzinfo is None else anchor.tz_convert('UTC')
    return (anchor + pd.Timedelta(hours=float(hours))).strftime(fmt)


def with_utc(table, snapshot):
    """Add calendar columns for elapsed-time outputs, retaining original columns.

    *_h columns denote snapshot-relative result times, never rates/durations.
    Raw hourly paths/events additionally get elapsed_days and timestamp_utc.
    """
    out = table.copy()
    for name in list(table.columns):
        if name == 'hour':
            out['elapsed_days'] = table[name] / 24
            target = 'timestamp_utc'
        elif name.endswith('_h'):
            target = name[:-2] + '_utc'
        else:
            continue
        out[target] = table[name].map(lambda h: utc_at(snapshot, h) if pd.notna(h) else None)
    return out


def utc_axis(ax, snapshot, hours_per_unit=1):
    """Keep elapsed time below a chart and add a linked UTC calendar axis above."""
    top = ax.secondary_xaxis('top')
    top.xaxis.set_major_locator(MaxNLocator(nbins=4))
    top.xaxis.set_major_formatter(FuncFormatter(
        lambda x, pos: utc_at(snapshot, x * hours_per_unit, '%b %d\n%H:%M')))
    top.set_xlabel('UTC calendar time (' + pd.Timestamp(snapshot).strftime('%Y') + ')')
    top.tick_params(labelsize=8)
    return top
