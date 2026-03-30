/**
 * NodeBox — custom ReactFlow node.
 *
 * Active:     bright green background, white text
 * Inactive:   dark grey, 30% opacity, still readable
 * Close call: amber border + ⚠️  (only on inactive nodes)
 * Leaf:       large rounded rectangle
 */

import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Tooltip } from "react-tooltip";
import "react-tooltip/dist/react-tooltip.css";

// ─── Colors ───────────────────────────────────────────────────────────────────
const C = {
  activeBg:       "#0f2d1a",
  activeBorder:   "#22c55e",
  activeText:     "#e6edf3",
  activeAccent:   "#22c55e",
  inactiveBg:     "#161b22",
  inactiveBorder: "#30363d",
  inactiveText:   "#6b7280",
  closeBorder:    "#f59e0b",
  closeIcon:      "#f59e0b",
  leafActiveBg:   "#0f2d1a",
  leafActiveBorder: "#22c55e",
  leafInactiveBg: "#161b22",
  leafInactiveBorder: "#21262d",
};

// ─── Tooltip Logic ────────────────────────────────────────────────────────────
const ASSET_DESCRIPTIONS = {
  TQQQ: 'ProShares UltraPro QQQ (TQQQ) — 3× daily Nasdaq-100. Fires in a bull market when tech is not overbought.',
  VIXY: 'ProShares VIX Short-Term Futures (VIXY) — tracks near-term volatility index futures. Fires when a sector RSI is dangerously high.',
  UVXY: 'ProShares Ultra VIX Short-Term Futures (UVXY) — 1.5× VIX futures. Fires when TQQQ is overbought (RSI > 79).',
  SOXL: 'Direxion Daily Semiconductors Bull 3X (SOXL) — 3× daily semiconductor index. Fires when SOXX is deeply oversold, betting on a semis rebound.',
  TECL: 'Direxion Daily Technology Bull 3X (TECL) — 3× daily tech sector. Fires when QQQ is deeply oversold, betting on a tech rebound.',
  UPRO: 'ProShares UltraPro S&P 500 (UPRO) — 3× daily S&P 500. Fires when the broad market is deeply oversold, betting on a market-wide rebound.',
  SQQQ: 'ProShares UltraPro Short QQQ (SQQQ) — 3× inverse Nasdaq-100. Fires as a bearish bet when TQQQ drops below its 20-day moving average.',
  BIL:  'SPDR Bloomberg 1-3 Month T-Bill (BIL) — cash equivalent, near-zero risk. Parked here when no signal fires — preserves capital while waiting.',
  TLT:  'iShares 20+ Year Treasury Bond (TLT) — long-duration US government bonds. Competes with SQQQ; whichever has the lower RSI wins (more room to recover).',
  PSQ:  "ProShares Short QQQ (PSQ) — 1× inverse Nasdaq-100. Mild hedge; fires when VIXY's own RSI is too high to safely hold.",
  URTY: 'ProShares UltraPro Russell 2000 (URTY) — 3× daily small-cap index. Fires in a specific FTLT bear-regime branch when SH signals a short-term bounce.',
};

const PLAIN_QUESTIONS = {
  'SPY_RSI_>':   () => `Is the broad market overbought?`,
  'SPY_RSI_<':   () => `Is the broad market deeply oversold?`,
  'QQQ_RSI_>':   () => `Is tech overbought?`,
  'QQQ_RSI_<':   () => `Is tech deeply oversold?`,
  'VTV_RSI_>':   () => `Are value stocks overbought?`,
  'VOX_RSI_>':   () => `Is the comms sector overbought?`,
  'XLK_RSI_>':   () => `Is the tech sector ETF overbought?`,
  'XLP_RSI_>':   () => `Are consumer staples overbought?`,
  'XLF_RSI_>':   () => `Is the financial sector overbought?`,
  'SOXX_RSI_<':  () => `Are semiconductors deeply oversold?`,
  'TQQQ_RSI_>':  () => `Is TQQQ overbought?`,
  'TQQQ_RSI_<':  () => `Is TQQQ deeply oversold?`,
  'SPXL_RSI_>':  () => `Is SPXL overbought?`,
  'SQQQ_RSI_<':  () => `Is SQQQ deeply oversold?`,
  'SPY_MA_>':    (t) => `Is the market above its ${t}-day moving average? (bull regime)`,
  'SPY_MA_<':    (t) => `Is the market below its ${t}-day moving average? (bear regime)`,
  'TQQQ_MA_<':   (t) => `Is TQQQ below its ${t}-day moving average?`,
  'TQQQ_CUM_RET_<': (t) => `Did TQQQ drop more than ${Math.abs(t)}% recently? (crash signal)`,
  'QQQ_MAX_DD_>':   () => `Is QQQ's recent drawdown severe enough to act?`,
  'SPY_MA_40_>':    () => `Is the market above its 40-day moving average?`,
  'QQQ_MA_25_>':    () => `Is QQQ above its 25-day moving average?`,
};

function buildPlainQuestion(node) {
  const key = `${node.ticker}_${node.indicator}_${node.operator}`;
  const fn = PLAIN_QUESTIONS[key];
  return fn ? fn(node.threshold) : node.label;
}

function buildConditionTooltip(node) {
  const question = buildPlainQuestion(node);

  if (node.live_value == null) {
    return `${question} — no data available`;
  }

  const isPrice = node.indicator && node.indicator.includes('MA') && !node.indicator.includes('RSI');
  const pfx = isPrice ? '$' : '';
  
  let liveName = `${node.ticker} ${node.indicator}(${node.window})`;
  if (isPrice) liveName = node.ticker;
  
  const live = `${liveName} = ${pfx}${node.live_value?.toFixed(2)}`;
  
  const gapAbsNum = node.distance;
  const gapAbsStr = gapAbsNum != null ? Math.abs(gapAbsNum).toFixed(2) : null;
  const gapAbs = gapAbsNum != null 
    ? `${gapAbsNum > 0 ? '+' : gapAbsNum < 0 ? '−' : ''}${pfx}${gapAbsStr}` 
    : '—';
    
  const gapPctNum = node.live_value 
    ? (node.distance / node.live_value) * 100 
    : null;
    
  const gapPct = gapPctNum != null ? Math.abs(gapPctNum).toFixed(1) : null;
  const gapPctStr = gapPctNum != null 
    ? `${gapPctNum > 0 ? '+' : gapPctNum < 0 ? '−' : ''}${gapPct}%` 
    : null;

  const gapStr = gapPctStr
    ? `gap: ${gapAbs} / ${gapPctStr}`
    : `gap: ${gapAbs}`;
    
  const warning = node.close_call ? ' ⚠️ Close call' : '';

  return [question, `${live} (need ${node.operator} ${pfx}${node.threshold}, ${gapStr})${warning}`]
    .filter(Boolean)
    .join(' — ');
}

// ─── Leaf node ────────────────────────────────────────────────────────────────
function LeafNode({ node }) {
  const active = node.active;
  const ticker = node.outcome || "?";

  const filterDetails = node.filter_details;
  const tooltipId = `tooltip-${node.id}`;

  return (
    <div
      data-tooltip-id={tooltipId}
      data-tooltip-delay-show={200}
      data-tooltip-delay-hide={150}
      style={{
        width: 160,
        minHeight: 70,
        borderRadius: 12,
        background: active ? C.leafActiveBg : C.leafInactiveBg,
        border: `2px solid ${active ? C.leafActiveBorder : C.leafInactiveBorder}`,
        opacity: active ? 1 : 0.35,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "10px 12px",
        gap: 4,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "transparent", border: "none" }} />

      <div
        style={{
          fontSize: 22,
          fontWeight: 800,
          color: active ? C.activeAccent : C.inactiveText,
          letterSpacing: "-0.5px",
        }}
      >
        → {ticker}
      </div>

      {filterDetails && (
        <div style={{ fontSize: 9, color: active ? "#86efac" : "#484f58", textAlign: "center", lineHeight: 1.4 }}>
          SQQQ {filterDetails.SQQQ_RSI} vs TLT {filterDetails.TLT_RSI}
          <br />
          {filterDetails.winner} wins (lower RSI)
        </div>
      )}
    </div>
  );
}

// ─── Condition node ───────────────────────────────────────────────────────────
function CondNode({ node }) {
  const active = node.active;
  const isClosecall = node.close_call && !active;
  const isMaGate = node.display_type === "ma_gate";

  const borderColor = active
    ? C.activeBorder
    : isClosecall
    ? C.closeBorder
    : C.inactiveBorder;

  const textColor = active ? C.activeText : C.inactiveText;
  const accentColor = active ? C.activeAccent : C.inactiveText;
  const tooltipId = `tooltip-${node.id}`;

  return (
    <div
      data-tooltip-id={tooltipId}
      data-tooltip-delay-show={200}
      data-tooltip-delay-hide={150}
      style={{
        width: 200,
        minHeight: 110,
        borderRadius: 8,
        background: active ? C.activeBg : C.inactiveBg,
        border: `2px solid ${borderColor}`,
        opacity: active ? 1 : 0.35,
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 3,
        position: "relative",
        boxShadow: active ? `0 0 12px rgba(34,197,94,0.15)` : "none",
      }}
    >
      <Handle type="target" position={Position.Left}  style={{ background: borderColor, border: "none", width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: borderColor, border: "none", width: 8, height: 8 }} />

      {isClosecall && (
        <span
          style={{
            position: "absolute",
            top: 6,
            right: 8,
            fontSize: 12,
            title: "Close call — within 5 of trigger",
          }}
        >
          ⚠️
        </span>
      )}

      {/* Line 1: Ticker + Indicator */}
      <div style={{ fontSize: 13, fontWeight: 700, color: accentColor }}>
        {node.ticker}&nbsp;&nbsp;
        <span style={{ fontWeight: 400, opacity: 0.8 }}>
          {node.indicator === "RSI"
            ? `RSI(${node.window})`
            : node.indicator === "MA"
            ? `MA(${node.window})`
            : node.indicator || ""}
        </span>
      </div>

      {/* MA Gate: special 2-line layout */}
      {isMaGate ? (
        <>
          <div style={{ fontSize: 11, color: textColor }}>
            {node.operator === ">"
              ? `Price > MA?  ${node.result ? "✓ YES" : "✗ NO"}`
              : `Price < MA?  ${node.result ? "✓ YES" : "✗ NO"}`}
          </div>
          <div style={{ fontSize: 11, color: textColor, opacity: 0.8 }}>
            Price: {node.price_value ?? node.live_value}
            &nbsp; MA: {node.ma_value ?? node.threshold}
          </div>
          <div
            style={{
              fontSize: 11,
              color: accentColor,
              fontWeight: 600,
            }}
          >
            {node.distance != null
              ? `${node.distance > 0 ? "+" : ""}${node.distance.toFixed(2)} ${node.distance >= 0 ? "above" : "below"}`
              : "—"}
          </div>
        </>
      ) : (
        <>
          {/* Line 2: Condition */}
          <div style={{ fontSize: 12, color: textColor }}>
            {node.operator} {node.threshold}
          </div>
          {/* Line 3: Live value */}
          <div style={{ fontSize: 11, color: textColor, opacity: 0.85 }}>
            Current: {node.live_value ?? "—"}
          </div>
          {/* Line 4: Distance */}
          <div
            style={{
              fontSize: 11,
              color: isClosecall ? C.closeIcon : accentColor,
              fontWeight: 600,
            }}
          >
            {node.distance != null
              ? `${node.distance > 0 ? "+" : ""}${node.distance.toFixed(2)} from trigger`
              : "—"}
          </div>
        </>
      )}
    </div>
  );
}

// ─── NodeBox (exported) ────────────────────────────────────────────────────────
function NodeBox({ data }) {
  const { node, isLeaf, activeChain, tabName, computedAt, onOpenPanel } = data;
  if (!node) return null;

  const tooltipId = `tooltip-${node.id}`;
  const isOutcome = !!node.outcome;
  const isActive = node.active;

  const tooltipContent = isOutcome
    ? (ASSET_DESCRIPTIONS[node.outcome] ?? node.outcome)
    : buildConditionTooltip(node);

  return (
    <>
      {isLeaf ? <LeafNode node={node} /> : <CondNode node={node} />}
      <Tooltip
        id={tooltipId}
        place="top"
        style={{ maxWidth: "420px", fontSize: "12px", background: "#1a1a2e", zIndex: 1000 }}
      >
        <span style={{ opacity: isActive ? 1 : 0.55 }}>{tooltipContent}</span>
        {isActive && (
          <button
            style={{
              display: "inline-block",
              marginLeft: "8px",
              background: "none",
              border: "none",
              color: "inherit",
              opacity: 0.3,
              cursor: "pointer",
              fontSize: "13px",
              padding: 0,
              lineHeight: 1,
              verticalAlign: "middle"
            }}
            onMouseOver={(e) => e.target.style.opacity = 0.75}
            onMouseOut={(e) => e.target.style.opacity = 0.3}
            onClick={(e) => {
              e.stopPropagation();
              if (onOpenPanel) {
                onOpenPanel({ chain: activeChain, highlightNodeId: node.id, tabName, computedAt });
              }
            }}
          >
            ⋯
          </button>
        )}
      </Tooltip>
    </>
  );
}

export default memo(NodeBox);
