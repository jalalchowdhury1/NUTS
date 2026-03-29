"""
NUTS Backend - Bull Market Scenario Demo
This shows what the output would look like when SPY is ABOVE its 200d MA (Bull Regime)
"""

dummy_response_bull = {
    'cache_hit': False,
    'frontrunners': {
        'fired': False,
        'result': '→ FTLT',
        'active_path': ['fr_node_1', 'fr_node_2', 'fr_node_3', 'fr_node_4', 'fr_node_5',
                       'fr_node_6', 'fr_node_7', 'fr_node_8', 'fr_node_9', 'fr_node_10', 'fr_default'],
        'nodes': [
            {'id': 'fr_node_1', 'label': 'SPY RSI(10) > 80', 'ticker': 'SPY', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 80, 'live_value': 65.27, 'distance': -14.73, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_2', 'label': 'QQQ RSI(10) > 79', 'ticker': 'QQQ', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 79, 'live_value': 62.51, 'distance': -16.49, 'result': False, 'active': True, 'close_call': False, 'outcome': 'VIXY'},
            {'id': 'fr_node_3', 'label': 'VTV RSI(10) > 79', 'ticker': 'VTV', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 79, 'live_value': 58.23, 'distance': -20.77, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_4', 'label': 'VOX RSI(10) > 84', 'ticker': 'VOX', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 84, 'live_value': 71.88, 'distance': -12.12, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_5', 'label': 'XLK RSI(10) > 79', 'ticker': 'XLK', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 79, 'live_value': 69.44, 'distance': -9.56, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_6', 'label': 'XLP RSI(10) > 75', 'ticker': 'XLP', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 75, 'live_value': 61.32, 'distance': -13.68, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_7', 'label': 'XLF RSI(10) > 80', 'ticker': 'XLF', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 80, 'live_value': 67.81, 'distance': -12.19, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_8', 'label': 'SOXX RSI(10) < 30', 'ticker': 'SOXX', 'indicator': 'RSI', 'window': 10, 'operator': '<', 'threshold': 30, 'live_value': 45.63, 'distance': 15.63, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_node_9', 'label': 'QQQ RSI(10) < 30', 'ticker': 'QQQ', 'indicator': 'RSI', 'window': 10, 'operator': '<', 'threshold': 30, 'live_value': 62.51, 'distance': 32.51, 'result': False, 'active': True, 'close_call': False, 'outcome': 'VIXY'},
            {'id': 'fr_node_10', 'label': 'SPY RSI(10) < 30', 'ticker': 'SPY', 'indicator': 'RSI', 'window': 10, 'operator': '<', 'threshold': 30, 'live_value': 65.27, 'distance': 35.27, 'result': False, 'active': True, 'close_call': False, 'outcome': 'UVXY'},
            {'id': 'fr_default', 'label': 'No condition fired → FTLT', 'is_leaf': True, 'active': True}
        ]
    },
    'ftlt': {
        'fired': True,
        'result': 'UVXY',
        'active_path': ['gate_spy_200ma', 'b1_tqqq_rsi_high', 'b2_spxl_rsi_high', 'leaf_uvxy_bull'],
        'nodes': [
            {'id': 'gate_spy_200ma', 'label': 'SPY vs 200d MA', 'ticker': 'SPY', 'indicator': 'MA', 'window': 200, 'live_value': 512.10, 'threshold': 498.30, 'result': True, 'active': True, 'close_call': False, 'ma_value': 498.30, 'price_value': 512.10},
            {'id': 'b1_tqqq_rsi_high', 'label': 'TQQQ RSI(10) > 79', 'ticker': 'TQQQ', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 79, 'live_value': 54.20, 'distance': -24.80, 'result': False, 'active': True, 'close_call': False},
            {'id': 'b2_spxl_rsi_high', 'label': 'SPXL RSI(10) > 80', 'ticker': 'SPXL', 'indicator': 'RSI', 'window': 10, 'operator': '>', 'threshold': 80, 'live_value': 82.45, 'distance': 2.45, 'result': True, 'active': True, 'close_call': True},
            {'id': 'leaf_uvxy_bull', 'label': '→ UVXY', 'is_leaf': True, 'active': True}
        ]
    },
    'final_result': 'UVXY',
    'final_source': 'ftlt',
    'indicators': {
        'SPY_RSI_10': 65.27, 'QQQ_RSI_10': 62.51, 'TQQQ_RSI_10': 54.20,
        'SPXL_RSI_10': 82.45, 'SQQQ_RSI_10': 28.33, 'TLT_RSI_10': 55.48,
        'SPY_price': 512.10, 'SPY_vs_200MA': True, 'SPY_200MA_value': 498.30,
        'TQQQ_price': 84.50, 'TQQQ_vs_20MA': True, 'TQQQ_20MA_value': 82.30
    },
    'data_quality': {
        'SPY': {'rows': 206, 'last_date': '2026-03-28', 'last_close': 512.10},
        'QQQ': {'rows': 206, 'last_date': '2026-03-28', 'last_close': 441.20}
    },
    'evaluated_at': '2026-03-28T14:30:00-0400'
}

print('╔══════════════════════════════════════════════════════════════╗')
print('║      NUTS BACKEND — BULL MARKET SCENARIO (DUMMY DATA)      ║')
print('╚══════════════════════════════════════════════════════════════╝')
print()
print('='*70)
print('FRONTRUNNERS TREE')
print('='*70)
print()
print('  STEP BY STEP TRAVERSAL:')
print()
for node in dummy_response_bull['frontrunners']['nodes']:
    if node.get('is_leaf'):
        print(f'  → {node["label"]}')
    elif node.get('ticker'):
        result_str = 'True' if node['result'] else 'False'
        next_step = node['outcome'] if node['result'] else 'continue'
        print(f'  Step: {node["label"]}? → {result_str} ({node["live_value"]}) → {next_step}')

print()
print(f'  RESULT: {dummy_response_bull["frontrunners"]["result"]}')
print(f'  FIRED: {dummy_response_bull["frontrunners"]["fired"]}')

print()
print('='*70)
print('FTLT TREE — BULL REGIME PATH')
print('='*70)
print()
print('  GATE CHECK:')
gate = dummy_response_bull['ftlt']['nodes'][0]
regime = 'Bull Regime' if gate['result'] else 'Bear Regime'
print(f'  SPY (${gate["price_value"]}) > 200d MA (${gate["ma_value"]})? → {gate["result"]} → {regime}')
print()
print('  BULL PATH: B1 → B2')
print()
for node in dummy_response_bull['ftlt']['nodes'][1:]:
    if node.get('is_leaf') and node.get('active'):
        print(f'  → {node["label"]}')
    elif node.get('active') and not node.get('is_leaf'):
        result_str = 'True' if node['result'] else 'False'
        status = '⚠️ CLOSE CALL' if node.get('close_call') else ''
        print(f'  {node["label"]}? → {result_str} ({node["live_value"]}) {status}')

print()
print(f'  RESULT: {dummy_response_bull["ftlt"]["result"]}')
print(f'  FIRED: {dummy_response_bull["ftlt"]["fired"]}')

print()
print('='*70)
print('FINAL SIGNAL')
print('='*70)
print()
print(f'  SIGNAL:    {dummy_response_bull["final_result"]}')
print(f'  SOURCE:    {dummy_response_bull["final_source"]}')
print(f'  EVALUATED: {dummy_response_bull["evaluated_at"]}')

print()
print('='*70)
print('INDICATORS')
print('='*70)
print()
print('  Ticker  | RSI(10) | Last Close')
print('  ' + '-'*35)
for ticker in ['SPY', 'QQQ', 'TQQQ', 'SPXL', 'SQQQ', 'TLT']:
    rsi_key = f'{ticker}_RSI_10'
    if rsi_key in dummy_response_bull['indicators']:
        print(f'  {ticker:<6} | {dummy_response_bull["indicators"][rsi_key]:>7.2f} |')

print()
print('  SPY Analysis:')
print(f'    Current Price:  ${dummy_response_bull["indicators"]["SPY_price"]:.2f}')
print(f'    200d SMA:       ${dummy_response_bull["indicators"]["SPY_200MA_value"]:.2f}')
print(f'    Position:        {"ABOVE" if dummy_response_bull["indicators"]["SPY_vs_200MA"] else "BELOW"}')

print()
print('  TQQQ Analysis:')
print(f'    Current Price:  ${dummy_response_bull["indicators"]["TQQQ_price"]:.2f}')
print(f'    20d SMA:        ${dummy_response_bull["indicators"]["TQQQ_20MA_value"]:.2f}')
print(f'    Position:        {"ABOVE" if dummy_response_bull["indicators"]["TQQQ_vs_20MA"] else "BELOW"}')

print()
print('='*70)
print('CLOSE CALLS')
print('='*70)
print()
print('  ⚠️  CLOSE CALL: SPXL RSI(10) = 82.45, threshold = 80')
print('      (distance = 2.45)')
print()
print('  This is flagged because SPXL is within 5 points of the 80 threshold.')
