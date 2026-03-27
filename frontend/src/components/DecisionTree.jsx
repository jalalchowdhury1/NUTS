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

// ─── Component ────────────────────────────────────────────────────────────────
export default function DecisionTree({ branch, treeData }) {
  const { rfNodes: initNodes, rfEdges: initEdges } = useMemo(() => {
    if (!treeData?.nodes) return { rfNodes: [], rfEdges: [] };
    if (branch === "frontrunners") return buildFrontrunnersGraph(treeData);
    if (branch === "ftlt") return buildFtltGraph(treeData);
    return { rfNodes: [], rfEdges: [] };
  }, [branch, treeData]);

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
