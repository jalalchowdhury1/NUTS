"""
NUTS Algo — Data fetcher.

Loads price history from S3 CSVs via data_manager instead of downloading
120+ days of data from yfinance on every Lambda invocation.

Historical CSVs are populated once by bootstrap_historical.py and kept
up-to-date by the daily EventBridge cron (action='update_prices') which
calls data_manager.update_daily() for each ticker.

During market hours (9:30 AM – 4:00 PM ET, Mon–Fri), download_ticker()
also appends the current intraday snapshot price so that signal
calculations always reflect today's live price, not yesterday's close.
"""

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime
import pytz


# ─────────────────────────────────────────────────────────────────────────────
# Canonical ticker list (22 tickers)
# ─────────────────────────────────────────────────────────────────────────────

ALL_TICKERS = [
    "BIL", "BND", "IEF", "QQQ", "SH", "SOXX", "SOXL",
    "SPY", "SPXL", "SQQQ", "TECL", "TLT", "TMF", "TQQQ",
    "UPRO", "UVXY", "VIXY", "VOX", "VTV", "XLF", "XLK", "XLP",
]

MIN_ROWS = 60

_ET = pytz.timezone("America/New_York")
_MARKET_OPEN  = dtime(9, 30)
_MARKET_CLOSE = dtime(16, 0)


def _market_is_open() -> bool:
    """Return True if US equity markets are currently open (Mon–Fri, 9:30–16:00 ET)."""
    now_et = datetime.now(_ET)
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _MARKET_OPEN <= now_et.time() < _MARKET_CLOSE


def _fetch_live_price(ticker: str) -> float | None:
    """
    Fetch the latest trade price for *ticker* via yfinance 1-minute bar.
    Returns None on any failure so callers can degrade gracefully.
    """
    try:
        import yfinance as yf
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data is None or data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception as exc:
        print(f"[data_fetcher] live price fetch failed for {ticker}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Per-ticker loader
# ─────────────────────────────────────────────────────────────────────────────

def download_ticker(ticker: str) -> tuple:
    """
    Load closing prices for *ticker* from the S3 historical CSV.

    Returns:
        prices: np.ndarray of closing prices (float64, NaN stripped, oldest first)
        meta:   dict with rows, last_date, last_close

    Raises:
        FileNotFoundError: if the CSV hasn't been bootstrapped yet.
        ValueError:        if there are fewer than MIN_ROWS data points.
    """
    from data_manager import load_historical
    series = load_historical(ticker)   # raises FileNotFoundError if missing

    # During market hours, append today's live price if not yet in the CSV.
    today_str = datetime.now(_ET).strftime("%Y-%m-%d")
    if _market_is_open() and series.index[-1] < today_str:
        live = _fetch_live_price(ticker)
        if live is not None:
            series[today_str] = live
            print(f"[data_fetcher] {ticker}: appended live intraday price {live:.4f}")

    prices = np.array(series.values, dtype=float)
    prices = prices[~np.isnan(prices)]

    if len(prices) < MIN_ROWS:
        raise ValueError(
            f"Insufficient data for {ticker}: {len(prices)} rows "
            f"(minimum {MIN_ROWS} required)"
        )

    last_date  = series.index[-1]
    last_close = round(float(prices[-1]), 4)

    meta = {
        "rows":       int(len(prices)),
        "last_date":  last_date,
        "last_close": last_close,
    }
    return prices, meta


# ─────────────────────────────────────────────────────────────────────────────
# Bulk loader
# ─────────────────────────────────────────────────────────────────────────────

def download_all_tickers() -> tuple:
    """
    Load all tickers in ALL_TICKERS from S3 in parallel.

    Returns:
        prices_dict:  {ticker: np.ndarray}
        data_quality: {ticker: {rows, last_date, last_close}}
        errors:       list of {ticker, error} for any failures
    """
    prices_dict  = {}
    data_quality = {}
    errors       = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_ticker, t): t for t in ALL_TICKERS}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                prices, meta = future.result()
                prices_dict[ticker]  = prices
                data_quality[ticker] = meta
            except Exception as exc:
                errors.append({"ticker": ticker, "error": str(exc)})

    return prices_dict, data_quality, errors
