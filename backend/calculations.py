"""
NUTS Algo — Indicator calculations.

RSI window for ALL NUTS conditions = 10.
RSI formula uses SMA (Simple Moving Average), NOT EMA.

Unit test:
  prices=[100,102,101,103,102,104,105,103,106,107], window=9 → 73.3333
"""

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# RSI (SMA method) — copied verbatim from trading-algorithm repo
# ─────────────────────────────────────────────────────────────────────────────

def calculate_rsi_sma(prices, window):
    """
    Calculate RSI using Simple Moving Average (SMA).

    NOT EMA. This is the canonical NUTS RSI formula.

    Unit test:
      prices=[100,102,101,103,102,104,105,103,106,107]
      window=9 → 73.3333
    """
    prices = np.array(prices, dtype=float)
    diffs = np.diff(prices)
    ups = np.where(diffs > 0, diffs, 0)
    downs = np.where(diffs < 0, np.abs(diffs), 0)
    avg_up = np.mean(ups[-window:])
    avg_down = np.mean(downs[-window:])
    if avg_down == 0:
        return 100.0
    rs = avg_up / avg_down
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


# ─────────────────────────────────────────────────────────────────────────────
# Moving average
# ─────────────────────────────────────────────────────────────────────────────

def moving_average_price(prices, window):
    """Simple mean of the last N closing prices."""
    prices = np.array(prices, dtype=float)
    return float(np.mean(prices[-window:]))


def current_price(prices):
    """Return the most recent closing price."""
    prices = np.array(prices, dtype=float)
    return float(prices[-1])


# ─────────────────────────────────────────────────────────────────────────────
# RSI filter — pick ticker with the lowest RSI
# ─────────────────────────────────────────────────────────────────────────────

def rsi_filter(ticker_prices_dict, window):
    """
    Given {ticker: prices_array}, compute RSI for each.
    Returns (winner_ticker, {ticker: rsi_value}) where winner has the LOWEST RSI.

    This mirrors Composer's "sort by RSI ascending, select top 1".
    """
    rsi_values = {}
    for ticker, prices in ticker_prices_dict.items():
        rsi_values[ticker] = calculate_rsi_sma(prices, window)
    winner = min(rsi_values, key=lambda t: rsi_values[t])
    return winner, rsi_values


# ─────────────────────────────────────────────────────────────────────────────
# Stubs — implement in Phase 3
# ─────────────────────────────────────────────────────────────────────────────

def cumulative_return(prices, window_days):
    if len(prices) < window_days:
        return None
    return (prices[-1] - prices[-window_days]) / prices[-window_days] * 100


def max_drawdown(prices, window_days):
    if len(prices) < window_days:
        return None
    window = prices[-window_days:]
    max_dd = 0
    peak = window[0]
    for price in window:
        if price > peak:
            peak = price
        dd = (peak - price) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ─────────────────────────────────────────────────────────────────────────────
# Unit test
# ─────────────────────────────────────────────────────────────────────────────

def run_unit_test():
    """
    Canonical unit test for calculate_rsi_sma.
    Must pass before any live data is processed.

    Manual verification:
      diffs = [2,-1,2,-1,2,1,-2,3,1]
      ups   = [2, 0,2, 0,2,1, 0,3,1]  → sum=11  avg=11/9=1.2222
      downs = [0, 1,0, 1,0,0, 2,0,0]  → sum=4   avg=4/9=0.4444
      RS    = 1.2222/0.4444 = 2.75
      RSI   = 100 − 100/(1+2.75) = 100 − 26.6667 = 73.3333  ✓
    """
    prices = [100, 102, 101, 103, 102, 104, 105, 103, 106, 107]
    window = 9
    result = calculate_rsi_sma(prices, window)
    expected = 73.3333
    passed = abs(result - expected) < 0.001
    return {
        "expected": round(expected, 4),
        "calculated": round(result, 4),
        "pass": passed,
    }


if __name__ == "__main__":
    test = run_unit_test()
    print(f"Unit test: expected={test['expected']}, calculated={test['calculated']}, pass={test['pass']}")
    assert test["pass"], "UNIT TEST FAILED — do NOT process live data"
    print("Unit test PASSED ✓")
