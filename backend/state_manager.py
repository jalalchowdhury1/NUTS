"""
NUTS Algo — State / cache manager.

Adapted from trading-algorithm/state_manager.py pattern.

Stores the last /evaluate result in /tmp/nuts_cache.json (Lambda)
or ./nuts_cache_local.json (local dev).

Cache is valid for CACHE_TTL_MINUTES minutes.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

import pytz

CACHE_TTL_MINUTES = 60
EASTERN = pytz.timezone("US/Eastern")

# Detect Lambda environment
_IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
_CACHE_PATH = "/tmp/nuts_cache.json" if _IS_LAMBDA else "./nuts_cache_local.json"


def read_state() -> Optional[dict]:
    """
    Read cached evaluation result.

    Returns the cached dict if it exists and is fresher than CACHE_TTL_MINUTES,
    otherwise returns None.
    """
    try:
        with open(_CACHE_PATH, "r") as f:
            state = json.load(f)

        cached_at_str = state.get("_cached_at_utc")
        if not cached_at_str:
            return None

        cached_at = datetime.fromisoformat(cached_at_str).replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - cached_at).total_seconds() / 60

        if age_minutes < CACHE_TTL_MINUTES:
            return state
        return None  # stale

    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return None


def write_state(result: dict) -> dict:
    """
    Write evaluation result to cache.

    Adds _cached_at_utc (ISO string) and evaluated_at (Eastern time ISO string).
    Returns the enriched dict that was written.
    """
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(EASTERN)

    result["_cached_at_utc"] = now_utc.isoformat()
    result["evaluated_at"] = now_et.strftime("%Y-%m-%dT%H:%M:%S%z")

    try:
        with open(_CACHE_PATH, "w") as f:
            json.dump(result, f, cls=_NumpyEncoder)
    except OSError as exc:
        print(f"[state_manager] Warning: could not write cache to {_CACHE_PATH}: {exc}")

    return result
