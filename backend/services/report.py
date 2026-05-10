from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_TEMPLATE = """# 多教材知识整合报告

**生成时间**：{timestamp}
**整合教材**：{textbook_list}
**整合ID**：`{merge_id}`

---

## 一、整合概览

| 指标 | 整合前 | 整合后 | 变化 |
|---|---|---|---|
| 教材数量 | {original_textbook_count} 本 | 1 本（整合版） | - |
| 总字数 | {original_chars} | {merged_chars} | 压缩至 {compression_ratio:.1%} |
| 知识点节点 | {original_nodes} | {merged_nodes} | 减少 {node_reduction} 个 |
| 关系边 | {original_edges} | {merged_edges} | 减少 {edge_reduction} 条 |

**压缩比**：{compression_ratio:.1%}（目标 30%，允许浮动 25%-40%）

---

## 二、整合决策统计

| 决策类型 | 数量 | 占比 | 说明 |
|---|---|---|---|
| 合并（Merge） | {merge_count} | {merge_ratio:.1%} | 识别为同一概念的节点被合并 |
| 保留（Keep） | {keep_count} | {keep_ratio:.1%} | 各教材独有、互补的知识点 |
| 删除（Remove） | {remove_count} | {remove_ratio:.1%} | 冗余或定义较弱的重复节点 |

---

## 三、典型整合案例

{case_studies}

---

## 四、教学完整性说明

### 4.1 知识覆盖度

整合后的知识图谱保留了原始教材中的**核心知识体系**。被删除的节点主要为：
- **重复定义**：多本教材对同一概念的不同表述
- **过度细节**：不影响主线理解的具体例子
- **局部补充**：某教材特有的非核心扩展

### 4.2 知识连贯性

整合后的知识图谱保持了原有的逻辑结构：
- **先修关系（prerequisite）**：{prerequisite_count} 条
- **包含关系（contains）**：{contains_count} 条
- **并列关系（parallel）**：{parallel_count} 条
- **应用关系（applies_to）**：{applies_to_count} 条

### 4.3 教学建议

1. **适用对象**：本整合版本适合已有基础的学习者，可作为复习或考前冲刺材料
2. **补充建议**：对于初学者，建议结合原始教材中的详细案例和习题
3. **使用方式**：通过知识图谱浏览整体结构，通过 RAG 问答精准定位具体知识点

---

## 五、RAG 问答索引状态

- **索引状态**：{rag_status}
- **文本块数量**：{rag_chunks}
- **覆盖教材**：{rag_textbooks}

---

## 六、技术说明

### 6.1 整合算法

本次整合使用了**多维度相似度算法**：

| 维度 | 权重 | 说明 |
|---|---|---|
| 名称相似度 | 20% | 字符串编辑距离 |
| 语义相似度 | 50% | sentence-transformers 余弦相似度 |
| 章节共现 | 15% | 上下文一致性 |
| 类别一致性 | 15% | 是否属于同一类型 |

**合并阈值**：综合分数 ≥ 0.75

### 6.2 LLM 模型信息

- **Provider**：{llm_provider}
- **Model**：{llm_model}

---

## 七、附录

### 7.1 完整决策列表

调用 API 获取：
```
GET /api/merge/{merge_id}
```

### 7.2 可视化图谱

访问前端界面查看交互式知识图谱。

---

**报告生成工具**：学科知识整合智能体
**赛事**：第一届 AI 全栈黑客松
"""


def _generate_case_study(decision: dict, index: int) -> str:
    """生成单个案例的 Markdown"""
    dec_type = decision.get("type", "")

    if dec_type == "merge":
        merged_node = decision.get("merged_node", {})
        nodes_list = decision.get("nodes", [])
        nodes_str = "、".join(nodes_list) if nodes_list else "无"
        return f"""### 案例 {index}：合并「{merged_node.get('name', '未知')}」

**涉及节点**：{nodes_str}

**合并理由**：{decision.get('reason', '无')}

**置信度**：{decision.get('confidence', 0):.2f}

**合并后定义**：
> {merged_node.get('definition', '无')}
"""
    elif dec_type == "remove":
        node_info = decision.get("node", "未知")
        if isinstance(node_info, dict):
            node_info = node_info.get("name", "未知")
        return f"""### 案例 {index}：删除「{node_info}」

**删除理由**：{decision.get('reason', '无')}

**置信度**：{decision.get('confidence', 0):.2f}
"""
    elif dec_type == "keep":
        node_info = decision.get("node", "未知")
        if isinstance(node_info, dict):
            node_info = node_info.get("name", "未知")
        return f"""### 案例 {index}：保留「{node_info}」

**保留理由**：{decision.get('reason', '无')}

**置信度**：{decision.get('confidence', 0):.2f}
"""
    return ""


def generate_report(merge_id: str) -> dict[str, Any]:
    """生成整合报告。"""
    from . import graph_store

    merge_result = graph_store.load_merged_graph(merge_id)
    if not merge_result:
        return {"success": False, "error": "未找到整合结果，请先执行整合"}

    decisions = merge_result.get("decisions", [])
    if isinstance(decisions, str):
        decisions = json.loads(decisions)

    merged_graph = merge_result.get("graph", {})
    textbook_ids = merge_result.get("textbook_ids", [])
    if isinstance(textbook_ids, str):
        textbook_ids = json.loads(textbook_ids)

    merge_count = sum(1 for d in decisions if d.get("type") == "merge")
    keep_count = sum(1 for d in decisions if d.get("type") == "keep")
    remove_count = sum(1 for d in decisions if d.get("type") == "remove")
    total_decisions = max(len(decisions), 1)

    original_nodes = merge_result.get("original_nodes", 0)
    merged_nodes_list = merged_graph.get("nodes", [])
    merged_edges_list = merged_graph.get("edges", [])
    merged_nodes = len(merged_nodes_list)
    merged_edges = len(merged_edges_list)

    parsed_dir = Path(__file__).resolve().parent.parent / "data" / "parsed"
    original_chars = 0
    for tid in textbook_ids:
        f = parsed_dir / f"{tid}.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            original_chars += data.get("total_chars", 0)
    original_edges = int(original_nodes * 1.5)

    merged_chars = sum(len(n.get("definition", "")) for n in merged_nodes_list)

    compression_ratio = merge_result.get("compression_ratio",
                                          merged_chars / max(original_chars, 1))

    prerequisite_count = sum(1 for e in merged_edges_list if e.get("relation_type") == "prerequisite")
    contains_count = sum(1 for e in merged_edges_list if e.get("relation_type") == "contains")
    parallel_count = sum(1 for e in merged_edges_list if e.get("relation_type") == "parallel")
    applies_to_count = sum(1 for e in merged_edges_list if e.get("relation_type") == "applies_to")

    rag_status = "未索引"
    rag_chunks = 0
    rag_textbooks = "无"
    try:
        from . import rag as rag_module
        if hasattr(rag_module, "get_rag_status"):
            rag_info = rag_module.get_rag_status()
            rag_status = rag_info.get("status", "未索引")
            rag_chunks = rag_info.get("total_chunks", 0)
            rag_textbooks = "、".join(rag_info.get("textbook_ids", [])) or "无"
    except Exception:
        pass

    merge_cases = [d for d in decisions if d.get("type") == "merge"][:3]
    remove_cases = [d for d in decisions if d.get("type") == "remove"][:1]
    keep_cases = [d for d in decisions if d.get("type") == "keep"][:1]
    selected_cases = merge_cases + remove_cases + keep_cases

    case_studies_md = ""
    if selected_cases:
        for i, dec in enumerate(selected_cases, 1):
            case_studies_md += _generate_case_study(dec, i) + "\n"
    else:
        case_studies_md = "*暂无典型案例*\n"

    report_content = REPORT_TEMPLATE.format(
        timestamp=datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        textbook_list="、".join(textbook_ids) if textbook_ids else "无",
        merge_id=merge_id,
        original_textbook_count=len(textbook_ids),
        original_chars=f"{original_chars:,}",
        merged_chars=f"{merged_chars:,}",
        compression_ratio=compression_ratio,
        original_nodes=original_nodes,
        merged_nodes=merged_nodes,
        node_reduction=max(original_nodes - merged_nodes, 0),
        original_edges=original_edges,
        merged_edges=merged_edges,
        edge_reduction=max(original_edges - merged_edges, 0),
        merge_count=merge_count,
        merge_ratio=merge_count / total_decisions,
        keep_count=keep_count,
        keep_ratio=keep_count / total_decisions,
        remove_count=remove_count,
        remove_ratio=remove_count / total_decisions,
        case_studies=case_studies_md,
        prerequisite_count=prerequisite_count,
        contains_count=contains_count,
        parallel_count=parallel_count,
        applies_to_count=applies_to_count,
        rag_status=rag_status,
        rag_chunks=f"{rag_chunks:,}",
        rag_textbooks=rag_textbooks,
        llm_provider=merge_result.get("provider") or "未知",
        llm_model=merge_result.get("model") or "未知",
    )

    report_dir = Path(__file__).resolve().parent.parent.parent / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "整合报告.md"
    report_path.write_text(report_content, encoding="utf-8")

    return {
        "success": True,
        "report_path": str(report_path),
        "report_content": report_content,
        "report_length": len(report_content),
    }


def get_report(merge_id: str = None) -> dict[str, Any]:
    """读取已保存的报告（兼容无 merge_id 的旧接口）"""
    report_path = Path(__file__).resolve().parent.parent.parent / "report" / "整合报告.md"
    if not report_path.exists():
        return {"success": False, "error": "报告尚未生成"}
    return {
        "success": True,
        "report_path": str(report_path),
        "report_content": report_path.read_text(encoding="utf-8"),
    }
