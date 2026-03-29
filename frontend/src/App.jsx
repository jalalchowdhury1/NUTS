import React, { useState, useEffect, useCallback, useRef } from "react";
import DecisionTree from "./components/DecisionTree.jsx";
import IndicatorSidebar from "./components/IndicatorSidebar.jsx";

const API_URL = import.meta.env.VITE_API_URL || "";
const REFRESH_INTERVAL_MS = 60 * 60 * 1000; // 60 minutes

// ─── Color helpers ────────────────────────────────────────────────────────────
const SIGNAL_COLOR = {
  // Vol hedges
  VIXY: "#f59e0b", UVXY: "#f59e0b",
  // Leveraged longs
  TQQQ: "#22c55e", SOXL: "#22c55e", TECL: "#22c55e",
  UPRO: "#22c55e", SPXL: "#22c55e", FNGU: "#22c55e",
  URTY: "#22c55e",
  // Bear/short
  SQQQ: "#ef4444", SH: "#ef4444", PSQ: "#ef4444",
  // Cash / bonds
  BIL: "#94a3b8", TLT: "#94a3b8", BND: "#94a3b8",
  IEF: "#94a3b8", TMF: "#94a3b8",
  // Default
  "→ FTLT": "#6b7280",
};

function signalColor(ticker) {
  return SIGNAL_COLOR[ticker] || "#e6edf3";
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const S = {
  app: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: "#0d1117",
    color: "#e6edf3",
    fontFamily: "'Inter', system-ui, sans-serif",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 24px",
    background: "#161b22",
    borderBottom: "1px solid #30363d",
    flexShrink: 0,
    gap: 16,
  },
  headerLeft: { display: "flex", alignItems: "center", gap: 12 },
  title: { fontSize: 18, fontWeight: 700, color: "#e6edf3", letterSpacing: "-0.3px" },
  signal: { fontSize: 22, fontWeight: 800, letterSpacing: "-0.5px" },
  headerRight: { display: "flex", alignItems: "center", gap: 12, flexShrink: 0 },
  lastUpdated: { fontSize: 12, color: "#8b949e" },
  refreshBtn: {
    background: "#21262d",
    color: "#e6edf3",
    border: "1px solid #30363d",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    transition: "background 0.15s",
  },
  tabs: {
    display: "flex",
    gap: 0,
    padding: "0 24px",
    background: "#161b22",
    borderBottom: "1px solid #30363d",
    flexShrink: 0,
  },
  tab: (active, dimmed, locked) => ({
    padding: "10px 20px",
    fontSize: 14,
    fontWeight: 600,
    cursor: locked ? "not-allowed" : "pointer",
    border: "none",
    background: "transparent",
    color: locked ? "#484f58" : dimmed ? "#484f58" : active ? "#e6edf3" : "#8b949e",
    borderBottom: active ? "2px solid #58a6ff" : "2px solid transparent",
    opacity: dimmed ? 0.45 : 1,
    transition: "all 0.15s",
    display: "flex",
    alignItems: "center",
    gap: 6,
  }),
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    position: "relative",
  },
  treeArea: {
    flex: 1,
    overflow: "hidden",
    position: "relative",
  },
  banner: {
    background: "#1c2128",
    border: "1px solid #f59e0b",
    borderRadius: 8,
    padding: "10px 18px",
    margin: "12px 24px 0",
    fontSize: 13,
    color: "#f59e0b",
    flexShrink: 0,
  },
  loadingOverlay: {
    position: "absolute",
    inset: 0,
    background: "rgba(13,17,23,0.75)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 100,
    gap: 14,
  },
  spinner: {
    width: 36,
    height: 36,
    border: "3px solid #30363d",
    borderTopColor: "#58a6ff",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  loadingMsg: { color: "#8b949e", fontSize: 14 },
  errorBanner: {
    background: "#1c2128",
    border: "1px solid #ef4444",
    borderRadius: 8,
    padding: "10px 18px",
    margin: "12px 24px",
    fontSize: 13,
    color: "#ef4444",
  },
  comingSoon: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    color: "#484f58",
  },
};

// ─── Format Eastern time ──────────────────────────────────────────────────────
function formatET(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }) + " ET";
  } catch {
    return isoString;
  }
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMsg, setLoadingMsg] = useState("Fetching live data...");
  const [apiError, setApiError] = useState(null);
  const [activeTab, setActiveTab] = useState("frontrunners");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const timerRef = useRef(null);

  const fetchData = useCallback(async (force = false) => {
    setLoading(true);
    setLoadingMsg(force ? "Downloading fresh market data..." : "Fetching live data...");
    setApiError(null);

    const url = `${API_URL}/evaluate${force ? "?force=true" : ""}`;

    try {
      const res = await fetch(url);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
      }
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      setData(json);
    } catch (err) {
      console.error("Fetch error:", err);
      setApiError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + auto-refresh
  useEffect(() => {
    fetchData(false);
    timerRef.current = setInterval(() => fetchData(false), REFRESH_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchData]);

  const finalResult = data?.final_result;
  const finalSource = data?.final_source;

  // Tab state
  const frFired = data?.frontrunners?.fired;
  const ftltActive = !frFired; // FTLT is the active source when FR didn't fire

  const tabFR = activeTab === "frontrunners";
  const tabFTLT = activeTab === "ftlt";
  const tabBS = activeTab === "blackswan";

  // Dimmed: the branch that is NOT the source of today's signal
  const frDimmed = !frFired && !!data;
  const ftltDimmed = frFired && !!data;

  // Current tree data for rendering
  const treeData = tabFR ? data?.frontrunners : tabFTLT ? data?.ftlt : tabBS ? data?.blackswan : null;
  const showNotSourceBanner =
    data && ((tabFR && frDimmed) || (tabFTLT && ftltDimmed));

  return (
    <div style={S.app}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        button:hover { filter: brightness(1.15); }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #161b22; }
        ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
      `}</style>

      {/* ── Header ── */}
      <header style={S.header}>
        <div style={S.headerLeft}>
          <span style={S.title}>NUTS Algo</span>
          {finalResult && (
            <span style={{ ...S.signal, color: signalColor(finalResult) }}>
              ⚡ CURRENT SIGNAL: {finalResult}
            </span>
          )}
          {!finalResult && !loading && (
            <span style={{ color: "#484f58", fontSize: 16 }}>⚡ No signal yet</span>
          )}
        </div>
        <div style={S.headerRight}>
          {data?.evaluated_at && (
            <span style={S.lastUpdated}>
              {data.cache_hit ? "Cached" : "Updated"}: {formatET(data.evaluated_at)}
            </span>
          )}
          <button
            style={S.refreshBtn}
            onClick={() => fetchData(true)}
            disabled={loading}
          >
            {loading ? "Loading..." : "Force Refresh"}
          </button>
        </div>
      </header>

      {/* ── Tabs ── */}
      <nav style={S.tabs}>
        <button
          style={S.tab(tabFR, frDimmed, false)}
          onClick={() => setActiveTab("frontrunners")}
        >
          {frFired ? "●" : "○"} Frontrunners
          {frFired && <span style={{ fontSize: 11, color: "#22c55e" }}>ACTIVE</span>}
        </button>
        <button
          style={S.tab(tabFTLT, ftltDimmed, false)}
          onClick={() => setActiveTab("ftlt")}
        >
          {ftltActive ? "●" : "○"} FTLT
          {ftltActive && !!data && <span style={{ fontSize: 11, color: "#22c55e" }}>ACTIVE</span>}
        </button>
        <button
          style={S.tab(tabBS, false, false)}
          onClick={() => setActiveTab("blackswan")}
        >
          {tabBS ? "●" : "○"} BlackSwan
        </button>
        <button
          style={{
            ...S.tab(false, false, false),
            marginLeft: "auto",
            fontSize: 12,
            color: "#8b949e",
          }}
          onClick={() => setSidebarOpen((v) => !v)}
        >
          {sidebarOpen ? "▼ Indicators" : "▶ Indicators"}
        </button>
      </nav>

      {/* ── Main ── */}
      <div style={S.main}>
        {/* Error banner (stale data) */}
        {apiError && (
          <div style={S.errorBanner}>
            ⚠️ Live data unavailable — {data ? `showing cached result from ${formatET(data.evaluated_at)}` : "no data available"}.
            <br />
            <span style={{ opacity: 0.7, fontSize: 12 }}>{apiError}</span>
          </div>
        )}

        {/* Download errors */}
        {data?.download_errors?.length > 0 && (
          <div style={{ ...S.errorBanner, borderColor: "#f59e0b", color: "#f59e0b" }}>
            ⚠️ Data errors for: {data.download_errors.map((e) => `${e.ticker} (${e.error})`).join(", ")}
          </div>
        )}

        {/* "Not source" banner */}
        {showNotSourceBanner && (
          <div style={S.banner}>
            ⚠️ This branch was not the source of today's signal. Showing live values for reference.
          </div>
        )}

        {/* Tree area */}
        <div style={S.treeArea}>
          {treeData ? (
            <DecisionTree
              branch={activeTab}
              treeData={treeData}
              key={activeTab}
            />
          ) : loading ? null : (
            <div style={S.comingSoon}>
              <div style={{ fontSize: 14, color: "#484f58" }}>No data available</div>
            </div>
          )}

          {/* Loading overlay — keep last result visible underneath */}
          {loading && (
            <div style={S.loadingOverlay}>
              <div style={S.spinner} />
              <div style={S.loadingMsg}>{loadingMsg}</div>
            </div>
          )}
        </div>

        {/* Indicator sidebar */}
        {sidebarOpen && data && (
          <IndicatorSidebar
            indicators={data.indicators}
            dataQuality={data.data_quality}
            frontrunners={data.frontrunners}
            ftlt={data.ftlt}
          />
        )}
      </div>
    </div>
  );
}
