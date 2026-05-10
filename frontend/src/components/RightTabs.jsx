import React, { useState } from "react";
import { MessageSquare, Search, ScrollText, SplitSquareHorizontal, WandSparkles } from "lucide-react";

const tabs = [
  { id: "merge", label: "合并", icon: SplitSquareHorizontal },
  { id: "rag", label: "检索", icon: Search },
  { id: "chat", label: "对话", icon: MessageSquare },
  { id: "report", label: "报告", icon: ScrollText },
];

const tabCopy = {
  merge: "重复、互补与缺失判断",
  rag: "教材片段与图谱上下文",
  chat: "教师反馈与迭代建议",
  report: "最终整合报告大纲",
};

function formatPanelValue(value) {
  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

function RightTabs({ data, onRunAction, isLoading, selectedNode }) {
  const [activeTab, setActiveTab] = useState("merge");
  const active = tabs.find((tab) => tab.id === activeTab);
  const ActiveIcon = active?.icon || WandSparkles;

  return (
    <aside className="right-panel" aria-label="工作面板">
      <div className="panel-heading compact">
        <div className="panel-icon">
          <WandSparkles size={17} />
        </div>
        <div>
          <h2>Agent 面板</h2>
          <p>{tabCopy[activeTab]}</p>
        </div>
      </div>

      {selectedNode && (
        <section className="node-detail-card">
          <span className="agent-kicker">节点详情</span>
          <h3>{selectedNode.name || selectedNode.label}</h3>
          <p className="node-meta">
            {[selectedNode.category, selectedNode.chapter, selectedNode.page ? `P.${selectedNode.page}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {selectedNode.definition && <p>{selectedNode.definition}</p>}
          {selectedNode.source_textbook && <footer>来源：{selectedNode.source_textbook}</footer>}
        </section>
      )}

      <div className="tab-list" role="tablist">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={activeTab === tab.id ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={15} />
              {tab.label}
            </button>
          );
        })}
      </div>

      <section className="agent-card">
        <header>
          <span className="agent-kicker">
            <ActiveIcon size={15} />
            {active?.label}
          </span>
          <span className={isLoading ? "run-state loading" : "run-state"}>{isLoading ? "运行中" : "待运行"}</span>
        </header>
        <pre>{formatPanelValue(data[activeTab])}</pre>
      </section>

      <button
        className="button dark-button run-button"
        type="button"
        onClick={() => onRunAction(activeTab)}
        disabled={isLoading}
      >
        <WandSparkles size={16} />
        运行当前 Agent
      </button>
    </aside>
  );
}

export default RightTabs;
