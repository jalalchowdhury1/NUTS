"""
NUTS Algo — Data fetcher.

Downloads 120 days of OHLCV history using yfinance.
Handles multi-level columns, strips NaN, enforces 60-row minimum.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta


# All tickers needed across all branches (pre-fetch for Branch 3 readiness)
ALL_TICKERS = sorted(set([
    # Branch 1: Frontrunners
    "SPY", "QQQ", "VTV", "VOX", "XLK", "XLP", "XLF",
    "SOXX", "SOXL", "TECL", "UPRO", "VIXY", "UVXY",
    # Branch 2: FTLT
    "TQQQ", "SPXL", "SQQQ", "TLT",
    # Branch 3 (stub — pre-fetch only)
    "SH", "TMF", "BND", "BIL", "IEF", "URTY", "PSQ",
]))

HISTORY_DAYS = 300  # Branch 3 needs RSI(200d) and max_drawdown(180d) — requires ~210 trading days
MIN_ROWS = 60

# yfinance is not thread-safe for concurrent downloads due to shared internal caches
DOWNLOAD_LOCK = threading.Lock()


def download_ticker(ticker: str) -> tuple[np.ndarray, dict]:
    """
    Download HISTORY_DAYS of closing prices for a single ticker.

    Returns:
        prices: numpy array of closing prices (NaN stripped)
        meta:   dict with rows, last_date, last_close

    Raises:
        ValueError: if download fails or fewer than MIN_ROWS rows.
    """
    end = datetime.today()
    start = end - timedelta(days=HISTORY_DAYS)

    with DOWNLOAD_LOCK:
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True
        )

    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker}")

    # Handle multi-level columns (yfinance sometimes returns MultiIndex in weird cases)
    if isinstance(df.columns, pd.MultiIndex):
        close_series = df["Close"].iloc[:, 0]
    else:
        close_series = df["Close"]

    prices = close_series.values.astype(float)

    # Strip NaN
    prices = prices[~np.isnan(prices)]

    if len(prices) < MIN_ROWS:
        raise ValueError(
            f"Insufficient data for {ticker}: {len(prices)} rows (minimum {MIN_ROWS} required)"
        )

    last_date = close_series.dropna().index[-1]
    if hasattr(last_date, "date"):
        last_date_str = last_date.date().isoformat()
    else:
        last_date_str = str(last_date)[:10]

    meta = {
        "rows": int(len(prices)),
        "last_date": last_date_str,
        "last_close": round(float(prices[-1]), 4),
    }

    return prices, meta


def download_all_tickers() -> tuple[dict, dict, list]:
    """
    Download all tickers in ALL_TICKERS.

    Returns:
        prices_dict:  {ticker: np.ndarray}
        data_quality: {ticker: {rows, last_date, last_close}}
        errors:       list of {ticker, error} for failures
    """
    prices_dict = {}
    data_quality = {}
    errors = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_ticker, ticker): ticker for ticker in ALL_TICKERS}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                prices, meta = future.result()
                prices_dict[ticker] = prices
                data_quality[ticker] = meta
            except Exception as exc:
                errors.append({"ticker": ticker, "error": str(exc)})

    return prices_dict, data_quality, errors
