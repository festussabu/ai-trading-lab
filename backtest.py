"""
Simple strategy backtest on monthly S&P 500 data (with dividends).
Data: github.com/datasets/s-and-p-500 (Shiller monthly data).

Strategies compared:
  1. Buy & Hold           - buy the index, never sell
  2. Trend (10-month SMA) - hold stocks only when price > its 10-month average, else cash
  3. Momentum (12-month)  - hold stocks only when the past 12-month return is positive, else cash
  4. Panic Seller         - sell after any month that drops more than 5%, buy back 3 months later

Assumptions: cash earns 2%/yr, each switch in/out costs 0.1%, no taxes.
Run:  python3 backtest.py
"""
import json
import numpy as np
import pandas as pd

CASH_RATE = 0.02 / 12
SWITCH_COST = 0.001
START = "1995-01-01"
MONTHLY_CONTRIB = 200      # for the "$200/month" scenario
CONTRIB_START = "2006-10-01"

df = pd.read_csv("sp500.csv", parse_dates=["Date"]).set_index("Date")
df["Dividend"] = df["Dividend"].replace(0, np.nan).ffill()
price = df["SP500"]
div_ret = df["Dividend"] / 12 / price
stock_ret = price.pct_change() + div_ret.shift(1)

# Signals use only data known at the end of the previous month (no peeking ahead)
sma10 = price.rolling(10).mean()
sig_trend = (price > sma10).astype(int).shift(1)
sig_mom = (price.pct_change(12) > 0).astype(int).shift(1)

panic = pd.Series(1, index=price.index)
out_until = None
monthly = price.pct_change()
for i, d in enumerate(price.index):
    if out_until is not None and i < out_until:
        panic.iloc[i] = 0
        continue
    out_until = None
    if monthly.iloc[i] < -0.05:
        out_until = i + 1 + 3
sig_panic = panic.shift(1)


def run(signal, rets):
    signal = signal.reindex(rets.index).fillna(1)
    r = signal * rets + (1 - signal) * CASH_RATE
    switches = signal.diff().abs().fillna(0)
    r = r - switches * SWITCH_COST
    return r, int(switches.sum())


rets = stock_ret[START:].dropna()
strategies = {
    "Buy & Hold": (pd.Series(1, index=rets.index), "Buy the index, never sell"),
    "Trend (10-mo avg)": (sig_trend, "In stocks only when price is above its 10-month average"),
    "Momentum (12-mo)": (sig_mom, "In stocks only when the last 12 months were positive"),
    "Panic Seller": (sig_panic, "Sells after any -5% month, buys back 3 months later"),
}

results, curves = [], {}
years = len(rets) / 12
for name, (sig, desc) in strategies.items():
    r, n_switch = run(sig, rets)
    growth = (1 + r).cumprod()
    curves[name] = (10000 * growth).round(0)
    dd = (growth / growth.cummax() - 1).min()
    cagr = growth.iloc[-1] ** (1 / years) - 1
    vol = r.std() * np.sqrt(12)
    # Contribution scenario: $200/month
    rc = r[CONTRIB_START:]
    bal = 0.0
    for x in rc:
        bal = (bal + MONTHLY_CONTRIB) * (1 + x)
    pct_in = float(sig.reindex(rets.index).fillna(1).mean())
    results.append({
        "name": name, "desc": desc,
        "final_10k": round(float(10000 * growth.iloc[-1])),
        "cagr": round(cagr * 100, 2),
        "max_drawdown": round(dd * 100, 1),
        "volatility": round(vol * 100, 1),
        "trades": n_switch,
        "pct_invested": round(pct_in * 100),
        "contrib_final": round(bal),
        "contrib_paid": MONTHLY_CONTRIB * len(rc),
    })

for row in results:
    print(row)

out = {
    "start": START, "end": str(rets.index[-1].date()),
    "contrib_start": CONTRIB_START,
    "results": results,
    "dates": [d.strftime("%Y-%m") for d in rets.index],
    "curves": {k: v.tolist() for k, v in curves.items()},
}
json.dump(out, open("results.json", "w"))
