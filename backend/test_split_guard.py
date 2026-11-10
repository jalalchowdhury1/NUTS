"""Split/adjustment guards (SOXX 3:1, 5 Nov 2026). Live Yahoo data, S3 stubbed. Run: python test_split_guard.py"""
import sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd, yfinance as yf, io
import data_fetcher as f, data_manager as dm, calculations as c
h = yf.Ticker("SOXX").history(period="2y", auto_adjust=True)["Close"].dropna()
good = pd.Series(h.values, index=[d.date().isoformat() for d in h.index])
bad = good.copy(); bad[bad.index < "2026-11-05"] *= 3
R = lambda p: round(c.calculate_rsi_sma(p, 10), 2)
ok = True
def check(name, got, want):
    global ok; ok &= abs(got - want) < 0.05; print(("PASS " if abs(got-want) < .05 else "FAIL ") + name, got, want)
want = R(good.values)
# 1. split already in stored history (yesterday's situation)
check("stored unadjusted", R(f._undo_unadjusted_splits("SOXX", list(bad.index), bad.values.astype(float))), want)
# 2. split day: S3 ends pre-split on 11-04, live post-split price appended
b2 = bad[bad.index < "2026-11-05"]; p2 = np.append(b2.values, good["2026-11-05"])
check("split day live bar", R(f._undo_unadjusted_splits("SOXX", list(b2.index), p2)), R(good[good.index <= "2026-11-05"].values))
# 3. already-adjusted history is left alone
check("adjusted untouched", R(f._undo_unadjusted_splits("SOXX", list(good.index), good.values.astype(float))), want)
# 4. real crash, no split: SOXL untouched
s = yf.Ticker("SOXL").history(period="2y", auto_adjust=True)["Close"].dropna()
x = s.values.astype(float).copy(); x[-1] = x[-2] * 0.6
check("real -40% crash untouched", R(f._undo_unadjusted_splits("SOXL", [d.date().isoformat() for d in s.index], x)), R(x))
# 5. update_daily: dividend-sized drift (0.35%) triggers a full reload; exact rows append only
puts = {}
class C:
    def put_object(self, **k): puts[k["Key"]] = k["Body"]
dm._s3_client = lambda: C()
b = yf.Ticker("BIL").history(period="1y", auto_adjust=True)["Close"].dropna()
bs = pd.Series(b.values, index=[d.date().isoformat() for d in b.index])
st = bs[bs.index < bs.index[-2]].copy(); st *= 1.0035
dm.load_historical = lambda t: st; dm.update_daily("BIL")
n = len(pd.read_csv(io.BytesIO(puts["historical/BIL_prices.csv"]))); check("BIL drift -> full reload (rows>1000)", float(n > 1000), 1.0)
puts.clear(); dm.load_historical = lambda t: bs[bs.index < bs.index[-2]]; dm.update_daily("BIL")
n = len(pd.read_csv(io.BytesIO(puts["historical/BIL_prices.csv"]))); check("BIL exact -> append only", float(n == len(bs)), 1.0)
sys.exit(0 if ok else 1)
