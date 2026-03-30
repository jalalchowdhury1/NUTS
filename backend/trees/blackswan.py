"""
NUTS Algo — Branch 3: BlackSwan / MeanRev / BondSignal.

Gate 1: TQQQ RSI(10) > 79 → UVXY (gate closes the tree)
Otherwise: Gate 2: TQQQ 6d cumulative return < -13%
  YES (Huge Volatility): Only Black Swan logic evaluated
  NO (Normal Market): Only NMA & NMB vote; NMA wins tiebreak
fired is always True.
"""

import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations import (
    calculate_rsi_sma,
    moving_average_price,
    current_price,
    cumulative_return,
    max_drawdown,
)

CLOSE_CALL_DISTANCE = 5


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _eval(value, operator, threshold):
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    raise ValueError(f"Unknown operator: {operator}")


def _leaf(node_id, outcome, active, subpath=None):
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
    if subpath:
        node["subpath"] = subpath
    return node


def _node(node_id, label, ticker, indicator, window, operator, threshold,
          live_value, active, outcome=None, subpath=None):
    distance = live_value - threshold
    node = {
        "id": node_id,
        "label": label,
        "ticker": ticker,
        "indicator": indicator,
        "window": window,
        "operator": operator,
        "threshold": round(threshold, 4),
        "live_value": round(live_value, 4),
        "distance": round(distance, 4),
        "result": bool(_eval(live_value, operator, threshold)),
        "active": active,
        "close_call": abs(distance) <= CLOSE_CALL_DISTANCE,
        "outcome": outcome,
    }
    if subpath:
        node["subpath"] = subpath
    return node


def _ma_node(node_id, label, ticker, window, operator, price_val, ma_val,
             active, outcome=None, subpath=None):
    distance = price_val - ma_val
    node = {
        "id": node_id,
        "label": label,
        "ticker": ticker,
        "indicator": "MA",
        "window": window,
        "operator": operator,
        "threshold": round(ma_val, 4),
        "live_value": round(price_val, 4),
        "distance": round(distance, 4),
        "result": bool(_eval(price_val, operator, ma_val)),
        "active": active,
        "close_call": abs(distance) <= CLOSE_CALL_DISTANCE,
        "outcome": outcome,
        "display_type": "ma_gate",
        "ma_value": round(ma_val, 4),
        "price_value": round(price_val, 4),
    }
    if subpath:
        node["subpath"] = subpath
    return node


# ─────────────────────────────────────────────────────────────────────────────
# Tree evaluator
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_blackswan(prices_dict: dict) -> dict:
    """
    Evaluate the BlackSwan decision tree.

    Args:
        prices_dict: {ticker: list/np.ndarray of closing prices}

    Returns:
        {
            "fired": True,
            "result": str,
            "active_path": [ids],
            "nodes": [...],          # ALL nodes (active + inactive)
            "sub_results": {...},    # BS / NMA / NMB votes
        }
    """
    # ── Pull price arrays ──────────────────────────────────────────────────────
    tqqq = prices_dict["TQQQ"]
    qqq  = prices_dict["QQQ"]
    spy  = prices_dict["SPY"]
    sh   = prices_dict["SH"]
    tmf  = prices_dict["TMF"]
    bnd  = prices_dict["BND"]
    bil  = prices_dict["BIL"]
    tlt  = prices_dict["TLT"]
    ief  = prices_dict["IEF"]
    vixy = prices_dict["VIXY"]

    # ── Pre-compute all indicators ─────────────────────────────────────────────
    tqqq_rsi10     = calculate_rsi_sma(tqqq, 10)
    tqqq_cumret_6  = cumulative_return(tqqq, 6)
    tqqq_cumret_1  = cumulative_return(tqqq, 1)
    tmf_maxdd_10   = max_drawdown(tmf, 10)
    qqq_maxdd_10   = max_drawdown(qqq, 10)
    sh_cumret_10   = cumulative_return(sh, 10)
    spy_price      = current_price(spy)
    spy_ma40       = moving_average_price(spy, 40)
    ief_rsi200     = calculate_rsi_sma(ief, 200)
    tlt_rsi200     = calculate_rsi_sma(tlt, 200)
    bnd_rsi45      = calculate_rsi_sma(bnd, 45)
    spy_rsi45      = calculate_rsi_sma(spy, 45)
    bnd_cumret_60  = cumulative_return(bnd, 60)
    bil_cumret_60  = cumulative_return(bil, 60)
    spy_maxdd_21   = max_drawdown(spy, 21)
    spy_maxdd_180  = max_drawdown(spy, 180)
    spy_rsi10      = calculate_rsi_sma(spy, 10)
    vixy_rsi10     = calculate_rsi_sma(vixy, 10)
    qqq_price      = current_price(qqq)
    qqq_ma25       = moving_average_price(qqq, 25)
    spy_rsi60      = calculate_rsi_sma(spy, 60)

    # Safe (None → 0.0) values used only for node display when insufficient data
    def _s(v):
        return v if v is not None else 0.0

    # ── GATE: TQQQ RSI(10) > 79 ───────────────────────────────────────────────
    gate_result   = bool(tqqq_rsi10 > 79)
    gate_distance = tqqq_rsi10 - 79
    active_set: set[str] = {"gate_tqqq_rsi"}

    bs_result = nma_result = nmb_result = None
    bs_active: set[str]  = set()
    nma_active: set[str] = set()
    nmb_active: set[str] = set()

    if gate_result:
        active_set.add("leaf_uvxy_gate")
        final_result = "UVXY"

    else:
        # ── GATE 2: Check for Huge Volatility (TQQQ 6d return < -13%) ───────────
        active_set.add("bs1_tqqq_cumret_6d")
        is_huge_vol = (tqqq_cumret_6 is not None and tqqq_cumret_6 < -13)

        if is_huge_vol:
            # ── PATH A: HUGE VOLATILITY (Black Swan Logic Only) ──────────────────
            bs_active = {"bs1_tqqq_cumret_6d"}

            bs_active.add("bs2_tqqq_cumret_1d")
            if tqqq_cumret_1 is not None and tqqq_cumret_1 > 6:
                bs_result = "UVXY"
                bs_active.add("leaf_bs_uvxy")
            else:
                bs_active.add("bs3_tqqq_rsi_low")
                if tqqq_rsi10 < 32:
                    bs_result = "TQQQ"
                    bs_active.add("leaf_bs_tqqq_b3")
                else:
                    bs_active.add("bs4_tmf_maxdd")
                    if tmf_maxdd_10 is not None and tmf_maxdd_10 < 7:
                        bs_result = "TQQQ"
                        bs_active.add("leaf_bs_tqqq_b4")
                    else:
                        bs_result = "BIL"
                        bs_active.add("leaf_bs_bil")

            final_result = bs_result
            active_set |= bs_active
        else:
            # ── PATH B: NORMAL MARKET (NMA & NMB Vote) ─────────────────────────
            # Evaluate NMA
            nma_active = {"nma1_qqq_maxdd"}

            if qqq_maxdd_10 is not None and qqq_maxdd_10 > 6:
                nma_result = "BIL"
                nma_active.add("leaf_nma_bil_1")
            else:
                nma_active.add("nma2_sh_cumret")
                if sh_cumret_10 is not None and sh_cumret_10 > 5:
                    nma_active.add("nma2a_spy_vs_ma40")
                    if spy_price > spy_ma40:
                        nma_result = "URTY"
                        nma_active.add("leaf_nma_urty")
                    else:
                        # → NMA3
                        nma_active.add("nma3_ief_vs_tlt_rsi")
                        if ief_rsi200 < tlt_rsi200:
                            nma_active.add("nma3a_bnd_vs_spy_rsi")
                            if bnd_rsi45 > spy_rsi45:
                                nma_result = "TQQQ"
                                nma_active.add("leaf_nma_tqqq_3a")
                            else:
                                nma_result = "BIL"
                                nma_active.add("leaf_nma_bil_3a")
                        else:
                            nma_result = "BIL"
                            nma_active.add("leaf_nma_bil_3")
                else:
                    # → NMA4
                    nma_active.add("nma4_bnd_vs_bil_cumret")
                    bnd_gt_bil = (bnd_cumret_60 is not None and bil_cumret_60 is not None
                                  and bnd_cumret_60 > bil_cumret_60)
                    if bnd_gt_bil:
                        # → NMA4b
                        nma_active.add("nma4b_spy_maxdd")
                        spy_dd_lt = (spy_maxdd_21 is not None and spy_maxdd_180 is not None
                                     and spy_maxdd_21 < spy_maxdd_180)
                        if spy_dd_lt:
                            nma_active.add("nma4c_spy_rsi_high")
                            if spy_rsi10 > 80:
                                nma_result = "UVXY"
                                nma_active.add("leaf_nma_uvxy")
                            else:
                                nma_active.add("nma5_vixy_rsi")
                                if vixy_rsi10 > 84:
                                    nma_result = "PSQ"
                                    nma_active.add("leaf_nma_psq")
                                else:
                                    nma_result = "TQQQ"
                                    nma_active.add("leaf_nma_tqqq_5")
                        else:
                            # → NMA6
                            nma_active.add("nma6_ief_vs_tlt_rsi")
                            if ief_rsi200 < tlt_rsi200:
                                nma_active.add("nma6a_bnd_vs_spy_rsi")
                                if bnd_rsi45 > spy_rsi45:
                                    nma_result = "TQQQ"
                                    nma_active.add("leaf_nma_tqqq_6a")
                                else:
                                    nma_result = "BIL"
                                    nma_active.add("leaf_nma_bil_6a")
                            else:
                                nma_result = "BIL"
                                nma_active.add("leaf_nma_bil_6")
                    else:
                        # → NMA6
                        nma_active.add("nma6_ief_vs_tlt_rsi")
                        if ief_rsi200 < tlt_rsi200:
                            nma_active.add("nma6a_bnd_vs_spy_rsi")
                            if bnd_rsi45 > spy_rsi45:
                                nma_result = "TQQQ"
                                nma_active.add("leaf_nma_tqqq_6a")
                            else:
                                nma_result = "BIL"
                                nma_active.add("leaf_nma_bil_6a")
                        else:
                            nma_result = "BIL"
                            nma_active.add("leaf_nma_bil_6")

            # Evaluate NMB
            nmb_active = {"nmb1_qqq_maxdd"}

            if qqq_maxdd_10 is not None and qqq_maxdd_10 > 6:
                nmb_result = "BIL"
                nmb_active.add("leaf_nmb_bil_1")
            else:
                nmb_active.add("nmb2_tmf_maxdd")
                if tmf_maxdd_10 is not None and tmf_maxdd_10 > 7:
                    nmb_result = "BIL"
                    nmb_active.add("leaf_nmb_bil_2")
                else:
                    nmb_active.add("nmb3_qqq_vs_ma25")
                    if qqq_price > qqq_ma25:
                        nmb_result = "TQQQ"
                        nmb_active.add("leaf_nmb_tqqq_3")
                    else:
                        nmb_active.add("nmb4_spy_rsi_60")
                        if spy_rsi60 > 50:
                            nmb_active.add("nmb4a_bnd_vs_spy_rsi")
                            if bnd_rsi45 > spy_rsi45:
                                nmb_result = "TQQQ"
                                nmb_active.add("leaf_nmb_tqqq_4a")
                            else:
                                nmb_result = "BIL"
                                nmb_active.add("leaf_nmb_bil_4a")
                        else:
                            nmb_active.add("nmb5_ief_vs_tlt_rsi")
                            if ief_rsi200 < tlt_rsi200:
                                nmb_active.add("nmb5a_bnd_vs_spy_rsi")
                                if bnd_rsi45 > spy_rsi45:
                                    nmb_result = "TQQQ"
                                    nmb_active.add("leaf_nmb_tqqq_5a")
                                else:
                                    nmb_result = "BIL"
                                    nmb_active.add("leaf_nmb_bil_5a")
                            else:
                                nmb_result = "BIL"
                                nmb_active.add("leaf_nmb_bil_5")

            # Vote between NMA and NMB (NMA wins tie)
            if nma_result == nmb_result:
                final_result = nma_result
            else:
                final_result = nma_result

            active_set |= nma_active | nmb_active

    # ── Build ordered active_path ──────────────────────────────────────────────
    _ordered = [
        "gate_tqqq_rsi", "leaf_uvxy_gate",
        # BS
        "bs1_tqqq_cumret_6d", "leaf_bs_tqqq_normal",
        "bs2_tqqq_cumret_1d", "leaf_bs_uvxy",
        "bs3_tqqq_rsi_low", "leaf_bs_tqqq_b3",
        "bs4_tmf_maxdd", "leaf_bs_tqqq_b4", "leaf_bs_bil",
        # NMA
        "nma1_qqq_maxdd", "leaf_nma_bil_1",
        "nma2_sh_cumret",
        "nma2a_spy_vs_ma40", "leaf_nma_urty",
        "nma3_ief_vs_tlt_rsi",
        "nma3a_bnd_vs_spy_rsi", "leaf_nma_tqqq_3a", "leaf_nma_bil_3a",
        "leaf_nma_bil_3",
        "nma4_bnd_vs_bil_cumret",
        "nma4b_spy_maxdd",
        "nma4c_spy_rsi_high", "leaf_nma_uvxy",
        "nma5_vixy_rsi", "leaf_nma_psq", "leaf_nma_tqqq_5",
        "nma6_ief_vs_tlt_rsi",
        "nma6a_bnd_vs_spy_rsi", "leaf_nma_tqqq_6a", "leaf_nma_bil_6a",
        "leaf_nma_bil_6",
        # NMB
        "nmb1_qqq_maxdd", "leaf_nmb_bil_1",
        "nmb2_tmf_maxdd", "leaf_nmb_bil_2",
        "nmb3_qqq_vs_ma25", "leaf_nmb_tqqq_3",
        "nmb4_spy_rsi_60",
        "nmb4a_bnd_vs_spy_rsi", "leaf_nmb_tqqq_4a", "leaf_nmb_bil_4a",
        "nmb5_ief_vs_tlt_rsi",
        "nmb5a_bnd_vs_spy_rsi", "leaf_nmb_tqqq_5a", "leaf_nmb_bil_5a",
        "leaf_nmb_bil_5",
    ]
    active_path = [nid for nid in _ordered if nid in active_set]

    # ── Build ALL nodes (active + inactive) ───────────────────────────────────
    def a(nid):
        return nid in active_set

    nodes = []

    # GATE
    nodes.append({
        "id": "gate_tqqq_rsi",
        "label": "TQQQ RSI(10) > 79",
        "ticker": "TQQQ",
        "indicator": "RSI",
        "window": 10,
        "operator": ">",
        "threshold": 79,
        "live_value": round(tqqq_rsi10, 2),
        "distance": round(gate_distance, 2),
        "result": gate_result,
        "active": a("gate_tqqq_rsi"),
        "close_call": abs(gate_distance) <= CLOSE_CALL_DISTANCE,
        "outcome": "UVXY",
        "fired": gate_result,
        "subpath": "gate",
    })
    nodes.append(_leaf("leaf_uvxy_gate", "UVXY", a("leaf_uvxy_gate"), "gate"))

    # ── BS nodes ──────────────────────────────────────────────────────────────
    nodes.append(_node(
        "bs1_tqqq_cumret_6d", "TQQQ cumulative_return(6d) < -13",
        "TQQQ", "CUM_RET", 6, "<", -13, _s(tqqq_cumret_6),
        a("bs1_tqqq_cumret_6d"), subpath="bs",
    ))
    nodes.append(_leaf("leaf_bs_tqqq_normal", "Normal Market → TQQQ", a("leaf_bs_tqqq_normal"), "bs"))
    nodes.append(_node(
        "bs2_tqqq_cumret_1d", "TQQQ cumulative_return(1d) > 6",
        "TQQQ", "CUM_RET", 1, ">", 6, _s(tqqq_cumret_1),
        a("bs2_tqqq_cumret_1d"), subpath="bs",
    ))
    nodes.append(_leaf("leaf_bs_uvxy", "UVXY", a("leaf_bs_uvxy"), "bs"))
    nodes.append(_node(
        "bs3_tqqq_rsi_low", "TQQQ RSI(10) < 32",
        "TQQQ", "RSI", 10, "<", 32, tqqq_rsi10,
        a("bs3_tqqq_rsi_low"), subpath="bs",
    ))
    nodes.append(_leaf("leaf_bs_tqqq_b3", "TQQQ", a("leaf_bs_tqqq_b3"), "bs"))
    nodes.append(_node(
        "bs4_tmf_maxdd", "TMF max_drawdown(10d) < 7",
        "TMF", "MAX_DD", 10, "<", 7, _s(tmf_maxdd_10),
        a("bs4_tmf_maxdd"), subpath="bs",
    ))
    nodes.append(_leaf("leaf_bs_tqqq_b4", "TQQQ", a("leaf_bs_tqqq_b4"), "bs"))
    nodes.append(_leaf("leaf_bs_bil", "BIL", a("leaf_bs_bil"), "bs"))

    # ── NMA nodes ─────────────────────────────────────────────────────────────
    nodes.append(_node(
        "nma1_qqq_maxdd", "QQQ max_drawdown(10d) > 6",
        "QQQ", "MAX_DD", 10, ">", 6, _s(qqq_maxdd_10),
        a("nma1_qqq_maxdd"), subpath="nma",
    ))
    nodes.append(_leaf("leaf_nma_bil_1", "BIL", a("leaf_nma_bil_1"), "nma"))
    nodes.append(_node(
        "nma2_sh_cumret", "SH cumulative_return(10d) > 5",
        "SH", "CUM_RET", 10, ">", 5, _s(sh_cumret_10),
        a("nma2_sh_cumret"), subpath="nma",
    ))
    nodes.append(_ma_node(
        "nma2a_spy_vs_ma40", "SPY price > SPY MA(40)",
        "SPY", 40, ">", spy_price, spy_ma40,
        a("nma2a_spy_vs_ma40"), outcome="URTY", subpath="nma",
    ))
    nodes.append(_leaf("leaf_nma_urty", "URTY", a("leaf_nma_urty"), "nma"))
    nodes.append(_node(
        "nma3_ief_vs_tlt_rsi", "IEF RSI(200) < TLT RSI(200)",
        "IEF", "RSI", 200, "<", tlt_rsi200, ief_rsi200,
        a("nma3_ief_vs_tlt_rsi"), subpath="nma",
    ))
    nodes.append(_node(
        "nma3a_bnd_vs_spy_rsi", "BND RSI(45) > SPY RSI(45)",
        "BND", "RSI", 45, ">", spy_rsi45, bnd_rsi45,
        a("nma3a_bnd_vs_spy_rsi"), subpath="nma",
    ))
    nodes.append(_leaf("leaf_nma_tqqq_3a", "TQQQ", a("leaf_nma_tqqq_3a"), "nma"))
    nodes.append(_leaf("leaf_nma_bil_3a", "BIL", a("leaf_nma_bil_3a"), "nma"))
    nodes.append(_leaf("leaf_nma_bil_3", "BIL", a("leaf_nma_bil_3"), "nma"))
    nodes.append(_node(
        "nma4_bnd_vs_bil_cumret", "BND cumulative_return(60d) > BIL cumulative_return(60d)",
        "BND", "CUM_RET", 60, ">", _s(bil_cumret_60), _s(bnd_cumret_60),
        a("nma4_bnd_vs_bil_cumret"), subpath="nma",
    ))
    nodes.append(_node(
        "nma4b_spy_maxdd", "SPY max_drawdown(21d) < SPY max_drawdown(180d)",
        "SPY", "MAX_DD", 21, "<", _s(spy_maxdd_180), _s(spy_maxdd_21),
        a("nma4b_spy_maxdd"), subpath="nma",
    ))
    nodes.append(_node(
        "nma4c_spy_rsi_high", "SPY RSI(10) > 80",
        "SPY", "RSI", 10, ">", 80, spy_rsi10,
        a("nma4c_spy_rsi_high"), subpath="nma",
    ))
    nodes.append(_leaf("leaf_nma_uvxy", "UVXY", a("leaf_nma_uvxy"), "nma"))
    nodes.append(_node(
        "nma5_vixy_rsi", "VIXY RSI(10) > 84",
        "VIXY", "RSI", 10, ">", 84, vixy_rsi10,
        a("nma5_vixy_rsi"), subpath="nma",
    ))
    nodes.append(_leaf("leaf_nma_psq", "PSQ", a("leaf_nma_psq"), "nma"))
    nodes.append(_leaf("leaf_nma_tqqq_5", "TQQQ", a("leaf_nma_tqqq_5"), "nma"))
    nodes.append(_node(
        "nma6_ief_vs_tlt_rsi", "IEF RSI(200) < TLT RSI(200)",
        "IEF", "RSI", 200, "<", tlt_rsi200, ief_rsi200,
        a("nma6_ief_vs_tlt_rsi"), subpath="nma",
    ))
    nodes.append(_node(
        "nma6a_bnd_vs_spy_rsi", "BND RSI(45) > SPY RSI(45)",
        "BND", "RSI", 45, ">", spy_rsi45, bnd_rsi45,
        a("nma6a_bnd_vs_spy_rsi"), subpath="nma",
    ))
    nodes.append(_leaf("leaf_nma_tqqq_6a", "TQQQ", a("leaf_nma_tqqq_6a"), "nma"))
    nodes.append(_leaf("leaf_nma_bil_6a", "BIL", a("leaf_nma_bil_6a"), "nma"))
    nodes.append(_leaf("leaf_nma_bil_6", "BIL", a("leaf_nma_bil_6"), "nma"))

    # ── NMB nodes ─────────────────────────────────────────────────────────────
    nodes.append(_node(
        "nmb1_qqq_maxdd", "QQQ max_drawdown(10d) > 6",
        "QQQ", "MAX_DD", 10, ">", 6, _s(qqq_maxdd_10),
        a("nmb1_qqq_maxdd"), subpath="nmb",
    ))
    nodes.append(_leaf("leaf_nmb_bil_1", "BIL", a("leaf_nmb_bil_1"), "nmb"))
    nodes.append(_node(
        "nmb2_tmf_maxdd", "TMF max_drawdown(10d) > 7",
        "TMF", "MAX_DD", 10, ">", 7, _s(tmf_maxdd_10),
        a("nmb2_tmf_maxdd"), subpath="nmb",
    ))
    nodes.append(_leaf("leaf_nmb_bil_2", "BIL", a("leaf_nmb_bil_2"), "nmb"))
    nodes.append(_ma_node(
        "nmb3_qqq_vs_ma25", "QQQ price > QQQ MA(25)",
        "QQQ", 25, ">", qqq_price, qqq_ma25,
        a("nmb3_qqq_vs_ma25"), outcome="TQQQ", subpath="nmb",
    ))
    nodes.append(_leaf("leaf_nmb_tqqq_3", "TQQQ", a("leaf_nmb_tqqq_3"), "nmb"))
    nodes.append(_node(
        "nmb4_spy_rsi_60", "SPY RSI(60) > 50",
        "SPY", "RSI", 60, ">", 50, spy_rsi60,
        a("nmb4_spy_rsi_60"), subpath="nmb",
    ))
    nodes.append(_node(
        "nmb4a_bnd_vs_spy_rsi", "BND RSI(45) > SPY RSI(45)",
        "BND", "RSI", 45, ">", spy_rsi45, bnd_rsi45,
        a("nmb4a_bnd_vs_spy_rsi"), subpath="nmb",
    ))
    nodes.append(_leaf("leaf_nmb_tqqq_4a", "TQQQ", a("leaf_nmb_tqqq_4a"), "nmb"))
    nodes.append(_leaf("leaf_nmb_bil_4a", "BIL", a("leaf_nmb_bil_4a"), "nmb"))
    nodes.append(_node(
        "nmb5_ief_vs_tlt_rsi", "IEF RSI(200) < TLT RSI(200)",
        "IEF", "RSI", 200, "<", tlt_rsi200, ief_rsi200,
        a("nmb5_ief_vs_tlt_rsi"), subpath="nmb",
    ))
    nodes.append(_node(
        "nmb5a_bnd_vs_spy_rsi", "BND RSI(45) > SPY RSI(45)",
        "BND", "RSI", 45, ">", spy_rsi45, bnd_rsi45,
        a("nmb5a_bnd_vs_spy_rsi"), subpath="nmb",
    ))
    nodes.append(_leaf("leaf_nmb_tqqq_5a", "TQQQ", a("leaf_nmb_tqqq_5a"), "nmb"))
    nodes.append(_leaf("leaf_nmb_bil_5a", "BIL", a("leaf_nmb_bil_5a"), "nmb"))
    nodes.append(_leaf("leaf_nmb_bil_5", "BIL", a("leaf_nmb_bil_5"), "nmb"))

    return {
        "fired": True,
        "result": final_result,
        "active_path": active_path,
        "nodes": nodes,
        "sub_results": {
            "bs":  bs_result,
            "nma": nma_result,
            "nmb": nmb_result,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dry run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import numpy as np

    rng = np.random.default_rng(42)

    def _rw(start, n, drift=0.0, vol=1.0):
        """Random-walk price series."""
        steps = rng.normal(drift, vol, n)
        prices = np.cumprod(1 + steps / 100) * start
        return prices

    N = 210  # enough for RSI(200) + buffer

    prices = {
        "TQQQ": _rw(40,  N, drift=0.05, vol=2.5),
        "QQQ":  _rw(370, N, drift=0.03, vol=1.0),
        "SPY":  _rw(480, N, drift=0.02, vol=0.8),
        "SH":   _rw(14,  N, drift=-0.01, vol=0.8),
        "TMF":  _rw(8,   N, drift=-0.05, vol=2.0),
        "BND":  _rw(72,  N, drift=0.01, vol=0.3),
        "BIL":  _rw(91,  N, drift=0.005, vol=0.05),
        "TLT":  _rw(88,  N, drift=0.01, vol=1.0),
        "IEF":  _rw(95,  N, drift=0.01, vol=0.6),
        "VIXY": _rw(18,  N, drift=-0.05, vol=4.0),
    }

    print("=" * 60)
    print("BlackSwan dry run")
    print("=" * 60)

    out = evaluate_blackswan(prices)

    print(f"\nfired      : {out['fired']}")
    print(f"result     : {out['result']}")
    print(f"\nsub_results:")
    for k, v in out["sub_results"].items():
        print(f"  {k.upper():4s} → {v}")

    print(f"\nactive_path ({len(out['active_path'])} nodes):")
    for nid in out["active_path"]:
        node = next(n for n in out["nodes"] if n["id"] == nid)
        lv   = node.get("live_value")
        th   = node.get("threshold")
        op   = node.get("operator")
        res  = node.get("result")
        if node.get("is_leaf"):
            print(f"  [{nid}]  → {node['outcome']}")
        else:
            cc = " *** CLOSE CALL ***" if node.get("close_call") else ""
            print(f"  [{nid}]  {node['label']}  |  live={lv}  threshold={th}  "
                  f"op={op}  result={res}{cc}")

    total   = len(out["nodes"])
    active  = sum(1 for n in out["nodes"] if n["active"])
    print(f"\nnodes total={total}  active={active}  inactive={total - active}")
    print("=" * 60)
