import React from "react";

const S = {
  container: {
    flexShrink: 0,
    maxHeight: 260,
    overflowY: "auto",
    background: "#161b22",
    borderTop: "1px solid #30363d",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
  },
  th: {
    padding: "8px 16px",
    textAlign: "left",
    color: "#8b949e",
    fontWeight: 600,
    borderBottom: "1px solid #21262d",
    background: "#1c2128",
    position: "sticky",
    top: 0,
    zIndex: 1,
  },
  td: {
    padding: "8px 16px",
    borderBottom: "1px solid #21262d",
    color: "#c9d1d9",
  },
  ticker: {
    color: "#58a6ff",
    fontWeight: 700,
  },
  pill: {
    display: "inline-block",
    padding: "3px 8px",
    background: "#21262d",
    border: "1px solid #30363d",
    borderRadius: 6,
    marginRight: 6,
    marginBottom: 4,
    fontSize: 11,
    color: "#8b949e",
  },
  pillVal: {
    color: "#e6edf3",
    fontWeight: 600,
    marginLeft: 4,
  }
};

export default function IndicatorSidebar({ indicators }) {
  // Graceful fallback if old cached data (dictionary) is still loading
  if (!Array.isArray(indicators)) return null;

  return (
    <div style={S.container}>
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>Ticker</th>
            <th style={S.th}>Current Price</th>
            <th style={S.th}>RSI (10)</th>
            <th style={S.th}>Specific Indicators</th>
          </tr>
        </thead>
        <tbody>
          {indicators.map((row) => (
            <tr key={row.ticker}>
              <td style={{ ...S.td, ...S.ticker }}>{row.ticker}</td>
              <td style={S.td}>${row.price?.toFixed(2) ?? "—"}</td>
              <td style={S.td}>{row.rsi_10 ?? "—"}</td>
              <td style={S.td}>
                {Object.entries(row.extras || {}).map(([key, val]) => (
                  <span key={key} style={S.pill}>
                    {key} <span style={S.pillVal}>{val}</span>
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
