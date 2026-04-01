"""
NUTS Algo — Branch 2: TQQQ For the Long Term (FTLT).

Always evaluated, even when Frontrunners fires.
When Frontrunners fires, FTLT result is computed but fired=False
in the top-level response.

Tree structure:
  GATE: SPY price > SPY MA(200)?

  Bull regime (GATE = True):
    B1: TQQQ RSI(10) > 79?  YES → UVXY
    B2: SPXL RSI(10) > 80?  YES → UVXY  NO → TQQQ ✓

  Bear regime (GATE = False):
    B3: TQQQ RSI(10) < 31?  YES → TECL
    B4: SPY  RSI(10) < 30?  YES → UPRO
    B5: TQQQ price < TQQQ MA(20)?  YES → rsi_filter(SQQQ, TLT)
    B6: SQQQ RSI(10) < 31?  YES → SQQQ  NO → TQQQ ✓

All nodes (active AND inactive) are included in the response.
"""

import sys
import os
from typing import Optional
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations import (
    calculate_rsi_sma,
    moving_average_price,
    current_price,
    rsi_filter,
)

# ─────────────────────────────────────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────────────────────────────────────

THRESHOLDS = {
    "RSI_WINDOW": 10,
    "SPY_MA_WINDOW":   200,
    "TQQQ_MA_WINDOW":  20,
    "TQQQ_RSI_HIGH_BULL": 79,   # B1
    "SPXL_RSI_HIGH_BULL": 80,   # B2
    "TQQQ_RSI_LOW_BEAR":  31,   # B3
    "SPY_RSI_LOW_BEAR":   30,   # B4
    "SQQQ_RSI_LOW_BEAR":  31,   # B6
    "CLOSE_CALL_DISTANCE": 5,
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _eval_op(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    raise ValueError(f"Unknown operator: {operator}")


def _leaf(node_id: str, outcome: str, active: bool, regime: Optional[str] = None) -> dict:
    node = {
        "id": node_id,
        "label": f"→ {outcome}",
        "ticker": None,
        "indicator": None,
        "window": None,
        "operator": None,
        "threshold": None,
        "live_value": None,
        "distance": None,
        "result": True,
        "active": active,
        "close_call": False,
        "outcome": outcome,
        "is_leaf": True,
    }
    if regime:
        node["regime"] = regime
    return node


def _rsi_node(
    node_id: str, ticker: str, live_rsi: float, operator: str,
    threshold: float, outcome: str, active: bool, regime: str
) -> dict:
    window = THRESHOLDS["RSI_WINDOW"]
    distance = live_rsi - threshold
    return {
        "id": node_id,
        "label": f"{ticker} RSI({window}) {operator} {threshold}",
        "ticker": ticker,
        "indicator": "RSI",
        "window": window,
        "operator": operator,
        "threshold": threshold,
        "live_value": round(live_rsi, 2),
        "distance": round(distance, 2),
        "result": _eval_op(live_rsi, operator, threshold),
        "active": active,
        "close_call": abs(distance) <= THRESHOLDS["CLOSE_CALL_DISTANCE"],
        "outcome": outcome,
        "regime": regime,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tree evaluator
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_ftlt(prices_dict: dict) -> dict:
    """
    Evaluate the FTLT decision tree.

    Args:
        prices_dict: {ticker: np.ndarray}

    Returns:
        {
            "fired": True,          FTLT always returns fired=True
            "result": str,
            "active_path": [ids],
            "nodes": [...],         ALL nodes (active + inactive)
        }
    """
    window = THRESHOLDS["RSI_WINDOW"]
    ccd = THRESHOLDS["CLOSE_CALL_DISTANCE"]

    # ── Pre-compute ALL indicator values ──────────────────────────────────────
    spy_prices  = prices_dict["SPY"]
    tqqq_prices = prices_dict["TQQQ"]
    spxl_prices = prices_dict["SPXL"]
    sqqq_prices = prices_dict["SQQQ"]
    tlt_prices  = prices_dict["TLT"]

    spy_current  = current_price(spy_prices)
    spy_200ma    = moving_average_price(spy_prices, THRESHOLDS["SPY_MA_WINDOW"])
    tqqq_rsi     = calculate_rsi_sma(tqqq_prices, window)
    spxl_rsi     = calculate_rsi_sma(spxl_prices, window)
    spy_rsi      = calculate_rsi_sma(spy_prices, window)
    tqqq_ma20    = moving_average_price(tqqq_prices, THRESHOLDS["TQQQ_MA_WINDOW"])
    tqqq_current = current_price(tqqq_prices)
    sqqq_rsi     = calculate_rsi_sma(sqqq_prices, window)
    tlt_rsi      = calculate_rsi_sma(tlt_prices, window)

    filter_winner, filter_rsi_vals = rsi_filter(
        {"SQQQ": sqqq_prices, "TLT": tlt_prices}, window
    )

    # ── Gate ──────────────────────────────────────────────────────────────────
    gate_result  = spy_current > spy_200ma
    gate_distance = spy_current - spy_200ma

    # ── Determine active path ─────────────────────────────────────────────────
    active_set: set[str] = {"gate_spy_200ma"}
    result: Optional[str] = None

    if gate_result:
        # Bull regime
        active_set.add("b1_tqqq_rsi_high")
        if tqqq_rsi > THRESHOLDS["TQQQ_RSI_HIGH_BULL"]:
            result = "UVXY"
            active_set.add("leaf_uvxy_b1")
        else:
            active_set.add("b2_spxl_rsi_high")
            if spxl_rsi > THRESHOLDS["SPXL_RSI_HIGH_BULL"]:
                result = "UVXY"
                active_set.add("leaf_uvxy_b2")
            else:
                result = "TQQQ"
                active_set.add("leaf_tqqq_bull")
    else:
        # Bear regime
        active_set.add("b3_tqqq_rsi_low")
        if tqqq_rsi < THRESHOLDS["TQQQ_RSI_LOW_BEAR"]:
            result = "TECL"
            active_set.add("leaf_tecl")
        else:
            active_set.add("b4_spy_rsi_low")
            if spy_rsi < THRESHOLDS["SPY_RSI_LOW_BEAR"]:
                result = "UPRO"
                active_set.add("leaf_upro")
            else:
                active_set.add("b5_tqqq_vs_ma20")
                if tqqq_current < tqqq_ma20:
                    result = filter_winner
                    # Add the winning leaf as active; the other will be inactive
                    active_set.add(f"leaf_{filter_winner.lower()}_filter")
                else:
                    active_set.add("b6_sqqq_rsi_low")
                    if sqqq_rsi < THRESHOLDS["SQQQ_RSI_LOW_BEAR"]:
                        result = "SQQQ"
                        active_set.add("leaf_sqqq")
                    else:
                        result = "TQQQ"
                        active_set.add("leaf_tqqq_bear")

    # ── Build ordered active_path ─────────────────────────────────────────────
    # Keep logical traversal order for the UI
    _all_ids_ordered = [
        "gate_spy_200ma",
        # Bull branch
        "b1_tqqq_rsi_high", "leaf_uvxy_b1",
        "b2_spxl_rsi_high", "leaf_uvxy_b2", "leaf_tqqq_bull",
        # Bear branch
        "b3_tqqq_rsi_low", "leaf_tecl",
        "b4_spy_rsi_low", "leaf_upro",
        "b5_tqqq_vs_ma20", "leaf_sqqq_filter", "leaf_tlt_filter",
        "b6_sqqq_rsi_low", "leaf_sqqq", "leaf_tqqq_bear",
    ]
    active_path = [nid for nid in _all_ids_ordered if nid in active_set]

    # ── Build ALL nodes ───────────────────────────────────────────────────────
    nodes: list[dict] = []

    # Gate node (SPY vs 200d MA)
    nodes.append({
        "id": "gate_spy_200ma",
        "label": "SPY vs 200d MA",
        "ticker": "SPY",
        "indicator": "MA",
        "window": THRESHOLDS["SPY_MA_WINDOW"],
        "operator": ">",
        "threshold": round(spy_200ma, 2),
        "live_value": round(spy_current, 2),
        "distance": round(gate_distance, 2),
        "result": gate_result,
        "active": "gate_spy_200ma" in active_set,
        "close_call": abs(gate_distance) <= ccd,
        "outcome": None,
        "display_type": "ma_gate",
        "ma_value": round(spy_200ma, 2),
        "price_value": round(spy_current, 2),
    })

    # ── Bull branch nodes ─────────────────────────────────────────────────────
    nodes.append(_rsi_node(
        "b1_tqqq_rsi_high", "TQQQ", tqqq_rsi, ">",
        THRESHOLDS["TQQQ_RSI_HIGH_BULL"], "UVXY",
        "b1_tqqq_rsi_high" in active_set, "bull"
    ))
    nodes.append(_leaf("leaf_uvxy_b1", "UVXY", "leaf_uvxy_b1" in active_set, "bull"))

    nodes.append(_rsi_node(
        "b2_spxl_rsi_high", "SPXL", spxl_rsi, ">",
        THRESHOLDS["SPXL_RSI_HIGH_BULL"], "UVXY",
        "b2_spxl_rsi_high" in active_set, "bull"
    ))
    nodes.append(_leaf("leaf_uvxy_b2", "UVXY", "leaf_uvxy_b2" in active_set, "bull"))
    nodes.append(_leaf("leaf_tqqq_bull", "TQQQ", "leaf_tqqq_bull" in active_set, "bull"))

    # ── Bear branch nodes ─────────────────────────────────────────────────────
    nodes.append(_rsi_node(
        "b3_tqqq_rsi_low", "TQQQ", tqqq_rsi, "<",
        THRESHOLDS["TQQQ_RSI_LOW_BEAR"], "TECL",
        "b3_tqqq_rsi_low" in active_set, "bear"
    ))
    nodes.append(_leaf("leaf_tecl", "TECL", "leaf_tecl" in active_set, "bear"))

    nodes.append(_rsi_node(
        "b4_spy_rsi_low", "SPY", spy_rsi, "<",
        THRESHOLDS["SPY_RSI_LOW_BEAR"], "UPRO",
        "b4_spy_rsi_low" in active_set, "bear"
    ))
    nodes.append(_leaf("leaf_upro", "UPRO", "leaf_upro" in active_set, "bear"))

    # B5: TQQQ price vs MA(20)
    b5_distance = tqqq_current - tqqq_ma20
    nodes.append({
        "id": "b5_tqqq_vs_ma20",
        "label": "TQQQ price < TQQQ MA(20)",
        "ticker": "TQQQ",
        "indicator": "MA",
        "window": THRESHOLDS["TQQQ_MA_WINDOW"],
        "operator": "<",
        "threshold": round(tqqq_ma20, 2),
        "live_value": round(tqqq_current, 2),
        "distance": round(b5_distance, 2),
        "result": tqqq_current < tqqq_ma20,
        "active": "b5_tqqq_vs_ma20" in active_set,
        "close_call": abs(b5_distance) <= ccd,
        "outcome": filter_winner,
        "display_type": "ma_gate",
        "ma_value": round(tqqq_ma20, 2),
        "price_value": round(tqqq_current, 2),
        "regime": "bear",
    })

    # B5 leaves: two candidates — winner is active, loser is dimmed
    _b5_label = (
        f"SQQQ {filter_rsi_vals['SQQQ']:.2f} vs "
        f"TLT {filter_rsi_vals['TLT']:.2f} — {filter_winner} wins (higher RSI)"
    )
    _b5_filter_details = {
        "SQQQ_RSI": round(filter_rsi_vals["SQQQ"], 2),
        "TLT_RSI": round(filter_rsi_vals["TLT"], 2),
        "winner": filter_winner,
    }
    for _cand in ("SQQQ", "TLT"):
        _leaf_id = f"leaf_{_cand.lower()}_filter"
        _is_winner = (_cand == filter_winner)
        nodes.append({
            "id": _leaf_id,
            "label": f"→ {_cand}",
            "ticker": None,
            "indicator": "RSI_FILTER",
            "window": window,
            "operator": None,
            "threshold": None,
            "live_value": None,
            "distance": None,
            "result": _is_winner,
            "active": _leaf_id in active_set,
            "close_call": False,
            "outcome": _cand,
            "is_leaf": True,
            "regime": "bear",
            "filter_details": _b5_filter_details,
        })

    nodes.append(_rsi_node(
        "b6_sqqq_rsi_low", "SQQQ", sqqq_rsi, "<",
        THRESHOLDS["SQQQ_RSI_LOW_BEAR"], "SQQQ",
        "b6_sqqq_rsi_low" in active_set, "bear"
    ))
    nodes.append(_leaf("leaf_sqqq", "SQQQ", "leaf_sqqq" in active_set, "bear"))
    nodes.append(_leaf("leaf_tqqq_bear", "TQQQ", "leaf_tqqq_bear" in active_set, "bear"))

    return {
        "fired": True,   # FTLT is always evaluated
        "result": result,
        "active_path": active_path,
        "nodes": nodes,
    }
