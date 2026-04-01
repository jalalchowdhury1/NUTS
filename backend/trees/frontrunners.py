"""
NUTS Algo — Branch 1: Frontrunners decision tree.

Traverse top-to-bottom. First TRUE condition fires immediately.
If no condition fires → FTLT branch takes over (fired=False).

All thresholds are defined in THRESHOLDS — never hardcoded inline.
RSI window = 10 everywhere.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from calculations import calculate_rsi_sma


# ─────────────────────────────────────────────────────────────────────────────
# Thresholds — single source of truth
# ─────────────────────────────────────────────────────────────────────────────

THRESHOLDS = {
    "RSI_WINDOW": 10,
    "SPY_RSI_HIGH":  80,   # Node 1  → UVXY
    "QQQ_RSI_HIGH":  79,   # Node 2  → VIXY
    "VTV_RSI_HIGH":  79,   # Node 3  → VIXY
    "VOX_RSI_HIGH":  84,   # Node 4  → VIXY  ← 84, not 79
    "XLK_RSI_HIGH":  79,   # Node 5  → VIXY
    "XLP_RSI_HIGH":  75,   # Node 6  → VIXY
    "XLF_RSI_HIGH":  80,   # Node 7  → VIXY
    "SOXX_RSI_LOW":  30,   # Node 8  → SOXL
    "QQQ_RSI_LOW":   30,   # Node 9  → TECL
    "SPY_RSI_LOW":   30,   # Node 10 → UPRO
    "CLOSE_CALL_DISTANCE": 5,
}

# ─────────────────────────────────────────────────────────────────────────────
# Node definitions (ordered — first TRUE wins)
# ─────────────────────────────────────────────────────────────────────────────

NODE_DEFS = [
    {"id": "fr_node_1",  "ticker": "SPY",  "operator": ">", "threshold_key": "SPY_RSI_HIGH",  "outcome": "UVXY"},
    {"id": "fr_node_2",  "ticker": "QQQ",  "operator": ">", "threshold_key": "QQQ_RSI_HIGH",  "outcome": "VIXY"},
    {"id": "fr_node_3",  "ticker": "VTV",  "operator": ">", "threshold_key": "VTV_RSI_HIGH",  "outcome": "VIXY"},
    {"id": "fr_node_4",  "ticker": "VOX",  "operator": ">", "threshold_key": "VOX_RSI_HIGH",  "outcome": "VIXY"},
    {"id": "fr_node_5",  "ticker": "XLK",  "operator": ">", "threshold_key": "XLK_RSI_HIGH",  "outcome": "VIXY"},
    {"id": "fr_node_6",  "ticker": "XLP",  "operator": ">", "threshold_key": "XLP_RSI_HIGH",  "outcome": "VIXY"},
    {"id": "fr_node_7",  "ticker": "XLF",  "operator": ">", "threshold_key": "XLF_RSI_HIGH",  "outcome": "VIXY"},
    {"id": "fr_node_8",  "ticker": "SOXX", "operator": "<", "threshold_key": "SOXX_RSI_LOW",  "outcome": "SOXL"},
    {"id": "fr_node_9",  "ticker": "QQQ",  "operator": "<", "threshold_key": "QQQ_RSI_LOW",   "outcome": "TECL"},
    {"id": "fr_node_10", "ticker": "SPY",  "operator": "<", "threshold_key": "SPY_RSI_LOW",   "outcome": "UPRO"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _eval_op(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    raise ValueError(f"Unknown operator: {operator}")


# ─────────────────────────────────────────────────────────────────────────────
# Tree evaluator
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_frontrunners(prices_dict: dict) -> dict:
    """
    Evaluate the Frontrunners decision tree.

    Args:
        prices_dict: {ticker: np.ndarray of closing prices}

    Returns:
        {
            "fired": bool,           True if a condition fired
            "result": str,           ticker outcome or "→ FTLT"
            "active_path": [ids],    ordered traversal path
            "nodes": [...],          ALL nodes with live values
        }
    """
    window = THRESHOLDS["RSI_WINDOW"]
    close_call_dist = THRESHOLDS["CLOSE_CALL_DISTANCE"]

    # Pre-compute RSI for every ticker referenced in NODE_DEFS
    rsi_cache: dict[str, float] = {}
    seen_tickers = {nd["ticker"] for nd in NODE_DEFS}
    for ticker in seen_tickers:
        rsi_cache[ticker] = calculate_rsi_sma(prices_dict[ticker], window)

    active_path: list[str] = []
    cond_nodes: list[dict] = []   # condition nodes only (for leaf generation pass)
    result: Optional[str] = None
    fired: bool = False
    fired_node_id: Optional[str] = None

    for nd in NODE_DEFS:
        ticker = nd["ticker"]
        threshold = THRESHOLDS[nd["threshold_key"]]
        operator = nd["operator"]
        live_rsi = rsi_cache[ticker]
        distance = live_rsi - threshold
        cond_result = _eval_op(live_rsi, operator, threshold)

        is_on_active_path = not fired  # we traverse until something fires

        node = {
            "id": nd["id"],
            "label": f"{ticker} RSI({window}) {operator} {threshold}",
            "ticker": ticker,
            "indicator": "RSI",
            "window": window,
            "operator": operator,
            "threshold": threshold,
            "live_value": round(live_rsi, 2),
            "distance": round(distance, 2),
            "result": cond_result,
            "active": is_on_active_path,
            "close_call": abs(distance) <= close_call_dist,
            "outcome": nd["outcome"],
        }
        cond_nodes.append(node)

        if is_on_active_path:
            active_path.append(nd["id"])

        if not fired and cond_result:
            result = nd["outcome"]
            fired = True
            fired_node_id = nd["id"]
            active_path.append(f"leaf_{nd['id']}")

    # Build the final nodes list: all condition nodes first, then ALL leaf nodes
    # (active=True only for the fired leaf, so inactive leaves render dimmed)
    nodes: list[dict] = list(cond_nodes)
    for nd in NODE_DEFS:
        leaf_id = f"leaf_{nd['id']}"
        is_active_leaf = (leaf_id in active_path)
        nodes.append({
            "id": leaf_id,
            "label": f"→ {nd['outcome']}",
            "ticker": None,
            "indicator": None,
            "window": None,
            "operator": None,
            "threshold": None,
            "live_value": None,
            "distance": None,
            "result": is_active_leaf,
            "active": is_active_leaf,
            "close_call": False,
            "outcome": nd["outcome"],
            "is_leaf": True,
        })

    if not fired:
        # Default: no condition fired → hand off to FTLT
        result = "→ FTLT"
        default_id = "fr_default"
        nodes.append({
            "id": default_id,
            "label": "No condition fired → FTLT",
            "ticker": None,
            "indicator": None,
            "window": None,
            "operator": None,
            "threshold": None,
            "live_value": None,
            "distance": None,
            "result": True,
            "active": True,
            "close_call": False,
            "outcome": "→ FTLT",
            "is_leaf": True,
        })
        active_path.append(default_id)

    return {
        "fired": fired,
        "result": result,
        "active_path": active_path,
        "nodes": nodes,
    }
