"""
NUTS Algo — Historical data bootstrap script.

One-off script: downloads the maximum available history for every ticker in
ALL_TICKERS via yfinance and uploads a CSV to S3 at:

    s3://nuts-algo-data/historical/{TICKER}_prices.csv

CSV format (two columns, no index):
    date,close
    2010-01-04,113.33
    ...

Run this once before the first Lambda deployment, then rely on
data_manager.update_daily() for incremental daily updates.

Usage:
    python bootstrap_historical.py
    python bootstrap_historical.py --dry-run   # download only, skip S3 upload
"""

import argparse
import io
import sys

import boto3
import pandas as pd
import yfinance as yf
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

S3_BUCKET = "nuts-algo-data"
S3_PREFIX = "historical"

ALL_TICKERS = [
    "BIL", "BND", "IEF", "QQQ", "SH", "SOXX", "SOXL",
    "SPY", "SPXL", "SQQQ", "TECL", "TLT", "TMF", "TQQQ",
    "UPRO", "UVXY", "VIXY", "VOX", "VTV", "XLF", "XLK", "XLP",
]


# ─────────────────────────────────────────────────────────────────────────────
# Download helpers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_max_history(ticker: str) -> pd.DataFrame:
    """
    Download the maximum available daily close history for *ticker*.

    Returns a DataFrame with columns ['date', 'close'], date as a string
    (YYYY-MM-DD), NaN rows dropped, sorted ascending.

    Raises ValueError if no usable data is returned.
    """
    print(f"  [{ticker}] downloading max history …", end=" ", flush=True)
    ticker_obj = yf.Ticker(ticker)
    df = ticker_obj.history(period="max", auto_adjust=True)

    if df is None or df.empty:
        raise ValueError(f"yfinance returned no data for {ticker}")

    # Handle MultiIndex columns (shouldn't happen with .history() but be safe)
    if isinstance(df.columns, pd.MultiIndex):
        close_series = df["Close"].iloc[:, 0]
    else:
        close_series = df["Close"]

    close_series = close_series.dropna()

    if close_series.empty:
        raise ValueError(f"All Close values are NaN for {ticker}")

    # Normalise the index to plain date strings
    dates = close_series.index
    if hasattr(dates[0], "date"):
        date_strs = [d.date().isoformat() for d in dates]
    else:
        date_strs = [str(d)[:10] for d in dates]

    result = pd.DataFrame({
        "date":  date_strs,
        "close": close_series.values.astype(float),
    })

    print(f"{len(result)} rows  ({result['date'].iloc[0]} → {result['date'].iloc[-1]})")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# S3 upload helper
# ─────────────────────────────────────────────────────────────────────────────

def upload_to_s3(df: pd.DataFrame, ticker: str, s3_client) -> None:
    """Serialize *df* as CSV and upload to S3."""
    key = f"{S3_PREFIX}/{ticker}_prices.csv"
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    body = csv_buffer.getvalue().encode("utf-8")

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="text/csv",
    )
    print(f"  [{ticker}] uploaded → s3://{S3_BUCKET}/{key}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bootstrap NUTS historical price CSVs to S3")
    parser.add_argument("--dry-run", action="store_true",
                        help="Download data but do not upload to S3")
    parser.add_argument("--tickers", nargs="+", default=ALL_TICKERS,
                        help="Subset of tickers to process (default: all)")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    s3 = None if args.dry_run else boto3.client("s3")

    print(f"Bootstrap starting — {len(tickers)} tickers, dry_run={args.dry_run}")
    print(f"Target bucket: s3://{S3_BUCKET}/{S3_PREFIX}/\n")

    successes = []
    failures  = []

    for ticker in tickers:
        try:
            df = fetch_max_history(ticker)
            if not args.dry_run:
                upload_to_s3(df, ticker, s3)
            successes.append(ticker)
        except (ValueError, ClientError, Exception) as exc:
            print(f"  [{ticker}] FAILED: {exc}")
            failures.append({"ticker": ticker, "error": str(exc)})

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Done.  {len(successes)}/{len(tickers)} tickers succeeded.")
    if failures:
        print(f"\nFailed tickers ({len(failures)}):")
        for f in failures:
            print(f"  {f['ticker']}: {f['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
