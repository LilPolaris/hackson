import React, { useRef } from "react";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  FileText,
  FileUp,
  Layers,
  Play,
  Trash2,
  UploadCloud,
} from "lucide-react";

const statusLabels = {
  uploaded: "已上传",
  parsing: "解析中",
  parsed: "已解析",
  failed: "解析失败",
};

function formatBytes(sizeBytes) {
  if (!Number.isFinite(sizeBytes)) {
    return "--";
  }

  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }

  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }

  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`;
}

function TextbookManager({
  textbooks,
  activeTextbookId,
  onSelect,
  onUpload,
  onParse,
  onDelete,
  onRunAction,
  isLoading,
  notice,
}) {
  const fileInputRef = useRef(null);

  function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file);
    }
    event.target.value = "";
  }

  return (
    <aside className="sidebar" aria-label="教材管理">
      <div className="panel-heading">
        <div className="panel-icon">
          <BookOpen size={17} />
        </div>
        <div>
          <h2>教材管理</h2>
          <p>{textbooks.length} 本教材源</p>
        </div>
      </div>

      <input
        ref={fileInputRef}
        className="hidden-file-input"
        type="file"
        accept=".pdf,.md,.txt,.docx,application/pdf,text/markdown,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleFileChange}
      />
      <button
        className="button dark-button upload-button"
        type="button"
        disabled={isLoading}
        onClick={() => fileInputRef.current?.click()}
      >
        <FileUp size={16} />
        上传教材
      </button>

      <div className="drop-card">
        <UploadCloud size={18} />
        <span>支持 PDF / Markdown / TXT / Word</span>
      </div>

      {notice && (
        <div className="notice-card" role="alert">
          <AlertCircle size={16} />
          <span>{notice}</span>
        </div>
      )}

      <div className="textbook-list">
        {textbooks.length === 0 && (
          <div className="empty-card">
            <FileText size={18} />
            <span>还没有上传教材</span>
            <small>先上传教材，再点击解析。</small>
          </div>
        )}

        {textbooks.map((item) => {
          const isActive = item.textbook_id === activeTextbookId;
          const isParsed = item.parse_status === "parsed";
          const isParsing = item.parse_status === "parsing";

          return (
            <article className={isActive ? "textbook-item active" : "textbook-item"} key={item.textbook_id}>
              <button className="textbook-select" type="button" onClick={() => onSelect(item.textbook_id)}>
                <span className="textbook-row">
                  <strong title={item.filename}>{item.filename}</strong>
                  {isParsed && <CheckCircle2 size={16} />}
                </span>
                <small>{statusLabels[item.parse_status] || item.parse_status}</small>
              </button>
              <span className="textbook-meta">
                <span>{item.format.toUpperCase()}</span>
                <span>{formatBytes(item.size_bytes)}</span>
              </span>
              <div className="textbook-actions">
                <button
                  className="button cream-button parse-file-button"
                  type="button"
                  onClick={() => onParse(item.textbook_id)}
                  disabled={isLoading || isParsing}
                >
                  <Play size={14} />
                  {isParsed ? "重新解析" : "解析"}
                </button>
                <button
                  className="icon-button delete-textbook-button"
                  type="button"
                  aria-label={`删除 ${item.filename}`}
                  title={`删除 ${item.filename}`}
                  onClick={() => onDelete(item)}
                  disabled={isLoading}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <div className="action-stack">
        <button
          className="button ghost-button"
          type="button"
          onClick={() => onRunAction("parse")}
          disabled={isLoading || !activeTextbookId}
        >
          <Play size={15} />
          解析当前
        </button>
        <button
          className="button cream-button"
          type="button"
          onClick={() => onRunAction("merge")}
          disabled={isLoading || textbooks.length === 0}
        >
          <Layers size={15} />
          合并
        </button>
      </div>
    </aside>
  );
}

export default TextbookManager;
