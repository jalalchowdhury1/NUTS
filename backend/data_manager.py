"""
NUTS Algo — Data manager.

Owns all interaction with the S3 historical price CSVs.  Each CSV lives at:

    s3://nuts-algo-data/historical/{TICKER}_prices.csv

CSV format (written by bootstrap_historical.py):
    date,close
    2010-01-04,113.33
    ...

Public API
──────────
    load_historical(ticker)  → pd.Series  (index=date str, values=float close)
    update_daily(ticker)     → None        (append new trading days, overwrite S3)
    get_prices(ticker)       → list[float] (sorted ascending, ready for calcs)
"""

import io
from datetime import datetime, timedelta

import boto3
import numpy as np
import pandas as pd
import yfinance as yf
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

S3_BUCKET  = "nuts-algo-data"
S3_PREFIX  = "historical"

# How many calendar days to look back when fetching the yfinance delta.
# 5 trading days of overlap guarantees we never miss a day across weekends /
# holidays regardless of when the cron fires.
DELTA_DAYS = 5

MIN_ROWS   = 60   # minimum acceptable price history for any ticker


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _s3_key(ticker: str) -> str:
    return f"{S3_PREFIX}/{ticker}_prices.csv"


def _s3_client():
    return boto3.client("s3")


def _series_to_csv_bytes(series: pd.Series) -> bytes:
    """Convert a date-indexed Series to the canonical CSV format."""
    df = pd.DataFrame({"date": series.index, "close": series.values})
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_historical(ticker: str) -> pd.Series:
    """
    Load the full price history for *ticker* from S3.

    Returns a pd.Series with string date index (YYYY-MM-DD) and float values,
    sorted ascending.

    Raises:
        FileNotFoundError: if the CSV does not exist in S3 yet (run bootstrap).
        ValueError:        if the CSV is malformed or contains no usable rows.
    """
    key = _s3_key(ticker)
    s3  = _s3_client()

    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        body     = response["Body"].read().decode("utf-8")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            raise FileNotFoundError(
                f"Historical CSV not found for {ticker} "
                f"(s3://{S3_BUCKET}/{key}). Run bootstrap_historical.py first."
            ) from exc
        raise

    try:
        df = pd.read_csv(io.StringIO(body))
    except Exception as exc:
        raise ValueError(f"Could not parse CSV for {ticker}: {exc}") from exc

    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError(f"CSV for {ticker} is missing 'date' or 'close' columns")

    df = df.dropna(subset=["close"])
    df = df.sort_values("date")

    series = pd.Series(
        df["close"].values.astype(float),
        index=df["date"].astype(str).values,
        name=ticker,
    )
    return series


def update_daily(ticker: str) -> None:
    """
    Fetch the latest DELTA_DAYS of prices from yfinance and append any new
    dates to the existing S3 CSV, then overwrite it.

    This is called by the daily EventBridge cron (action='update_prices').
    It is intentionally idempotent — re-running it on the same day is safe.

    Raises:
        FileNotFoundError: if the historical CSV doesn't exist yet.
        ValueError:        if yfinance returns no usable data.
    """
    # Load what we have
    series = load_historical(ticker)
    last_known_date = series.index[-1]  # YYYY-MM-DD string

    # Fetch a short window from yfinance (overlap ensures no gaps)
    end   = datetime.today()
    start = end - timedelta(days=DELTA_DAYS + 3)  # +3 for weekend buffer

    ticker_obj = yf.Ticker(ticker)
    df_new = ticker_obj.history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
    )

    if df_new is None or df_new.empty:
        print(f"[data_manager] update_daily({ticker}): yfinance returned no data — skipping")
        return

    # Normalise
    if isinstance(df_new.columns, pd.MultiIndex):
        close_new = df_new["Close"].iloc[:, 0]
    else:
        close_new = df_new["Close"]

    close_new = close_new.dropna()

    # Build date strings for new rows
    idx = close_new.index
    if hasattr(idx[0], "date"):
        date_strs = [d.date().isoformat() for d in idx]
    else:
        date_strs = [str(d)[:10] for d in idx]

    new_series = pd.Series(
        close_new.values.astype(float),
        index=date_strs,
        name=ticker,
    )

    # Only keep rows that are strictly newer than what we already have
    new_rows = new_series[new_series.index > last_known_date]

    if new_rows.empty:
        print(f"[data_manager] update_daily({ticker}): already up to date (last={last_known_date})")
        return

    # Append and sort
    updated = pd.concat([series, new_rows]).sort_index()
    updated = updated[~updated.index.duplicated(keep="last")]

    # Overwrite S3
    s3  = _s3_client()
    key = _s3_key(ticker)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=_series_to_csv_bytes(updated),
        ContentType="text/csv",
    )
    print(f"[data_manager] update_daily({ticker}): appended {len(new_rows)} row(s), "
          f"new last date={updated.index[-1]}")


def get_prices(ticker: str) -> list:
    """
    Return the full price history for *ticker* as a plain list of floats,
    sorted oldest-first — the format expected by calculate_rsi_sma(),
    moving_average_price(), etc.

    Raises:
        FileNotFoundError: if the CSV hasn't been bootstrapped yet.
        ValueError:        if the series has fewer than MIN_ROWS data points.
    """
    series = load_historical(ticker)

    if len(series) < MIN_ROWS:
        raise ValueError(
            f"Insufficient history for {ticker}: {len(series)} rows "
            f"(minimum {MIN_ROWS} required)"
        )

    return series.tolist()
