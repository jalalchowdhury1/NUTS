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

import json
import urllib.request
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime
from typing import Optional
import pytz

FINNHUB_KEY = "d75f31pr01qk56kchlsgd75f31pr01qk56kchlt0"
POLYGON_KEY = "o0a2QcLRTxSur_kNLaZUUK1GIPjc_Iz3"


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
_MARKET_OPEN        = dtime(9, 30)
_PRICE_INJECT_UNTIL = dtime(20, 0)   # inject live price until 8 PM ET (covers after-hours close confirmation)


def _should_inject_live_price() -> bool:
    """Return True on weekdays from market open (9:30 ET) through 8 PM ET.

    This covers both intraday prices and the confirmed closing price that
    yfinance/Finnhub make available shortly after 4 PM ET.
    """
    now_et = datetime.now(_ET)
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _MARKET_OPEN <= now_et.time() < _PRICE_INJECT_UNTIL


def _fetch_live_price(ticker: str) -> Optional[float]:
    """Fetch live price with 3-layer redundancy: yfinance -> Finnhub -> Polygon"""
    # 1. Try yfinance
    try:
        import yfinance as yf
        live_data = yf.download(ticker, period="1d", interval="1m", auto_adjust=True, progress=False)
        if not live_data.empty and "Close" in live_data:
            val = float(live_data["Close"].iloc[-1])
            if not np.isnan(val):
                return val
    except Exception as e:
        print(f"[data_fetcher] yfinance failed for {ticker}: {e}")

    # 2. Try Finnhub Fallback
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("c") is not None and data["c"] > 0:
                print(f"[data_fetcher] Used Finnhub fallback for {ticker}")
                return float(data["c"])
    except Exception as e:
        print(f"[data_fetcher] Finnhub failed for {ticker}: {e}")

    # 3. Try Polygon Fallback
    try:
        url = f"https://api.polygon.io/v2/last/trade/{ticker}?apiKey={POLYGON_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "results" in data and "p" in data["results"]:
                print(f"[data_fetcher] Used Polygon fallback for {ticker}")
                return float(data["results"]["p"])
    except Exception as e:
        print(f"[data_fetcher] Polygon failed for {ticker}: {e}")

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

    prices = np.array(series.values, dtype=float)
    prices = prices[~np.isnan(prices)]

    # During market hours, always inject the live intraday price.
    if _should_inject_live_price():
        live = _fetch_live_price(ticker)
        if live is not None:
            today_str = datetime.now(_ET).strftime("%Y-%m-%d")
            if series.index[-1] == today_str:
                # Bootstrap already wrote today's row — overwrite it with the current price.
                prices[-1] = live
                print(f"[data_fetcher] {ticker}: overwrote today's S3 price with live {live:.4f}")
            else:
                # Last S3 row is from a previous day — append today's live price.
                prices = np.append(prices, live)
                print(f"[data_fetcher] {ticker}: appended live intraday price {live:.4f}")

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
