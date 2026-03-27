/**
 * IndicatorSidebar — collapsible bottom panel.
 *
 * Columns: Ticker | Indicator | Window | Live Value | Distance | On Active Path
 * Sort:    active path rows first, then alphabetical
 * Colors:  green for active, amber for close call
 *
 * Includes a collapsible "Verification" section with raw RSI values.
 */

import React, { useState, useMemo } from "react";

const S = {
  container: {
    flexShrink: 0,
    maxHeight: 240,
    overflowY: "auto",
    background: "#161b22",
    borderTop: "1px solid #30363d",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 12,
  },
  th: {
    padding: "6px 12px",
    textAlign: "left",
    color: "#8b949e",
    fontWeight: 600,
    borderBottom: "1px solid #21262d",
    background: "#1c2128",
    position: "sticky",
    top: 0,
    zIndex: 1,
    whiteSpace: "nowrap",
  },
  td: (active, closeCall) => ({
    padding: "5px 12px",
    borderBottom: "1px solid #21262d",
    color: active ? "#22c55e" : closeCall ? "#f59e0b" : "#8b949e",
    background: active ? "#0f2d1a" : closeCall ? "#1c1a0f" : "transparent",
    whiteSpace: "nowrap",
  }),
  verSection: {
    padding: "8px 12px",
    background: "#1c2128",
    borderTop: "1px solid #30363d",
  },
  verToggle: {
    cursor: "pointer",
    color: "#58a6ff",
    fontSize: 12,
    fontWeight: 600,
    border: "none",
    background: "transparent",
    padding: 0,
    marginBottom: 6,
  },
  verGrid: {
    display: "flex",
    flexWrap: "wrap",
    gap: "4px 16px",
  },
  verItem: {
    fontSize: 11,
    color: "#8b949e",
    fontFamily: "monospace",
  },
};

function buildRows(indicators, frontrunners, ftlt) {
  if (!indicators) return [];

  const activeIds = new Set([
    ...(frontrunners?.active_path || []),
    ...(ftlt?.active_path || []),
  ]);

  // Map indicator keys to display rows
  const rows = [];
  const rsiRegex = /^(.+)_RSI_(\d+)$/;

  Object.entries(indicators).forEach(([key, value]) => {
    const rsiMatch = key.match(rsiRegex);
    if (rsiMatch) {
      const ticker = rsiMatch[1];
      const window = parseInt(rsiMatch[2]);

      // Find this ticker in any tree node
      const allNodes = [
        ...(frontrunners?.nodes || []),
        ...(ftlt?.nodes || []),
      ];
      const matchedNode = allNodes.find(
        (n) => n.ticker === ticker && n.indicator === "RSI" && n.window === window
      );

      const active = matchedNode ? activeIds.has(matchedNode.id) : false;
      const threshold = matchedNode?.threshold ?? null;
      const distance = threshold != null ? value - threshold : null;
      const closeCall = !active && distance != null && Math.abs(distance) <= 5;

      rows.push({
        key,
        ticker,
        indicator: `RSI(${window})`,
        window,
        liveValue: typeof value === "number" ? value.toFixed(2) : String(value),
        distance: distance != null ? (distance > 0 ? "+" : "") + distance.toFixed(2) : "—",
        active,
        closeCall,
        sortKey: active ? 0 : closeCall ? 1 : 2,
      });
    }
  });

  // Add MA indicators
  if (indicators.SPY_vs_200MA !== undefined) {
    const active = ftlt?.active_path?.includes("gate_spy_200ma");
    rows.push({
      key: "SPY_MA_200",
      ticker: "SPY",
      indicator: "MA(200)",
      window: 200,
      liveValue: `${indicators.SPY_price ?? "—"} vs ${indicators.SPY_200MA_value ?? "—"}`,
      distance: indicators.SPY_price != null && indicators.SPY_200MA_value != null
        ? ((indicators.SPY_price - indicators.SPY_200MA_value) > 0 ? "+" : "") +
          (indicators.SPY_price - indicators.SPY_200MA_value).toFixed(2)
        : "—",
      active: !!active,
      closeCall: false,
      sortKey: active ? 0 : 2,
    });
  }
  if (indicators.TQQQ_vs_20MA !== undefined) {
    const active = ftlt?.active_path?.includes("b5_tqqq_vs_ma20");
    rows.push({
      key: "TQQQ_MA_20",
      ticker: "TQQQ",
      indicator: "MA(20)",
      window: 20,
      liveValue: `${indicators.TQQQ_price ?? "—"} vs ${indicators.TQQQ_20MA_value ?? "—"}`,
      distance: indicators.TQQQ_price != null && indicators.TQQQ_20MA_value != null
        ? ((indicators.TQQQ_price - indicators.TQQQ_20MA_value) > 0 ? "+" : "") +
          (indicators.TQQQ_price - indicators.TQQQ_20MA_value).toFixed(2)
        : "—",
      active: !!active,
      closeCall: false,
      sortKey: active ? 0 : 2,
    });
  }

  // Sort: active first, close-call second, rest alphabetical
  rows.sort((a, b) => {
    if (a.sortKey !== b.sortKey) return a.sortKey - b.sortKey;
    return a.ticker.localeCompare(b.ticker);
  });

  return rows;
}

export default function IndicatorSidebar({ indicators, dataQuality, frontrunners, ftlt }) {
  const [verOpen, setVerOpen] = useState(false);

  const rows = useMemo(
    () => buildRows(indicators, frontrunners, ftlt),
    [indicators, frontrunners, ftlt]
  );

  // Verification data: raw RSI values for cross-checking
  const verItems = useMemo(() => {
    if (!indicators) return [];
    return Object.entries(indicators)
      .filter(([k]) => k.includes("_RSI_"))
      .map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(4) : v}`)
      .sort();
  }, [indicators]);

  return (
    <div style={S.container}>
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>Ticker</th>
            <th style={S.th}>Indicator</th>
            <th style={S.th}>Live Value</th>
            <th style={S.th}>Distance</th>
            <th style={S.th}>Active Path</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td style={S.td(row.active, row.closeCall)}>{row.ticker}</td>
              <td style={S.td(row.active, row.closeCall)}>{row.indicator}</td>
              <td style={S.td(row.active, row.closeCall)}>{row.liveValue}</td>
              <td style={S.td(row.active, row.closeCall)}>
                {row.closeCall ? `⚠️ ${row.distance}` : row.distance}
              </td>
              <td style={S.td(row.active, row.closeCall)}>
                {row.active ? "✓ Yes" : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Verification section */}
      <div style={S.verSection}>
        <button style={S.verToggle} onClick={() => setVerOpen((v) => !v)}>
          {verOpen ? "▼" : "▶"} Verification (raw RSI values for cross-checking)
        </button>
        {verOpen && (
          <div style={S.verGrid}>
            {verItems.map((item) => (
              <span key={item} style={S.verItem}>
                {item}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
