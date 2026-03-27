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

// ─── Leaf node ────────────────────────────────────────────────────────────────
function LeafNode({ node }) {
  const active = node.active;
  const ticker = node.outcome || "?";

  const filterDetails = node.filter_details;

  return (
    <div
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

  return (
    <div
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
  const { node, isLeaf } = data;
  if (!node) return null;
  return isLeaf ? <LeafNode node={node} /> : <CondNode node={node} />;
}

export default memo(NodeBox);
