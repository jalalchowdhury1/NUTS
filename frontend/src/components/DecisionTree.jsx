/**
 * DecisionTree — renders a left-to-right flowchart using @xyflow/react + dagre.
 *
 * Active path: bright green nodes + connectors
 * Inactive:    dark grey, 30% opacity, grey connectors
 * Close call:  amber border + ⚠️ icon (abs(distance) ≤ 5)
 * Leaf nodes:  rounded rectangles
 */

import React, { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import NodeBox from "./NodeBox.jsx";

// ─── Constants ────────────────────────────────────────────────────────────────
const NODE_W = 200;
const NODE_H = 110;
const LEAF_W = 160;
const LEAF_H = 70;
const RANK_SEP = 120;
const NODE_SEP = 60;

const ACTIVE_EDGE_COLOR = "#22c55e";
const INACTIVE_EDGE_COLOR = "#30363d";

// ─── Custom node types ────────────────────────────────────────────────────────
const nodeTypes = { nutsNode: NodeBox };

// ─── Build Frontrunners graph ────────────────────────────────────────────────
/**
 * Frontrunners is a linear chain:
 *   Node1 ──YES──> Leaf1
 *     └─NO─> Node2 ──YES──> Leaf2 ...  └─NO─> DefaultLeaf
 */
function buildFrontrunnersGraph(treeData) {
  const { nodes: apiNodes, active_path } = treeData;
  const activeSet = new Set(active_path);

  const rfNodes = [];
  const rfEdges = [];

  // Separate condition nodes from leaf nodes
  const condNodes = apiNodes.filter((n) => !n.is_leaf && n.id !== "fr_default");
  const leafNodes = apiNodes.filter((n) => n.is_leaf || n.id === "fr_default");
  const leafByParent = {};
  leafNodes.forEach((ln) => {
    // Leaf id convention: "leaf_fr_node_X" → parent is "fr_node_X"
    const parentId = ln.id.replace(/^leaf_/, "");
    leafByParent[parentId] = ln;
  });

  // Dagre layout
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", ranksep: RANK_SEP, nodesep: NODE_SEP });

  condNodes.forEach((n) => {
    g.setNode(n.id, { width: NODE_W, height: NODE_H });
  });
  leafNodes.forEach((n) => {
    g.setNode(n.id, { width: LEAF_W, height: LEAF_H });
  });

  // Chain: cond[i] --NO--> cond[i+1], cond[i] --YES--> leaf[i]
  condNodes.forEach((n, i) => {
    // YES → leaf
    const leaf = leafByParent[n.id];
    if (leaf) {
      g.setEdge(n.id, leaf.id);
    }
    // NO → next cond node
    if (i < condNodes.length - 1) {
      g.setEdge(n.id, condNodes[i + 1].id);
    }
  });
  // Last cond → default leaf
  const defaultLeaf = leafNodes.find((l) => l.id === "fr_default");
  if (defaultLeaf && condNodes.length > 0) {
    g.setEdge(condNodes[condNodes.length - 1].id, defaultLeaf.id);
  }

  dagre.layout(g);

  [...condNodes, ...leafNodes].forEach((n) => {
    const pos = g.node(n.id);
    if (!pos) return;
    rfNodes.push({
      id: n.id,
      type: "nutsNode",
      position: { x: pos.x - (n.is_leaf ? LEAF_W : NODE_W) / 2, y: pos.y - (n.is_leaf ? LEAF_H : NODE_H) / 2 },
      data: { node: n, isLeaf: !!n.is_leaf },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });
  });

  // Edges
  condNodes.forEach((n, i) => {
    const leaf = leafByParent[n.id];
    if (leaf) {
      const isActive = activeSet.has(n.id) && activeSet.has(leaf.id);
      rfEdges.push(makeEdge(n.id, leaf.id, "YES", isActive));
    }
    if (i < condNodes.length - 1) {
      const next = condNodes[i + 1];
      const isActive = activeSet.has(n.id) && activeSet.has(next.id);
      rfEdges.push(makeEdge(n.id, next.id, "NO", isActive));
    }
  });
  if (defaultLeaf && condNodes.length > 0) {
    const lastCond = condNodes[condNodes.length - 1];
    const isActive = activeSet.has(lastCond.id) && activeSet.has(defaultLeaf.id);
    rfEdges.push(makeEdge(lastCond.id, defaultLeaf.id, "NO", isActive));
  }

  return { rfNodes, rfEdges };
}

// ─── Build FTLT graph ────────────────────────────────────────────────────────
/**
 * FTLT is a binary tree with a gate + bull/bear branches.
 *
 * We define the parent-child relationships explicitly, then run dagre.
 */
const FTLT_EDGES_DEF = [
  // From gate
  { src: "gate_spy_200ma", dst: "b1_tqqq_rsi_high", label: "YES (Bull)" },
  { src: "gate_spy_200ma", dst: "b3_tqqq_rsi_low",  label: "NO (Bear)" },
  // Bull
  { src: "b1_tqqq_rsi_high", dst: "leaf_uvxy_b1",      label: "YES" },
  { src: "b1_tqqq_rsi_high", dst: "b2_spxl_rsi_high",  label: "NO" },
  { src: "b2_spxl_rsi_high", dst: "leaf_uvxy_b2",      label: "YES" },
  { src: "b2_spxl_rsi_high", dst: "leaf_tqqq_bull",    label: "NO" },
  // Bear
  { src: "b3_tqqq_rsi_low",  dst: "leaf_tecl",         label: "YES" },
  { src: "b3_tqqq_rsi_low",  dst: "b4_spy_rsi_low",    label: "NO" },
  { src: "b4_spy_rsi_low",   dst: "leaf_upro",         label: "YES" },
  { src: "b4_spy_rsi_low",   dst: "b5_tqqq_vs_ma20",   label: "NO" },
  { src: "b5_tqqq_vs_ma20",  dst: "leaf_rsi_filter",   label: "YES" },
  { src: "b5_tqqq_vs_ma20",  dst: "b6_sqqq_rsi_low",   label: "NO" },
  { src: "b6_sqqq_rsi_low",  dst: "leaf_sqqq",         label: "YES" },
  { src: "b6_sqqq_rsi_low",  dst: "leaf_tqqq_bear",    label: "NO" },
];

const LEAF_IDS = new Set([
  "leaf_uvxy_b1", "leaf_uvxy_b2", "leaf_tqqq_bull",
  "leaf_tecl", "leaf_upro", "leaf_rsi_filter",
  "leaf_sqqq", "leaf_tqqq_bear",
]);

function buildFtltGraph(treeData) {
  const { nodes: apiNodes, active_path } = treeData;
  const activeSet = new Set(active_path);
  const nodeById = Object.fromEntries(apiNodes.map((n) => [n.id, n]));

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", ranksep: RANK_SEP + 20, nodesep: NODE_SEP + 20 });

  apiNodes.forEach((n) => {
    const isLeaf = LEAF_IDS.has(n.id);
    g.setNode(n.id, { width: isLeaf ? LEAF_W : NODE_W, height: isLeaf ? LEAF_H : NODE_H });
  });

  FTLT_EDGES_DEF.forEach(({ src, dst }) => {
    if (nodeById[src] && nodeById[dst]) {
      g.setEdge(src, dst);
    }
  });

  dagre.layout(g);

  const rfNodes = [];
  apiNodes.forEach((n) => {
    const pos = g.node(n.id);
    if (!pos) return;
    const isLeaf = LEAF_IDS.has(n.id);
    rfNodes.push({
      id: n.id,
      type: "nutsNode",
      position: {
        x: pos.x - (isLeaf ? LEAF_W : NODE_W) / 2,
        y: pos.y - (isLeaf ? LEAF_H : NODE_H) / 2,
      },
      data: { node: n, isLeaf },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });
  });

  const rfEdges = [];
  FTLT_EDGES_DEF.forEach(({ src, dst, label }) => {
    if (!nodeById[src] || !nodeById[dst]) return;
    const isActive = activeSet.has(src) && activeSet.has(dst);
    rfEdges.push(makeEdge(src, dst, label, isActive));
  });

  return { rfNodes, rfEdges };
}

// ─── Build BlackSwan graph ────────────────────────────────────────────────────
const BS_LEAF_IDS = new Set([
  "leaf_uvxy_gate",
  "leaf_bs_uvxy", "leaf_bs_tqqq_b3", "leaf_bs_tqqq_b4", "leaf_bs_bil",
  "leaf_nma_bil_1", "leaf_nma_urty",
  "leaf_nma_tqqq_3a", "leaf_nma_bil_3a", "leaf_nma_bil_3",
  "leaf_nma_uvxy", "leaf_nma_psq", "leaf_nma_tqqq_5",
  "leaf_nma_tqqq_6a", "leaf_nma_bil_6a", "leaf_nma_bil_6",
  "leaf_nmb_bil_1", "leaf_nmb_bil_2", "leaf_nmb_tqqq_3",
  "leaf_nmb_tqqq_4a", "leaf_nmb_bil_4a",
  "leaf_nmb_tqqq_5a", "leaf_nmb_bil_5a", "leaf_nmb_bil_5",
]);

const BS_EDGES_DEF = [
  // Gate
  { src: "gate_tqqq_rsi",         dst: "leaf_uvxy_gate",          label: "YES" },
  { src: "gate_tqqq_rsi",         dst: "bs1_tqqq_cumret_6d",      label: "NO" },
  { src: "gate_tqqq_rsi",         dst: "nma1_qqq_maxdd",          label: "NO" },
  { src: "gate_tqqq_rsi",         dst: "nmb1_qqq_maxdd",          label: "NO" },
  // BS sub-path
  { src: "bs1_tqqq_cumret_6d",    dst: "bs2_tqqq_cumret_1d",      label: "YES" },
  { src: "bs2_tqqq_cumret_1d",    dst: "leaf_bs_uvxy",            label: "YES" },
  { src: "bs2_tqqq_cumret_1d",    dst: "bs3_tqqq_rsi_low",        label: "NO" },
  { src: "bs3_tqqq_rsi_low",      dst: "leaf_bs_tqqq_b3",         label: "YES" },
  { src: "bs3_tqqq_rsi_low",      dst: "bs4_tmf_maxdd",           label: "NO" },
  { src: "bs4_tmf_maxdd",         dst: "leaf_bs_tqqq_b4",         label: "YES" },
  { src: "bs4_tmf_maxdd",         dst: "leaf_bs_bil",             label: "NO" },
  // NMA sub-path
  { src: "nma1_qqq_maxdd",        dst: "leaf_nma_bil_1",          label: "YES" },
  { src: "nma1_qqq_maxdd",        dst: "nma2_sh_cumret",          label: "NO" },
  { src: "nma2_sh_cumret",        dst: "nma2a_spy_vs_ma40",       label: "YES" },
  { src: "nma2a_spy_vs_ma40",     dst: "leaf_nma_urty",           label: "YES" },
  { src: "nma2a_spy_vs_ma40",     dst: "nma3_ief_vs_tlt_rsi",     label: "NO" },
  { src: "nma2_sh_cumret",        dst: "nma4_bnd_vs_bil_cumret",  label: "NO" },
  { src: "nma3_ief_vs_tlt_rsi",   dst: "nma3a_bnd_vs_spy_rsi",   label: "YES" },
  { src: "nma3a_bnd_vs_spy_rsi",  dst: "leaf_nma_tqqq_3a",       label: "YES" },
  { src: "nma3a_bnd_vs_spy_rsi",  dst: "leaf_nma_bil_3a",        label: "NO" },
  { src: "nma3_ief_vs_tlt_rsi",   dst: "leaf_nma_bil_3",         label: "NO" },
  { src: "nma4_bnd_vs_bil_cumret",dst: "nma4b_spy_maxdd",        label: "YES" },
  { src: "nma4b_spy_maxdd",       dst: "nma4c_spy_rsi_high",     label: "YES" },
  { src: "nma4c_spy_rsi_high",    dst: "leaf_nma_uvxy",          label: "YES" },
  { src: "nma4c_spy_rsi_high",    dst: "nma5_vixy_rsi",          label: "NO" },
  { src: "nma5_vixy_rsi",         dst: "leaf_nma_psq",           label: "YES" },
  { src: "nma5_vixy_rsi",         dst: "leaf_nma_tqqq_5",        label: "NO" },
  { src: "nma4b_spy_maxdd",       dst: "nma6_ief_vs_tlt_rsi",    label: "NO" },
  { src: "nma4_bnd_vs_bil_cumret",dst: "nma6_ief_vs_tlt_rsi",    label: "NO" },
  { src: "nma6_ief_vs_tlt_rsi",   dst: "nma6a_bnd_vs_spy_rsi",  label: "YES" },
  { src: "nma6a_bnd_vs_spy_rsi",  dst: "leaf_nma_tqqq_6a",      label: "YES" },
  { src: "nma6a_bnd_vs_spy_rsi",  dst: "leaf_nma_bil_6a",       label: "NO" },
  { src: "nma6_ief_vs_tlt_rsi",   dst: "leaf_nma_bil_6",        label: "NO" },
  // NMB sub-path
  { src: "nmb1_qqq_maxdd",        dst: "leaf_nmb_bil_1",         label: "YES" },
  { src: "nmb1_qqq_maxdd",        dst: "nmb2_tmf_maxdd",         label: "NO" },
  { src: "nmb2_tmf_maxdd",        dst: "leaf_nmb_bil_2",         label: "YES" },
  { src: "nmb2_tmf_maxdd",        dst: "nmb3_qqq_vs_ma25",       label: "NO" },
  { src: "nmb3_qqq_vs_ma25",      dst: "leaf_nmb_tqqq_3",        label: "YES" },
  { src: "nmb3_qqq_vs_ma25",      dst: "nmb4_spy_rsi_60",        label: "NO" },
  { src: "nmb4_spy_rsi_60",       dst: "nmb4a_bnd_vs_spy_rsi",   label: "YES" },
  { src: "nmb4a_bnd_vs_spy_rsi",  dst: "leaf_nmb_tqqq_4a",       label: "YES" },
  { src: "nmb4a_bnd_vs_spy_rsi",  dst: "leaf_nmb_bil_4a",        label: "NO" },
  { src: "nmb4_spy_rsi_60",       dst: "nmb5_ief_vs_tlt_rsi",    label: "NO" },
  { src: "nmb5_ief_vs_tlt_rsi",   dst: "nmb5a_bnd_vs_spy_rsi",   label: "YES" },
  { src: "nmb5a_bnd_vs_spy_rsi",  dst: "leaf_nmb_tqqq_5a",       label: "YES" },
  { src: "nmb5a_bnd_vs_spy_rsi",  dst: "leaf_nmb_bil_5a",        label: "NO" },
  { src: "nmb5_ief_vs_tlt_rsi",   dst: "leaf_nmb_bil_5",         label: "NO" },
];

function buildBlackswanGraph(treeData) {
  const { nodes: apiNodes, active_path } = treeData;
  const activeSet = new Set(active_path);
  const nodeById = Object.fromEntries(apiNodes.map((n) => [n.id, n]));

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", ranksep: RANK_SEP + 20, nodesep: NODE_SEP + 20 });

  apiNodes.forEach((n) => {
    const isLeaf = BS_LEAF_IDS.has(n.id);
    g.setNode(n.id, { width: isLeaf ? LEAF_W : NODE_W, height: isLeaf ? LEAF_H : NODE_H });
  });

  BS_EDGES_DEF.forEach(({ src, dst }) => {
    if (nodeById[src] && nodeById[dst]) {
      g.setEdge(src, dst);
    }
  });

  dagre.layout(g);

  const rfNodes = [];
  apiNodes.forEach((n) => {
    const pos = g.node(n.id);
    if (!pos) return;
    const isLeaf = BS_LEAF_IDS.has(n.id);
    rfNodes.push({
      id: n.id,
      type: "nutsNode",
      position: {
        x: pos.x - (isLeaf ? LEAF_W : NODE_W) / 2,
        y: pos.y - (isLeaf ? LEAF_H : NODE_H) / 2,
      },
      data: { node: n, isLeaf },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });
  });

  const rfEdges = [];
  BS_EDGES_DEF.forEach(({ src, dst, label }) => {
    if (!nodeById[src] || !nodeById[dst]) return;
    const isActive = activeSet.has(src) && activeSet.has(dst);
    rfEdges.push(makeEdge(src, dst, label, isActive));
  });

  return { rfNodes, rfEdges };
}

// ─── Edge factory ─────────────────────────────────────────────────────────────
function makeEdge(src, dst, label, isActive) {
  const color = isActive ? ACTIVE_EDGE_COLOR : INACTIVE_EDGE_COLOR;
  return {
    id: `${src}__${dst}`,
    source: src,
    target: dst,
    label,
    animated: isActive,
    style: { stroke: color, strokeWidth: isActive ? 2 : 1.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color },
    labelStyle: {
      fill: isActive ? ACTIVE_EDGE_COLOR : "#6b7280",
      fontSize: 11,
      fontWeight: 600,
    },
    labelBgStyle: { fill: "#161b22", fillOpacity: 0.85 },
    type: "smoothstep",
  };
}

// ─── Active Chain extraction ────────────────────────────────────────────────────
function getActiveChain(clickedNodeId, treeData, isBlackswan) {
  const { nodes: apiNodes, active_path } = treeData;
  if (!active_path) return { conditionNodes: [], outcomeNodeId: null, outcome: null };

  const activeSet = new Set(active_path);
  const nodeById = Object.fromEntries(apiNodes.map(n => [n.id, n]));
  const clickedNode = nodeById[clickedNodeId];
  
  let targetSubpath = null;
  if (isBlackswan && clickedNode) {
    targetSubpath = clickedNode.subpath; // "bs", "nma", "nmb", or "gate"
  }
  
  const conditionNodes = [];
  let outcomeNodeId = null;
  let outcome = null;

  active_path.forEach(nid => {
    const n = nodeById[nid];
    if (!n) return;
    
    // Filter by subpath if we are in blackswan and a subpath node was clicked
    if (targetSubpath && n.subpath !== targetSubpath) return;
    
    if (n.is_leaf || n.id === "fr_default") {
      outcomeNodeId = n.id;
      outcome = n.outcome;
    } else {
      conditionNodes.push(n);
    }
  });
  
  // Gate fallback: If NO, the gate node is active but has no leaf of its own. Let's use overall result
  if (targetSubpath === "gate" && outcome == null) {
      outcome = treeData.result || treeData.final_result;
  }

  return { conditionNodes, outcomeNodeId, outcome };
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function DecisionTree({ branch, treeData, tabName, computedAt, onOpenPanel }) {
  const { rfNodes: initNodes, rfEdges: initEdges } = useMemo(() => {
    if (!treeData?.nodes) return { rfNodes: [], rfEdges: [] };
    
    let graph = { rfNodes: [], rfEdges: [] };
    if (branch === "frontrunners") graph = buildFrontrunnersGraph(treeData);
    else if (branch === "ftlt") graph = buildFtltGraph(treeData);
    else if (branch === "blackswan") graph = buildBlackswanGraph(treeData);
    
    // Inject extra panel data into nodes
    const isBs = branch === "blackswan";
    graph.rfNodes = graph.rfNodes.map(rfNode => {
      const activeChain = getActiveChain(rfNode.id, treeData, isBs);
      return {
        ...rfNode,
        data: {
          ...rfNode.data,
          activeChain,
          tabName,
          computedAt,
          onOpenPanel
        }
      };
    });
    
    return graph;
  }, [branch, treeData, tabName, computedAt, onOpenPanel]);

  const [nodes, , onNodesChange] = useNodesState(initNodes);
  const [edges, , onEdgesChange] = useEdgesState(initEdges);

  return (
    <div style={{ width: "100%", height: "100%", background: "#0d1117" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
      >
        <Background color="#21262d" gap={20} size={1} />
        <Controls
          style={{ background: "#161b22", border: "1px solid #30363d" }}
        />
        <MiniMap
          style={{ background: "#161b22", border: "1px solid #30363d" }}
          nodeColor={(n) => (n.data?.node?.active ? "#22c55e" : "#21262d")}
          maskColor="rgba(13,17,23,0.7)"
        />
      </ReactFlow>
    </div>
  );
}
