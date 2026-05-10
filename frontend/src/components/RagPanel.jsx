import React, { useState, useEffect } from "react";
import { Search, ChevronDown, ChevronUp, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { buildRagIndex, ragQueryV2, getRagStatus, listTextbooks } from "../api";

function RagPanel() {
  const [ragStatus, setRagStatus] = useState(null);
  const [textbooks, setTextbooks] = useState([]);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [expandedSources, setExpandedSources] = useState(new Set());
  const [isBuilding, setIsBuilding] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadStatus();
    loadTextbooks();
  }, []);

  async function loadStatus() {
    try {
      const status = await getRagStatus();
      setRagStatus(status);
    } catch (err) {
      console.error("Failed to load RAG status:", err);
    }
  }

  async function loadTextbooks() {
    try {
      const data = await listTextbooks();
      setTextbooks(data.textbooks || []);
    } catch (err) {
      console.error("Failed to load textbooks:", err);
    }
  }

  async function handleBuildIndex() {
    setIsBuilding(true);
    setError("");
    try {
      const parsedTextbooks = textbooks
        .filter((t) => t.parse_status === "parsed")
        .map((t) => t.textbook_id);

      if (parsedTextbooks.length === 0) {
        setError("没有已解析的教材，请先上传并解析教材");
        return;
      }

      const result = await buildRagIndex(parsedTextbooks);
      setRagStatus(result);
      if (result.warning) {
        setError(`索引已构建（${result.warning}）`);
      }
    } catch (err) {
      setError(`构建失败: ${err.message}`);
    } finally {
      setIsBuilding(false);
    }
  }

  async function handleQuery() {
    if (!query.trim()) return;

    setIsQuerying(true);
    setError("");
    try {
      const result = await ragQueryV2(query, 5);
      setAnswer(result.answer || "");
      setSources(result.sources || []);
      setExpandedSources(new Set());
    } catch (err) {
      setError(`查询失败: ${err.message}`);
      setAnswer("");
      setSources([]);
    } finally {
      setIsQuerying(false);
    }
  }

  function toggleSource(index) {
    const newExpanded = new Set(expandedSources);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSources(newExpanded);
  }

  const isIndexed = ragStatus?.status === "indexed" || ragStatus?.status === "indexed_without_embeddings";

  return (
    <div className="rag-panel">
      {/* 索引状态区 */}
      <section className="rag-status-card">
        <div className="rag-status-header">
          <span className="agent-kicker">索引状态</span>
          {isIndexed ? (
            <CheckCircle size={16} className="status-icon success" />
          ) : (
            <AlertCircle size={16} className="status-icon warning" />
          )}
        </div>
        {ragStatus ? (
          <div className="rag-status-info">
            <p>
              <strong>状态:</strong> {ragStatus.status === "indexed" ? "已索引" : ragStatus.status === "indexed_without_embeddings" ? "已索引（关键词模式）" : "未索引"}
            </p>
            {ragStatus.total_chunks > 0 && (
              <>
                <p><strong>文本块数:</strong> {ragStatus.total_chunks}</p>
                <p><strong>教材:</strong> {ragStatus.textbook_ids?.join(", ") || "无"}</p>
              </>
            )}
          </div>
        ) : (
          <p>加载中...</p>
        )}
        <button
          className="button dark-button"
          onClick={handleBuildIndex}
          disabled={isBuilding}
          style={{ marginTop: "0.5rem", width: "100%" }}
        >
          {isBuilding ? (
            <>
              <Loader2 size={16} className="spinner" />
              构建中...
            </>
          ) : (
            <>
              <Search size={16} />
              {isIndexed ? "重建索引" : "构建索引"}
            </>
          )}
        </button>
      </section>

      {/* 问答区 */}
      <section className="rag-query-card">
        <span className="agent-kicker">问答检索</span>
        <div className="rag-input-group">
          <input
            type="text"
            className="rag-input"
            placeholder="输入问题，如：动作电位的产生机制是什么？"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            disabled={!isIndexed || isQuerying}
          />
          <button
            className="button dark-button"
            onClick={handleQuery}
            disabled={!isIndexed || isQuerying || !query.trim()}
          >
            {isQuerying ? (
              <>
                <Loader2 size={16} className="spinner" />
                查询中
              </>
            ) : (
              <>
                <Search size={16} />
                查询
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="rag-error">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {answer && (
          <div className="rag-answer">
            <strong>回答：</strong>
            <p>{answer}</p>
          </div>
        )}
      </section>

      {/* 引用源列表 */}
      {sources.length > 0 && (
        <section className="rag-sources-card">
          <span className="agent-kicker">引用来源 ({sources.length})</span>
          <div className="rag-sources-list">
            {sources.map((source, index) => (
              <div key={index} className="rag-source-item">
                <button
                  className="rag-source-header"
                  onClick={() => toggleSource(index)}
                >
                  <div className="rag-source-title">
                    <strong>《{source.textbook_title}》</strong>
                    <span className="rag-source-meta">
                      {source.chapter} · P.{source.page} · 相似度: {(source.score * 100).toFixed(1)}%
                    </span>
                  </div>
                  {expandedSources.has(index) ? (
                    <ChevronUp size={16} />
                  ) : (
                    <ChevronDown size={16} />
                  )}
                </button>
                {expandedSources.has(index) && (
                  <div className="rag-source-content">
                    <pre>{source.content}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default RagPanel;
