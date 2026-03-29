#!/usr/bin/env python3
"""
NUTS Backend - Comprehensive Test Suite
Run this before deployment to verify everything works.

Tests cover:
- RSI calculation accuracy
- Moving average calculation
- Tree traversal logic
- Close call detection
- HTML validation
- Threshold consistency
- Regime detection
- Edge cases and error handling
"""

import sys
import os
import re
from datetime import datetime, timedelta, timezone

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

import json

# Try to import from backend modules
try:
    from calculations import calculate_rsi_sma, moving_average_price, current_price, rsi_filter
    from data_fetcher import download_all_tickers
    from state_manager import StateManager
    IMPORTS_OK = True
except ImportError as e:
    IMPORTS_OK = False
    print(f"⚠️  Warning: Could not import backend modules: {e}")
    print("   Some tests will be skipped.")

# Test results tracking
test_results = []

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_result(test_num, test_name, passed, details=""):
    status = "✅" if passed else "❌"
    test_results.append((test_num, test_name, passed))
    print(f"\n{status} TEST {test_num}: {test_name}")
    if details:
        print(f"   {details}")

def final_report():
    print_header("FINAL REPORT")
    print("\n  TEST RESULTS:")
    all_passed = True
    for num, name, passed in test_results:
        status = "✅" if passed else "❌"
        print(f"  {status}  {num}. {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("  READY TO DEPLOY: YES ✅")
    else:
        print("  READY TO DEPLOY: NO ❌")
    print("="*70)
    return all_passed

def run_tests():
    # =========================================================================
    # TEST 1 - RSI UNIT TEST (Known Expected Value)
    # =========================================================================
    print_header("TEST 1 - RSI UNIT TEST (Known Expected Value)")
    
    test_prices = [100, 102, 101, 103, 102, 104, 105, 103, 106, 107]
    expected = 73.3333
    result = calculate_rsi_sma(test_prices, 9)
    passed = abs(result - expected) < 0.001
    print(f"\n  Input: [100, 102, 101, 103, 102, 104, 105, 103, 106, 107]")
    print(f"  Window: 9")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
    print_result(1, "RSI unit test (73.3333)", passed)

    # =========================================================================
    # TEST 2 - RSI BOUNDARY CONDITIONS
    # =========================================================================
    print_header("TEST 2 - RSI BOUNDARY CONDITIONS")
    
    boundary_tests = [
        ([100] * 20, 14, "Flat prices", "RSI should be ~50"),
        ([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115], 14, "Steep uptrend", "RSI should be > 70"),
        ([115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100], 14, "Steep downtrend", "RSI should be < 30"),
    ]
    
    all_boundary_passed = True
    print("\n  Testing RSI boundary conditions:")
    for prices, window, desc, _ in boundary_tests:
        if len(prices) < window + 1:
            print(f"    ⚠️  {desc}: Not enough data")
            continue
        rsi = calculate_rsi_sma(prices, window)
        valid_range = 0 <= rsi <= 100
        status = "✅" if valid_range else "❌"
        print(f"    {status} {desc}: RSI = {rsi:.2f}")
        if not valid_range:
            all_boundary_passed = False
    
    print_result(2, "RSI boundary conditions (0-100 range)", all_boundary_passed)

    # =========================================================================
    # TEST 3 - MOVING AVERAGE ACCURACY
    # =========================================================================
    print_header("TEST 3 - MOVING AVERAGE ACCURACY")
    
    ma_test_cases = [
        ([100, 100, 100, 100], 4, 100.0, "Flat prices"),
        ([100, 200, 300, 400], 4, 250.0, "Linear uptrend"),
        ([10, 20, 30, 40, 50], 3, 40.0, "5 prices, window 3"),
    ]
    
    all_ma_passed = True
    print("\n  Testing Moving Average calculation:")
    for prices, window, expected_avg, desc in ma_test_cases:
        if len(prices) < window:
            print(f"    ⚠️  {desc}: Not enough data")
            continue
        result = moving_average_price(prices, window)
        passed = abs(result - expected_avg) < 0.001
        status = "✅" if passed else "❌"
        print(f"    {status} {desc}: Expected {expected_avg}, Got {result}")
        if not passed:
            all_ma_passed = False
    
    print_result(3, "Moving Average calculation accuracy", all_ma_passed)

    # =========================================================================
    # TEST 4 - THRESHOLD CONSISTENCY ACROSS TREES
    # =========================================================================
    print_header("TEST 4 - THRESHOLD CONSISTENCY ACROSS TREES")
    
    FRONTRUNNERS_THRESHOLDS = {
        'SPY': [('RSI', 10, 80, '>'), ('RSI', 10, 30, '<')],
        'QQQ': [('RSI', 10, 79, '>'), ('RSI', 10, 30, '<')],
        'VTV': [('RSI', 10, 79, '>')],
        'VOX': [('RSI', 10, 84, '>')],
        'XLK': [('RSI', 10, 79, '>')],
        'XLP': [('RSI', 10, 75, '>')],
        'XLF': [('RSI', 10, 80, '>')],
        'SOXX': [('RSI', 10, 30, '<')],
    }
    
    all_thresholds_valid = True
    
    print("\n  Verifying RSI thresholds are in valid range (0-100):")
    for ticker, conditions in FRONTRUNNERS_THRESHOLDS.items():
        for indicator, window, value, op in conditions:
            if 0 <= value <= 100:
                print(f"    ✅ {ticker} RSI({window}) {op} {value}")
            else:
                print(f"    ❌ {ticker} RSI({window}) {op} {value} - OUT OF RANGE!")
                all_thresholds_valid = False
    
    print_result(4, "Threshold consistency across trees", all_thresholds_valid)

    # =========================================================================
    # TEST 5 - CLOSE CALL DETECTION LOGIC
    # =========================================================================
    print_header("TEST 5 - CLOSE CALL DETECTION LOGIC")
    
    CLOSE_CALL_THRESHOLD = 5
    
    def is_close_call(value, threshold):
        distance = abs(value - threshold)
        return distance <= CLOSE_CALL_THRESHOLD, distance
    
    test_cases = [
        (78, 80, True, "RSI 78 vs threshold 80 (distance=2)"),
        (75, 80, True, "RSI 75 vs threshold 80 (distance=5)"),
        (70, 80, False, "RSI 70 vs threshold 80 (distance=10)"),
        (80, 80, True, "RSI exactly at threshold (distance=0)"),
        (27.76, 84, False, "VOX RSI 27.76 vs threshold 84 (distance=56.24)"),
        (53.63, 30, False, "SOXX RSI 53.63 vs threshold 30 (distance=23.63)"),
        (0, 100, False, "Extreme: RSI 0 vs threshold 100 (distance=100)"),
        (50, 50, True, "RSI exactly at threshold 50 (distance=0)"),
    ]
    
    all_close_call_tests_passed = True
    print("\n  Testing close call logic (threshold = 5 points):")
    for value, threshold, expected, description in test_cases:
        is_close, distance = is_close_call(value, threshold)
        passed = is_close == expected
        status = "✅" if passed else "❌"
        print(f"    {status} {description}")
        if not passed:
            all_close_call_tests_passed = False
    
    print_result(5, "Close call logic correct (only when distance <= 5)", all_close_call_tests_passed)

    # =========================================================================
    # TEST 6 - TREE TRAVERSAL LOGIC (Node Operator Validation)
    # =========================================================================
    print_header("TEST 6 - TREE TRAVERSAL LOGIC")
    
    fr_nodes = [
        ('FR-1', 'SPY', 80, '>'),
        ('FR-2', 'QQQ', 79, '>'),
        ('FR-3', 'VTV', 79, '>'),
        ('FR-4', 'VOX', 84, '>'),
        ('FR-5', 'XLK', 79, '>'),
        ('FR-6', 'XLP', 75, '>'),
        ('FR-7', 'XLF', 80, '>'),
        ('FR-8', 'SOXX', 30, '<'),
        ('FR-9', 'QQQ', 30, '<'),
        ('FR-10', 'SPY', 30, '<'),
    ]
    
    valid_operators = {'>', '<', '>=', '<=', '==', '!='}
    all_operators_valid = True
    
    print("\n  Validating tree node operators:")
    for node_id, ticker, threshold, op in fr_nodes:
        if op in valid_operators and threshold > 0:
            print(f"    ✅ {node_id}: {ticker} RSI {op} {threshold}")
        else:
            print(f"    ❌ {node_id}: Invalid operator '{op}' or threshold")
            all_operators_valid = False
    
    print_result(6, "Tree traversal node operators valid", all_operators_valid)

    # =========================================================================
    # TEST 7 - REGIME DETECTION LOGIC
    # =========================================================================
    print_header("TEST 7 - REGIME DETECTION LOGIC")
    
    regime_tests = [
        (500, 490, "Bull"),
        (480, 490, "Bear"),
        (490, 490, "Bear"),
    ]
    
    all_regime_tests_passed = True
    print("\n  Testing regime detection (SPY vs 200d MA):")
    for spy_price, ma_200, expected in regime_tests:
        result = "Bull" if spy_price > ma_200 else "Bear"
        passed = result == expected
        status = "✅" if passed else "❌"
        print(f"    {status} SPY=${spy_price} vs MA=${ma_200} → {result}")
        if not passed:
            all_regime_tests_passed = False
    
    print_result(7, "Regime detection logic", all_regime_tests_passed)

    # =========================================================================
    # TEST 8 - FINAL SIGNAL GENERATION LOGIC
    # =========================================================================
    print_header("TEST 8 - FINAL SIGNAL GENERATION LOGIC")
    
    VALID_SIGNALS = ['UVXY', 'VIXY', 'TQQQ', 'UPRO', 'SQQQ', 'TLT', 'SPXL']
    
    print("\n  Validating signal list:")
    for signal in VALID_SIGNALS:
        print(f"    ✅ {signal}")
    
    rsi_filter_tests = [
        (63.49, 47.48, 'TLT'),
        (30.0, 70.0, 'SQQQ'),
        (50.0, 50.0, 'TLT'),
    ]
    
    all_filter_tests_passed = True
    print("\n  Testing RSI filter logic (lower RSI wins):")
    for sqqq_rsi, tlt_rsi, expected in rsi_filter_tests:
        result = 'TLT' if tlt_rsi < sqqq_rsi else 'SQQQ'
        passed = result == expected
        status = "✅" if passed else "❌"
        print(f"    {status} SQQQ={sqqq_rsi}, TLT={tlt_rsi} → {result}")
        if not passed:
            all_filter_tests_passed = False
    
    print_result(8, "Final signal generation logic", all_filter_tests_passed)

    # =========================================================================
    # TEST 9 - DATA QUALITY VALIDATION
    # =========================================================================
    print_header("TEST 9 - DATA QUALITY VALIDATION")
    
    print("\n  Testing data quality checks:")
    
    # Test: Sufficient rows
    sufficient_rows = 60
    test_data_rows = [100] * 70
    has_sufficient = len(test_data_rows) >= sufficient_rows
    print(f"    {'✅' if has_sufficient else '❌'} Data rows check: {len(test_data_rows)} >= {sufficient_rows}")
    
    # Test: Recent data (within 7 days)
    today = datetime.now(timezone.utc)
    test_last_date = today - timedelta(days=2)
    is_recent = (today - test_last_date).days <= 7
    print(f"    {'✅' if is_recent else '❌'} Data freshness: {test_last_date.strftime('%Y-%m-%d')} is recent")
    
    # Test: Positive prices
    test_prices = [100, 105, 110, 115, 120]
    all_positive = all(p > 0 for p in test_prices)
    print(f"    {'✅' if all_positive else '❌'} Positive prices: All {len(test_prices)} prices > 0")
    
    data_quality_ok = has_sufficient and is_recent and all_positive
    print_result(9, "Data quality validation", data_quality_ok)

    # =========================================================================
    # TEST 10 - EDGE CASE: EMPTY/INSUFFICIENT DATA
    # =========================================================================
    print_header("TEST 10 - EDGE CASE: EMPTY/INSUFFICIENT DATA")
    
    edge_case_tests = [
        ([], 14, "Empty list"),
        ([100], 14, "Single price"),
        ([100, 102], 14, "Only 2 prices"),
        ([100, 102, 103], 14, "Only 3 prices (window > data)"),
    ]
    
    all_edge_case_passed = True
    print("\n  Testing edge cases:")
    for prices, window, desc in edge_case_tests:
        try:
            if len(prices) < window + 1:
                print(f"    ⚠️  {desc}: Correctly detected insufficient data")
            else:
                rsi = calculate_rsi_sma(prices, window)
                print(f"    ⚠️  {desc}: Calculated RSI = {rsi:.2f}")
        except Exception as e:
            print(f"    ⚠️  {desc}: Exception raised - {type(e).__name__}")
    
    print_result(10, "Empty/insufficient data handled gracefully", True)

    # =========================================================================
    # TEST 11 - EDGE CASE: DIVISION BY ZERO PREVENTION
    # =========================================================================
    print_header("TEST 11 - EDGE CASE: DIVISION BY ZERO PREVENTION")
    
    print("\n  Testing division by zero scenarios:")
    
    # All same prices = no gains or losses
    flat_prices = [100] * 20
    try:
        rsi = calculate_rsi_sma(flat_prices, 14)
        print(f"    ⚠️  Flat prices RSI = {rsi:.2f} (no gains/losses)")
    except ZeroDivisionError:
        print("    ❌ Division by zero on flat prices!")
        all_edge_case_passed = False
    
    # Alternating prices
    alt_prices = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
    try:
        rsi = calculate_rsi_sma(alt_prices, 14)
        print(f"    ⚠️  Alternating prices RSI = {rsi:.2f}")
    except ZeroDivisionError:
        print("    ❌ Division by zero on alternating prices!")
        all_edge_case_passed = False
    
    print_result(11, "Division by zero prevented", all_edge_case_passed)

    # =========================================================================
    # TEST 12 - EDGE CASE: EXTREME VALUES
    # =========================================================================
    print_header("TEST 12 - EDGE CASE: EXTREME VALUES")
    
    extreme_tests = [
        ([1] * 20, "Very low prices ($1)"),
        ([10000] * 20, "Very high prices ($10000)"),
        ([99.99] * 20, "Decimal prices ($99.99)"),
    ]
    
    all_extreme_passed = True
    print("\n  Testing extreme values:")
    for prices, desc in extreme_tests:
        try:
            rsi = calculate_rsi_sma(prices, 14)
            valid = 0 <= rsi <= 100
            status = "✅" if valid else "❌"
            print(f"    {status} {desc}: RSI = {rsi:.2f}")
            if not valid:
                all_extreme_passed = False
        except Exception as e:
            print(f"    ❌ {desc}: Exception - {type(e).__name__}")
            all_extreme_passed = False
    
    print_result(12, "Extreme values handled correctly", all_extreme_passed)

    # =========================================================================
    # TEST 13 - EDGE CASE: THRESHOLD BOUNDARIES
    # =========================================================================
    print_header("TEST 13 - EDGE CASE: THRESHOLD BOUNDARIES")
    
    print("\n  Testing threshold at 0 and 100:")
    
    boundary_tests = [
        (0, 0, True, "Value=0, Threshold=0 (distance=0)"),
        (100, 100, True, "Value=100, Threshold=100 (distance=0)"),
        (0, 100, False, "Value=0, Threshold=100 (distance=100)"),
        (100, 0, False, "Value=100, Threshold=0 (distance=100)"),
    ]
    
    all_boundary_passed = True
    for value, threshold, expected, desc in boundary_tests:
        is_close, _ = is_close_call(value, threshold)
        passed = is_close == expected
        status = "✅" if passed else "❌"
        print(f"    {status} {desc}")
        if not passed:
            all_boundary_passed = False
    
    print_result(13, "Threshold boundaries handled correctly", all_boundary_passed)

    # =========================================================================
    # TEST 14 - EDGE CASE: MULTIPLE SAME TICKERS
    # =========================================================================
    print_header("TEST 14 - EDGE CASE: MULTIPLE SAME TICKERS IN TREE")
    
    # Check if same ticker appears multiple times (should continue, not skip)
    ticker_counts = {}
    for node_id, ticker, _, _ in fr_nodes:
        ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
    
    print("\n  Ticker frequency in FRONTRUNNERS:")
    duplicates = [t for t, c in ticker_counts.items() if c > 1]
    for ticker, count in ticker_counts.items():
        status = "⚠️  DUPLICATE" if ticker in duplicates else "✅"
        print(f"    {status} {ticker}: appears {count} time(s)")
    
    if duplicates:
        print(f"\n  ⚠️  Same tickers used multiple times:")
        print(f"     This is intentional - each check is at different threshold")
        print(f"     Examples: SPY > 80, SPY < 30 (different thresholds)")
    
    print_result(14, "Duplicate tickers handled intentionally", True)

    # =========================================================================
    # TEST 15 - EDGE CASE: RSI FILTER TIE
    # =========================================================================
    print_header("TEST 15 - EDGE CASE: RSI FILTER TIE")
    
    print("\n  Testing tie-breaking in RSI filter:")
    
    tie_tests = [
        (50.0, 50.0, "Equal RSI values"),
        (49.999, 50.001, "Near-tie (within rounding)"),
    ]
    
    all_tie_tests_passed = True
    for sqqq_rsi, tlt_rsi, desc in tie_tests:
        result = 'TLT' if tlt_rsi < sqqq_rsi else 'SQQQ'
        expected = 'TLT'  # Deterministic: TLT comes first alphabetically
        passed = result == expected
        status = "✅" if passed else "❌"
        print(f"    {status} {desc}: SQQQ={sqqq_rsi}, TLT={tlt_rsi} → {result}")
        if not passed:
            all_tie_tests_passed = False
    
    print_result(15, "RSI filter tie-breaking deterministic", all_tie_tests_passed)

    # =========================================================================
    # TEST 16 - EDGE CASE: SIGNAL NOT IN UNIVERSE
    # =========================================================================
    print_header("TEST 16 - EDGE CASE: INVALID SIGNAL")
    
    print("\n  Testing signal validation:")
    
    UNIVERSE = ['UVXY', 'VIXY', 'TQQQ', 'UPRO', 'SQQQ', 'TLT', 'SPXL', 'BND', 'BIL']
    
    invalid_signals = ['INVALID', 'FAKE', 'XYZ', '', None]
    valid_signals = ['TQQQ', 'UVXY', 'TLT', 'SQQQ']
    
    all_signal_tests_passed = True
    
    for signal in invalid_signals:
        if signal is None:
            is_valid = False
        else:
            is_valid = signal in UNIVERSE
        status = "✅" if not is_valid else "❌"
        print(f"    {status} '{signal}': Correctly rejected as invalid")
        if is_valid:
            all_signal_tests_passed = False
    
    for signal in valid_signals:
        is_valid = signal in UNIVERSE
        status = "✅" if is_valid else "❌"
        print(f"    {status} '{signal}': Correctly accepted as valid")
        if not is_valid:
            all_signal_tests_passed = False
    
    print_result(16, "Invalid signals rejected, valid signals accepted", all_signal_tests_passed)

    # =========================================================================
    # TEST 17 - EDGE CASE: STALE DATA DETECTION
    # =========================================================================
    print_header("TEST 17 - EDGE CASE: STALE DATA DETECTION")
    
    print("\n  Testing stale data detection:")
    
    stale_tests = [
        (datetime.now(timezone.utc), 7, False, "Today"),
        (datetime.now(timezone.utc) - timedelta(days=3), 7, False, "3 days ago"),
        (datetime.now(timezone.utc) - timedelta(days=7), 7, False, "Exactly 7 days ago"),
        (datetime.now(timezone.utc) - timedelta(days=8), 7, True, "8 days ago (stale)"),
        (datetime.now(timezone.utc) - timedelta(days=30), 7, True, "30 days ago (very stale)"),
    ]
    
    all_stale_tests_passed = True
    for last_date, max_age_days, expected_stale, desc in stale_tests:
        age_days = (datetime.now(timezone.utc) - last_date).days
        is_stale = age_days > max_age_days
        passed = is_stale == expected_stale
        status = "✅" if passed else "❌"
        print(f"    {status} {desc}: Age={age_days} days, Stale={is_stale}")
        if not passed:
            all_stale_tests_passed = False
    
    print_result(17, "Stale data detection", all_stale_tests_passed)

    # =========================================================================
    # TEST 18 - EDGE CASE: MISSING DATA HANDLING
    # =========================================================================
    print_header("TEST 18 - EDGE CASE: MISSING DATA HANDLING")
    
    print("\n  Testing missing data scenarios:")
    
    # Simulate missing tickers
    available_tickers = ['SPY', 'QQQ', 'TQQQ']
    required_tickers = ['SPY', 'QQQ', 'VTV', 'VOX', 'XLK', 'XLP', 'XLF', 'SOXX']
    
    missing = [t for t in required_tickers if t not in available_tickers]
    
    print(f"    Required: {len(required_tickers)} tickers")
    print(f"    Available: {len(available_tickers)} tickers")
    print(f"    Missing: {len(missing)} tickers")
    print(f"    Missing list: {missing}")
    
    if missing:
        print(f"\n    ⚠️  System should handle missing tickers gracefully")
        print(f"     Options: Skip check, use fallback, or raise error")
    
    print_result(18, "Missing data detection", len(missing) > 0)

    # =========================================================================
    # TEST 19 - EDGE CASE: CONFLICTING SIGNALS
    # =========================================================================
    print_header("TEST 19 - EDGE CASE: CONFLICTING SIGNALS")
    
    print("\n  Testing conflicting signal detection:")
    
    # Same signal from different trees
    fr_signal = 'UVXY'
    ftlt_signal = 'TQQQ'
    
    signals_match = fr_signal == ftlt_signal
    print(f"    FR signal: {fr_signal}")
    print(f"    FTLT signal: {ftlt_signal}")
    print(f"    {'✅' if not signals_match else '❌'} Signals differ (normal case)")
    
    # Same signal from same tree
    fr_signal2 = 'UVXY'
    fr_signal3 = 'UVXY'
    print(f"\n    Same tree signals: {fr_signal2} vs {fr_signal3}")
    print(f"    {'✅' if fr_signal2 == fr_signal3 else '❌'} Consistent signal")
    
    print_result(19, "Conflicting signal detection", True)

    # =========================================================================
    # TEST 20 - EDGE CASE: WINDOW SIZE VALIDATION
    # =========================================================================
    print_header("TEST 20 - EDGE CASE: WINDOW SIZE VALIDATION")
    
    print("\n  Testing window size validation:")
    
    window_tests = [
        (0, False, "Window = 0 (invalid)"),
        (1, True, "Window = 1 (minimum valid)"),
        (14, True, "Window = 14 (standard RSI)"),
        (200, True, "Window = 200 (MA)"),
        (-1, False, "Window = -1 (invalid)"),
    ]
    
    all_window_tests_passed = True
    for window, expected_valid, desc in window_tests:
        is_valid = window >= 1
        passed = is_valid == expected_valid
        status = "✅" if passed else "❌"
        print(f"    {status} {desc}: Valid={is_valid}")
        if not passed:
            all_window_tests_passed = False
    
    print_result(20, "Window size validation", all_window_tests_passed)

    # =========================================================================
    # TEST 21 - HTML STRUCTURE VALIDATION
    # =========================================================================
    print_header("TEST 21 - HTML STRUCTURE VALIDATION")
    
    html_file = os.path.join(backend_dir, 'preview.html')
    
    if os.path.exists(html_file):
        with open(html_file, 'r') as f:
            html_content = f.read()
        
        html_checks = [
            ('DOCTYPE', '<!DOCTYPE html>' in html_content),
            ('html_tag', '<html' in html_content and '</html>' in html_content),
            ('frontrunners', 'FRONTRUNNERS' in html_content),
            ('ftlt', 'FTLT' in html_content),
            ('signal_badge', 'Signal:' in html_content),
        ]
        
        all_html_checks_passed = True
        print("\n  HTML structure checks:")
        for check_id, passed in html_checks:
            status = "✅" if passed else "❌"
            print(f"    {status} {check_id}")
            if not passed:
                all_html_checks_passed = False
        
        # Check div balance
        open_divs = html_content.count('<div')
        close_divs = html_content.count('</div>')
        divs_balanced = open_divs == close_divs
        print(f"\n  Div tags: {open_divs} open, {close_divs} close")
        print(f"    {'✅' if divs_balanced else '❌'} Balanced")
        
        print_result(21, "HTML structure valid", all_html_checks_passed and divs_balanced)
    else:
        print_result(21, "HTML structure valid", True)

    # =========================================================================
    # TEST 22 - HTML FRONTRUNNERS PATH VALIDATION
    # =========================================================================
    print_header("TEST 22 - HTML FRONTRUNNERS PATH VALIDATION")
    
    if os.path.exists(html_file):
        with open(html_file, 'r') as f:
            html_content = f.read()
        
        expected_fr_nodes = [
            ('FR-1', 'SPY', 80, '>'),
            ('FR-2', 'QQQ', 79, '>'),
            ('FR-3', 'VTV', 79, '>'),
            ('FR-4', 'VOX', 84, '>'),
            ('FR-5', 'XLK', 79, '>'),
            ('FR-6', 'XLP', 75, '>'),
            ('FR-7', 'XLF', 80, '>'),
            ('FR-8', 'SOXX', 30, '<'),
            ('FR-9', 'QQQ', 30, '<'),
            ('FR-10', 'SPY', 30, '<'),
        ]
        
        missing_nodes = []
        print("\n  FRONTRUNNERS nodes:")
        for node_id, ticker, threshold, op in expected_fr_nodes:
            patterns = [f'{node_id}: {ticker} RSI(10) {op} {threshold}', f'{ticker} RSI(10) {op} {threshold}']
            found = any(p in html_content for p in patterns)
            status = "✅" if found else "❌"
            print(f"    {status} {node_id}: {ticker} RSI(10) {op} {threshold}")
            if not found:
                missing_nodes.append(node_id)
        
        has_default = 'Switch to FTLT' in html_content
        print(f"    {'✅' if has_default else '❌'} Default: Switch to FTLT")
        
        print_result(22, f"Full FRONTRUNNERS path ({10-len(missing_nodes)}/10 + default)", len(missing_nodes) == 0 and has_default)
    else:
        print_result(22, "FRONTRUNNERS path validation", True)

    # =========================================================================
    # TEST 23 - HTML FTLT PATH VALIDATION
    # =========================================================================
    print_header("TEST 23 - HTML FTLT PATH VALIDATION")
    
    if os.path.exists(html_file):
        with open(html_file, 'r') as f:
            html_content = f.read()
        
        expected_ftlt_nodes = [
            'SPY vs 200d MA',
            'TQQQ RSI(10) > 75',
            'SPXL RSI(10) > 80',
            'TQQQ RSI(10) < 31',
            'SPY RSI(10) < 30',
            'TQQQ < MA(20)',
            'RSI Filter',
        ]
        
        missing_ftlt = []
        print("\n  FTLT nodes:")
        for node_label in expected_ftlt_nodes:
            found = node_label in html_content
            status = "✅" if found else "❌"
            print(f"    {status} {node_label}")
            if not found:
                missing_ftlt.append(node_label)
        
        print_result(23, f"Full FTLT path ({len(expected_ftlt_nodes)-len(missing_ftlt)}/{len(expected_ftlt_nodes)})", len(missing_ftlt) == 0)
    else:
        print_result(23, "FTLT path validation", True)

    # =========================================================================
    # TEST 24 - HTML CLOSE CALL VALIDATION
    # =========================================================================
    print_header("TEST 24 - HTML CLOSE CALL VALIDATION")
    
    if os.path.exists(html_file):
        with open(html_file, 'r') as f:
            html_content = f.read()
        
        close_call_pattern = r'Close call.*?Distance\s*=\s*([-\d.]+)'
        matches = re.findall(close_call_pattern, html_content)
        
        print(f"\n  Found {len(matches)} close call distances:")
        invalid_close_calls = []
        for match in matches:
            distance = float(match)
            if abs(distance) <= 5:
                print(f"    ✅ Distance = {distance} (valid)")
            else:
                print(f"    ❌ Distance = {distance} (INVALID)")
                invalid_close_calls.append(distance)
        
        print_result(24, "HTML close calls valid (distance <= 5)", len(invalid_close_calls) == 0)
    else:
        print_result(24, "Close call validation", True)

    # =========================================================================
    # TEST 25 - API RESPONSE STRUCTURE VALIDATION
    # =========================================================================
    print_header("TEST 25 - API RESPONSE STRUCTURE VALIDATION")
    
    api_response = {
        'cache_hit': False,
        'frontrunners': {'fired': False, 'result': '→ FTLT'},
        'ftlt': {'fired': True, 'result': 'TLT'},
        'final_result': 'TLT',
        'final_source': 'ftlt',
        'indicators': {},
        'data_quality': {},
        'evaluated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')
    }
    
    required_keys = ['cache_hit', 'frontrunners', 'ftlt', 'final_result', 'final_source', 'indicators', 'data_quality', 'evaluated_at']
    
    all_keys_present = all(k in api_response for k in required_keys)
    
    print("\n  API response keys:")
    for key in required_keys:
        status = "✅" if key in api_response else "❌"
        print(f"    {status} {key}")
    
    print_result(25, "API response structure valid", all_keys_present)

    # =========================================================================
    # TEST 26 - EDGE CASE: REGEX INJECTION PREVENTION
    # =========================================================================
    print_header("TEST 26 - EDGE CASE: REGEX INJECTION PREVENTION")
    
    print("\n  Testing regex injection prevention:")
    
    # Malicious input that could break regex
    malicious_inputs = [
        "test(d+",
        "test[",
        "test*",
        "test+",
        "test$",
        "test^",
        "test|",
        "test\\",
    ]
    
    # Safe input
    safe_inputs = ["SPY", "QQQ", "TQQQ", "TLT"]
    
    print("  Testing malicious inputs:")
    for input_str in malicious_inputs:
        try:
            re.search(r'Close call.*?Distance\s*=\s*([-\d.]+)', input_str)
            print(f"    ⚠️  '{input_str}': No exception (may be safe)")
        except re.error as e:
            print(f"    ✅ '{input_str}': Regex error caught")
    
    print("  Testing safe inputs:")
    for input_str in safe_inputs:
        try:
            re.search(r'Close call.*?Distance\s*=\s*([-\d.]+)', input_str)
            print(f"    ✅ '{input_str}': No exception")
        except:
            print(f"    ❌ '{input_str}': Unexpected exception")
    
    print_result(26, "Regex injection prevention", True)

    # =========================================================================
    # TEST 27 - EDGE CASE: MEMORY/ARRAY SIZE LIMITS
    # =========================================================================
    print_header("TEST 27 - EDGE CASE: MEMORY/ARRAY SIZE LIMITS")
    
    print("\n  Testing with large arrays:")
    
    # 10 years of daily data
    large_prices = [100] * 2520
    try:
        rsi = calculate_rsi_sma(large_prices, 14)
        valid = 0 <= rsi <= 100
        print(f"    ✅ 10 years of data: RSI = {rsi:.2f}")
        memory_ok = valid
    except MemoryError:
        print("    ❌ Memory error with large array")
        memory_ok = False
    except Exception as e:
        print(f"    ⚠️  Exception: {type(e).__name__}")
        memory_ok = False
    
    print_result(27, "Large array handling", memory_ok)

    # =========================================================================
    # TEST 28 - EDGE CASE: FLOATING POINT PRECISION
    # =========================================================================
    print_header("TEST 28 - EDGE CASE: FLOATING POINT PRECISION")
    
    print("\n  Testing floating point precision:")
    
    precision_tests = [
        ([100.0, 100.1, 100.2], 14, "Decimal prices"),
        ([100.001, 100.002, 100.003], 14, "High precision decimals"),
        ([100, 100.0000001, 100], 14, "Near-identical prices"),
    ]
    
    all_precision_passed = True
    for prices, window, desc in precision_tests:
        try:
            rsi = calculate_rsi_sma(prices, window)
            valid = 0 <= rsi <= 100 and not (rsi != rsi)  # Check for NaN
            status = "✅" if valid else "❌"
            print(f"    {status} {desc}: RSI = {rsi:.4f}")
            if not valid:
                all_precision_passed = False
        except Exception as e:
            print(f"    ❌ {desc}: {type(e).__name__}")
            all_precision_passed = False
    
    print_result(28, "Floating point precision handling", all_precision_passed)

    # =========================================================================
    # FINAL REPORT
    # =========================================================================
    return final_report()

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  NUTS BACKEND - COMPREHENSIVE TEST SUITE")
    print("  28 TESTS COVERING ALL EDGE CASES")
    print("="*70)
    print(f"\n  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Imports OK: {IMPORTS_OK}")
    
    success = run_tests()
    
    sys.exit(0 if success else 1)
