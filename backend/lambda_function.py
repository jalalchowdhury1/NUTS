"""
NUTS Algo — AWS Lambda handler + API Gateway routing.

Routes:
  GET /test-rsi          Run unit test
  GET /evaluate          Evaluate both trees (cached ≤ 60 min)
  GET /evaluate?force=true  Force fresh evaluation

ACCURACY IS THE #1 PRIORITY.
Unit test MUST pass before any live data is processed.
"""

import json
import traceback

from calculations import run_unit_test, calculate_rsi_sma, moving_average_price, current_price
from data_fetcher import download_all_tickers
from state_manager import read_state, write_state, _NumpyEncoder
from trees.frontrunners import evaluate_frontrunners
from trees.ftlt import evaluate_ftlt
from trees.blackswan import evaluate_blackswan


# ─────────────────────────────────────────────────────────────────────────────
# CORS headers (API Gateway HTTP API)
# ─────────────────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Content-Type": "application/json",
}


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=_NumpyEncoder),
    }


def _error(status: int, message: str, detail: str = "") -> dict:
    payload = {"error": message}
    if detail:
        payload["detail"] = detail
    return _response(status, payload)


# ─────────────────────────────────────────────────────────────────────────────
# /test-rsi
# ─────────────────────────────────────────────────────────────────────────────

def handle_test_rsi() -> dict:
    result = run_unit_test()
    return _response(200, result)


# ─────────────────────────────────────────────────────────────────────────────
# /evaluate
# ─────────────────────────────────────────────────────────────────────────────

def handle_evaluate(force: bool = False) -> dict:
    # Step 1 — unit test MUST pass before live data
    unit = run_unit_test()
    if not unit["pass"]:
        return _error(
            500,
            "RSI unit test FAILED — refusing to process live data",
            f"expected={unit['expected']} calculated={unit['calculated']}",
        )

    # Step 2 — check cache
    if not force:
        cached = read_state()
        if cached:
            cached["cache_hit"] = True
            return _response(200, cached)

    # Step 3 — download data
    prices_dict, data_quality, download_errors = download_all_tickers()

    if download_errors:
        # Report errors but continue if we have enough tickers
        print(f"[evaluate] Download errors: {download_errors}")

    # Step 4 — evaluate trees
    try:
        fr_result = evaluate_frontrunners(prices_dict)
    except Exception as exc:
        return _error(500, "Frontrunners evaluation failed", traceback.format_exc())

    try:
        ftlt_result = evaluate_ftlt(prices_dict)
    except Exception as exc:
        return _error(500, "FTLT evaluation failed", traceback.format_exc())

    blackswan_result = evaluate_blackswan(prices_dict)

    # Step 5 — determine final signal
    if fr_result["fired"]:
        final_result = fr_result["result"]
        final_source = "frontrunners"
        # FTLT was evaluated but is not the source of the signal
        ftlt_result["fired"] = False
    else:
        final_result = ftlt_result["result"]
        final_source = "ftlt"

    # Step 6 — build indicators summary
    window = 10  # RSI window for all NUTS conditions
    indicators = _build_indicators(prices_dict, window)

    # Step 7 — assemble response
    payload = {
        "cache_hit": False,
        "frontrunners": fr_result,
        "ftlt": ftlt_result,
        "blackswan": blackswan_result,
        "final_result": final_result,
        "final_source": final_source,
        "indicators": indicators,
        "data_quality": data_quality,
        "download_errors": download_errors,
        "unit_test": unit,
    }

    # Step 8 — cache and return
    saved = write_state(payload)
    return _response(200, saved)


def _build_indicators(prices_dict: dict, window: int) -> dict:
    """Build a flat dict of every computed indicator for the sidebar."""
    ind: dict = {}

    rsi_tickers = [
        "SPY", "QQQ", "VTV", "VOX", "XLK", "XLP", "XLF",
        "SOXX", "TQQQ", "SPXL", "SQQQ", "TLT",
    ]
    for ticker in rsi_tickers:
        if ticker in prices_dict:
            rsi_val = calculate_rsi_sma(prices_dict[ticker], window)
            ind[f"{ticker}_RSI_{window}"] = round(rsi_val, 2)

    # SPY vs 200d MA
    if "SPY" in prices_dict:
        spy_price = current_price(prices_dict["SPY"])
        spy_200ma = moving_average_price(prices_dict["SPY"], 200)
        ind["SPY_price"] = round(spy_price, 2)
        ind["SPY_vs_200MA"] = spy_price > spy_200ma
        ind["SPY_200MA_value"] = round(spy_200ma, 2)

    # TQQQ vs 20d MA
    if "TQQQ" in prices_dict:
        tqqq_price = current_price(prices_dict["TQQQ"])
        tqqq_20ma = moving_average_price(prices_dict["TQQQ"], 20)
        ind["TQQQ_price"] = round(tqqq_price, 2)
        ind["TQQQ_vs_20MA"] = tqqq_price > tqqq_20ma
        ind["TQQQ_20MA_value"] = round(tqqq_20ma, 2)

    return ind


# ─────────────────────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    print(f"[lambda_handler] event={json.dumps(event)}")

    # Handle CORS preflight
    http_method = (
        event.get("requestContext", {}).get("http", {}).get("method", "")
        or event.get("httpMethod", "")
    )
    if http_method == "OPTIONS":
        return _response(200, {})

    # Route
    raw_path = (
        event.get("requestContext", {}).get("http", {}).get("path", "")
        or event.get("path", "")
        or event.get("rawPath", "")
        or "/"
    )
    query_params = event.get("queryStringParameters") or {}

    path = raw_path.rstrip("/")

    if path == "/test-rsi":
        return handle_test_rsi()

    if path == "/evaluate":
        force = str(query_params.get("force", "false")).lower() == "true"
        return handle_evaluate(force=force)

    return _error(404, f"Unknown route: {raw_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Local dev runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    route = sys.argv[1] if len(sys.argv) > 1 else "/evaluate"
    force = "--force" in sys.argv

    if route == "/test-rsi":
        event = {"rawPath": "/test-rsi", "requestContext": {"http": {"method": "GET", "path": "/test-rsi"}}}
    else:
        event = {
            "rawPath": "/evaluate",
            "requestContext": {"http": {"method": "GET", "path": "/evaluate"}},
            "queryStringParameters": {"force": "true"} if force else {},
        }

    result = lambda_handler(event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
