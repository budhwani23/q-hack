// src/NodeGraph.jsx
import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  NODES,
  EDGES,
  NODE_POSITIONS,
  NODE_LABELS,
  stateLabel,
  stateColor,
  argmax,
} from "./dbn";

// Chunky node card with thick black border — Gen Z pop aesthetic
function BNNode({ data }) {
  const {
    label,
    topState,
    topProb,
    topDelta,
    k,
    color,
    isObserved,
    isOutcome,
  } = data;

  const pctText = `${(topProb * 100).toFixed(0)}%`;
  const deltaText =
    Math.abs(topDelta) >= 0.01
      ? (topDelta > 0 ? "↑" : "↓") + (Math.abs(topDelta) * 100).toFixed(0) + "%"
      : null;

  return (
    <div className="relative group">
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-ink-900 !border-ink-950 !w-2 !h-2"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-ink-900 !border-ink-950 !w-2 !h-2"
      />
      <div
        className={`
          relative flex flex-col items-center justify-center
          w-[130px] h-[92px] rounded-2xl
          bg-cream-50
          border-[2.5px] border-ink-950
          transition-all duration-500
          ${isObserved
            ? "shadow-[4px_4px_0_0_#FF5A3C]"
            : "shadow-[3px_3px_0_0_#1a1a1a]"}
        `}
      >
        {/* Color band at the top of the card showing dominant state */}
        <div
          className="absolute top-0 left-0 right-0 h-1.5 rounded-t-[14px] transition-colors duration-500"
          style={{ backgroundColor: color }}
        />
        <div className="text-[10px] uppercase tracking-[0.14em] text-ink-700 font-semibold mt-1">
          {label}
        </div>
        <div
          className="font-display text-xl leading-none mt-1 font-semibold"
          style={{ color: isOutcome ? color : "#1a1a1a" }}
        >
          {stateLabel(k, topState)}
        </div>
        <div className="font-mono text-[10px] text-ink-600 mt-1 flex gap-1.5 items-center">
          <span>{pctText}</span>
          {deltaText && (
            <span
              className="font-semibold"
              style={{ color: topDelta > 0 ? "#2F8559" : "#C92E3E" }}
            >
              {deltaText}
            </span>
          )}
        </div>
        {isObserved && (
          <div className="absolute -top-2 -right-2 w-4 h-4 rounded-full bg-coral-500 border-2 border-ink-950 animate-pulseRing" />
        )}
      </div>
    </div>
  );
}

const nodeTypes = { bn: BNNode };

export default function NodeGraph({ posteriors, evidence, kPerNode }) {
  const slice = useMemo(() => {
    if (!posteriors) return {};
    if (posteriors.slice_0) return posteriors.slice_0;
    return posteriors;
  }, [posteriors]);

  const nodes = useMemo(() => {
    return NODES.map((name) => {
      const k = kPerNode?.[name] ?? 3;
      const dist = slice[name] ?? {};
      const { state, prob, delta } = argmax(dist);
      const isObserved = evidence && name in evidence;
      const isOutcome = name === "stress" || name === "mood";

      const effectiveState = isObserved ? evidence[name] : state;
      const effectiveProb = isObserved ? 1.0 : prob ?? 0;
      const color = stateColor(k, effectiveState ?? 0, isOutcome);

      return {
        id: name,
        type: "bn",
        position: NODE_POSITIONS[name],
        data: {
          label: NODE_LABELS[name],
          topState: effectiveState ?? 0,
          topProb: effectiveProb,
          topDelta: isObserved ? 0 : delta,
          k,
          color,
          isObserved,
          isOutcome,
        },
        draggable: false,
      };
    });
  }, [slice, evidence, kPerNode]);

  const edges = useMemo(() => {
    return EDGES.map(([src, dst], i) => {
      const srcObserved = evidence && src in evidence;
      return {
        id: `e-${i}`,
        source: src,
        target: dst,
        type: "smoothstep",
        animated: srcObserved,
        style: {
          stroke: srcObserved ? "#FF5A3C" : "#1a1a1a",
          strokeWidth: srcObserved ? 2.5 : 1.5,
          opacity: srcObserved ? 1 : 0.35,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: srcObserved ? "#FF5A3C" : "#1a1a1a",
          width: 16,
          height: 16,
        },
      };
    });
  }, [evidence]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.28 }}
      proOptions={{ hideAttribution: true }}
      panOnDrag
      zoomOnScroll={false}
      zoomOnPinch
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
    >
      <Background color="#d9d3c5" gap={22} size={1.5} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
