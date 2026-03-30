"""
NUTS Algo — State / cache manager.

Stores the last /evaluate result in S3 (production) or a local JSON file
(local dev).  S3 is the source of truth; the Lambda /tmp cache is gone.

S3 layout:
    s3://nuts-algo-data/cache/latest_evaluation.json

Cache TTL is checked on read: stale entries return None, triggering a fresh
compute.  The EventBridge "compute" action bypasses the TTL entirely.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import boto3
import numpy as np
import pytz
from botocore.exceptions import ClientError


# ─────────────────────────────────────────────────────────────────────────────
# JSON encoder — handles numpy scalars / arrays that live inside the payload
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

CACHE_TTL_MINUTES = 60
EASTERN = pytz.timezone("US/Eastern")

S3_BUCKET = "nuts-algo-data"
CACHE_KEY  = "cache/latest_evaluation.json"

# Detect Lambda environment
_IS_LAMBDA   = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
_LOCAL_PATH  = "./nuts_cache_local.json"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _s3_client():
    """Return a boto3 S3 client (lazy, so local tests don't need AWS creds)."""
    return boto3.client("s3")


def _is_fresh(state: dict) -> bool:
    """Return True if the cached state is younger than CACHE_TTL_MINUTES."""
    cached_at_str = state.get("_cached_at_utc")
    if not cached_at_str:
        return False
    try:
        cached_at = datetime.fromisoformat(cached_at_str).replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - cached_at).total_seconds() / 60
        return age_minutes < CACHE_TTL_MINUTES
    except (ValueError, TypeError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def read_state() -> Optional[dict]:
    """
    Return the cached evaluation result if it exists and is fresh.

    In Lambda: reads from S3.
    Locally:   reads from ./nuts_cache_local.json.

    Returns None if the object doesn't exist, is malformed, or is stale.
    """
    if _IS_LAMBDA:
        return _read_s3()
    return _read_local()


def write_state(result: dict) -> dict:
    """
    Persist the evaluation result.

    Stamps _cached_at_utc (UTC ISO) and evaluated_at (Eastern ISO) onto the
    dict, serialises with _NumpyEncoder, and writes to S3 (Lambda) or the
    local file.

    Returns the enriched dict that was written.
    """
    now_utc = datetime.now(timezone.utc)
    now_et  = now_utc.astimezone(EASTERN)

    result["_cached_at_utc"] = now_utc.isoformat()
    result["evaluated_at"]   = now_et.strftime("%Y-%m-%dT%H:%M:%S%z")

    if _IS_LAMBDA:
        _write_s3(result)
    else:
        _write_local(result)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# S3 backend
# ─────────────────────────────────────────────────────────────────────────────

def _read_s3() -> Optional[dict]:
    try:
        s3 = _s3_client()
        response = s3.get_object(Bucket=S3_BUCKET, Key=CACHE_KEY)
        body = response["Body"].read().decode("utf-8")
        state = json.loads(body)
        if _is_fresh(state):
            return state
        print(f"[state_manager] S3 cache stale — will recompute")
        return None
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NoSuchKey", "404"):
            print("[state_manager] S3 cache not found — cold start")
            return None
        print(f"[state_manager] S3 get_object error ({error_code}): {exc}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"[state_manager] S3 cache parse error: {exc}")
        return None


def _write_s3(result: dict) -> None:
    try:
        body = json.dumps(result, cls=_NumpyEncoder)
        s3   = _s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=CACHE_KEY,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        print(f"[state_manager] Written to s3://{S3_BUCKET}/{CACHE_KEY}")
    except ClientError as exc:
        print(f"[state_manager] Warning: S3 put_object failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Local (dev) backend
# ─────────────────────────────────────────────────────────────────────────────

def _read_local() -> Optional[dict]:
    try:
        with open(_LOCAL_PATH, "r") as f:
            state = json.load(f)
        if _is_fresh(state):
            return state
        return None
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return None


def _write_local(result: dict) -> None:
    try:
        with open(_LOCAL_PATH, "w") as f:
            json.dump(result, f, cls=_NumpyEncoder)
    except OSError as exc:
        print(f"[state_manager] Warning: could not write local cache: {exc}")
