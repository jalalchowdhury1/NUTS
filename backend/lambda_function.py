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

from calculations import run_unit_test, calculate_rsi_sma, moving_average_price, current_price, cumulative_return, max_drawdown
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


def _build_indicators(prices_dict: dict, window: int) -> list:
    """Build a comprehensive list of all tickers and their algorithm metrics for the global frontend table."""
    market_data = []

    def _safe(func, *args):
        try:
            val = func(*args)
            return round(val, 2) if val is not None else None
        except Exception:
            return None

    for ticker, prices in prices_dict.items():
        if len(prices) == 0:
            continue
            
        current = current_price(prices)
        rsi_10 = _safe(calculate_rsi_sma, prices, 10)
            
        ticker_data = {
            "ticker": ticker,
            "price": round(current, 2),
            "rsi_10": rsi_10,
            "extras": {}
        }
        
        # ── Attach specific BlackSwan / FTLT / FR indicators ──
        if ticker == "SPY":
            ticker_data["extras"]["MA(40)"] = _safe(moving_average_price, prices, 40)
            ticker_data["extras"]["MA(200)"] = _safe(moving_average_price, prices, 200)
            ticker_data["extras"]["RSI(45)"] = _safe(calculate_rsi_sma, prices, 45)
            ticker_data["extras"]["RSI(60)"] = _safe(calculate_rsi_sma, prices, 60)
            ticker_data["extras"]["MaxDD(21d)"] = f"{_safe(max_drawdown, prices, 21)}%"
            ticker_data["extras"]["MaxDD(180d)"] = f"{_safe(max_drawdown, prices, 180)}%"
        elif ticker == "TQQQ":
            ticker_data["extras"]["MA(20)"] = _safe(moving_average_price, prices, 20)
            ticker_data["extras"]["CumRet(1d)"] = f"{_safe(cumulative_return, prices, 1)}%"
            ticker_data["extras"]["CumRet(6d)"] = f"{_safe(cumulative_return, prices, 6)}%"
        elif ticker == "QQQ":
            ticker_data["extras"]["MA(25)"] = _safe(moving_average_price, prices, 25)
            ticker_data["extras"]["MaxDD(10d)"] = f"{_safe(max_drawdown, prices, 10)}%"
        elif ticker == "TLT":
            ticker_data["extras"]["RSI(200)"] = _safe(calculate_rsi_sma, prices, 200)
        elif ticker == "IEF":
            ticker_data["extras"]["RSI(200)"] = _safe(calculate_rsi_sma, prices, 200)
        elif ticker == "BND":
            ticker_data["extras"]["RSI(45)"] = _safe(calculate_rsi_sma, prices, 45)
            ticker_data["extras"]["CumRet(60d)"] = f"{_safe(cumulative_return, prices, 60)}%"
        elif ticker == "BIL":
            ticker_data["extras"]["CumRet(60d)"] = f"{_safe(cumulative_return, prices, 60)}%"
        elif ticker == "SH":
            ticker_data["extras"]["CumRet(10d)"] = f"{_safe(cumulative_return, prices, 10)}%"
        elif ticker == "TMF":
            ticker_data["extras"]["MaxDD(10d)"] = f"{_safe(max_drawdown, prices, 10)}%"
            
        market_data.append(ticker_data)
        
    return sorted(market_data, key=lambda x: x["ticker"])


# ─────────────────────────────────────────────────────────────────────────────
# EventBridge scheduled-event handlers
# ─────────────────────────────────────────────────────────────────────────────

def handle_scheduled_compute() -> dict:
    """
    Called by the EventBridge 30-minute cron (action='compute').

    Forces a fresh evaluation regardless of cache age and writes the result
    back to S3.  Returns a lightweight status dict (not an API Gateway response
    envelope) because EventBridge doesn't use one.
    """
    print("[lambda_handler] EventBridge action=compute — forcing fresh evaluation")
    response = handle_evaluate(force=True)
    status = "ok" if response["statusCode"] == 200 else "error"
    print(f"[lambda_handler] Scheduled compute finished — status={status}")
    return {"status": status, "statusCode": response["statusCode"]}


def handle_scheduled_update_prices() -> dict:
    """
    Called by the EventBridge daily cron (action='update_prices').

    Imports data_manager at call-time so the module is only loaded when this
    action is actually invoked (keeps cold-start overhead minimal for the
    normal API path).
    """
    print("[lambda_handler] EventBridge action=update_prices — updating daily prices")
    try:
        from data_manager import update_daily
        from data_fetcher import ALL_TICKERS

        errors = []
        for ticker in ALL_TICKERS:
            try:
                update_daily(ticker)
            except Exception as exc:
                errors.append({"ticker": ticker, "error": str(exc)})
                print(f"[lambda_handler] update_daily({ticker}) failed: {exc}")

        status = "ok" if not errors else "partial"
        print(f"[lambda_handler] Price update done — status={status}, errors={len(errors)}")
        return {"status": status, "errors": errors}
    except Exception as exc:
        print(f"[lambda_handler] update_prices fatal error: {exc}")
        return {"status": "error", "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    print(f"[lambda_handler] event={json.dumps(event)}")

    # ── EventBridge scheduled events ─────────────────────────────────────────
    # EventBridge delivers a plain dict with an "action" key; it has no
    # requestContext, httpMethod, or path fields.
    action = event.get("action")
    if action == "compute":
        return handle_scheduled_compute()
    if action == "update_prices":
        return handle_scheduled_update_prices()

    # ── API Gateway HTTP API ──────────────────────────────────────────────────

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
