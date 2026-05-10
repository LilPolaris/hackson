import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

const CATEGORY_COLORS = {
  核心概念: "#3b82f6",
  子概念: "#10b981",
  性质: "#f59e0b",
  应用: "#ef4444",
};

const RELATION_COLORS = {
  prerequisite: "#6366f1",
  parallel: "#9ca3af",
  contains: "#14b8a6",
  applies_to: "#f97316",
};

function truncateLabel(label) {
  if (!label) {
    return "";
  }
  return label.length > 14 ? `${label.slice(0, 13)}…` : label;
}

function KnowledgeGraph({ graph, onNodeClick }) {
  const fgRef = useRef(null);
  const viewportRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 720, height: 420 });

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) {
      return undefined;
    }

    function updateDimensions() {
      const rect = element.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setDimensions({ width: rect.width, height: rect.height });
      }
    }

    updateDimensions();
    const observer = new ResizeObserver(updateDimensions);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const data = useMemo(() => {
    const nodes = (graph?.nodes || []).map((node) => ({
      id: node.id,
      name: node.name || node.label || node.id,
      category: node.category || node.type || "核心概念",
      raw: node,
    }));
    const links = (graph?.edges || []).map((edge) => ({
      source: edge.source,
      target: edge.target,
      relation_type: edge.relation_type || edge.relation || "parallel",
      description: edge.description || "",
    }));
    return { nodes, links };
  }, [graph]);

  const handleNodeClick = useCallback(
    (node) => {
      onNodeClick?.(node.raw);
      if (Number.isFinite(node.x) && Number.isFinite(node.y)) {
        fgRef.current?.centerAt(node.x, node.y, 500);
        fgRef.current?.zoom(2.4, 500);
      }
    },
    [onNodeClick],
  );

  const paintNode = useCallback((node, ctx, globalScale) => {
    const color = CATEGORY_COLORS[node.category] || "#64748b";
    const radius = 7;
    const label = truncateLabel(node.name);
    const fontSize = Math.max(10, 13 / globalScale);

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI, false);
    ctx.fillStyle = "rgba(255, 255, 255, 0.82)";
    ctx.fill();

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.fill();

    ctx.font = `600 ${fontSize}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "#1f2937";
    ctx.fillText(label, node.x, node.y + radius + 5);
  }, []);

  const paintPointerArea = useCallback((node, color, ctx) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, 18, 0, 2 * Math.PI, false);
    ctx.fill();
  }, []);

  if (!data.nodes.length) {
    return (
      <div className="graph-canvas graph-empty">
        <p>尚未构建知识图谱。请点击右上角「构建图谱」。</p>
      </div>
    );
  }

  return (
    <div className="graph-canvas">
      <div className="graph-toolbar">
        <span>
          {data.nodes.length} 节点 · {data.links.length} 关系
        </span>
        <div className="legend">
          {Object.entries(CATEGORY_COLORS).map(([name, color]) => (
            <span key={name}>
              <i className="legend-dot" style={{ background: color }} />
              {name}
            </span>
          ))}
        </div>
      </div>

      <div className="graph-viewport" ref={viewportRef}>
        <ForceGraph2D
          ref={fgRef}
          graphData={data}
          width={dimensions.width}
          height={dimensions.height}
          nodeRelSize={6}
          nodeCanvasObject={paintNode}
          nodeCanvasObjectMode={() => "replace"}
          nodePointerAreaPaint={paintPointerArea}
          linkColor={(link) => RELATION_COLORS[link.relation_type] || "#cbd5e1"}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkLabel={(link) => `${link.relation_type}: ${link.description || ""}`}
          onNodeClick={handleNodeClick}
          cooldownTicks={80}
        />
      </div>
    </div>
  );
}

export default KnowledgeGraph;
