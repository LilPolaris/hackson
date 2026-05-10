# 学科知识整合智能体

第一届AI全栈黑客松参赛项目 - 多教材知识整合与RAG问答系统

## 项目简介

本项目是一个基于AI的学科知识整合智能体，能够：
- 自动加载并解析多本教材（PDF/Markdown/TXT/Word）
- 为每本教材构建可视化知识图谱
- 跨教材识别知识点的重叠、互补与缺失
- 将多本教材整合压缩到不超过原始体量30%的精华版本
- 基于整合后的知识库进行RAG精准问答（带引用来源）
- 支持教师通过多轮对话迭代优化整合方案

## 技术栈

**后端**：
- FastAPI - Web框架
- SQLite - 数据持久化
- PyMuPDF - PDF解析
- sentence-transformers - 文本嵌入（多维度相似度计算）
- FAISS - 向量检索（RAG问答）
- OpenAI SDK - 统一 LLM 调用接口（兼容 OpenAI/通义千问/DeepSeek）

**前端**：
- React 19 + Vite
- react-force-graph-2d - 知识图谱可视化
- Lucide React - 图标库

## 目录结构

```text
backend/
  main.py                 # FastAPI主入口
  services/
    parser.py            # 教材解析（✅ 已完成）
    graph_builder.py     # 知识图谱构建（✅ 已完成）
    graph_store.py       # SQLite 数据持久化（✅ 已完成）
    merger.py            # 跨教材整合（✅ 已完成）
    llm/                 # LLM Provider 抽象层（✅ 已完成）
      base.py            # 统一接口定义
      providers.py       # OpenAI/通义/DeepSeek 实现
      registry.py        # Provider 注册与切换
    rag.py               # RAG检索问答（🚧 待实现）
    chat.py              # 多轮对话（🚧 待实现）
    report.py            # 整合报告生成（🚧 待实现）
  data/
    uploads/             # 上传的教材文件
    parsed/              # 解析后的 JSON
    graph.db             # SQLite 数据库
    llm_config.json      # LLM Provider 配置
frontend/
  src/
    App.jsx              # 主应用
    api.js               # API 调用封装
    components/
      TextbookManager.jsx    # 左侧教材管理
      KnowledgeGraph.jsx     # 中间图谱可视化（react-force-graph-2d）
      RightTabs.jsx          # 右侧功能面板
docs/
  需求分析.md
  系统设计.md
  Agent 架构说明.md
report/
  整合报告.md
TASK_跨教材整合.md          # 跨教材整合任务文档
TASK_第二阶段_整合与RAG.md   # 完整第二阶段任务文档
```

## 环境依赖

- **Python**: 3.10+
- **Node.js**: 18+
- **npm**: 9+

## 安装步骤

### 1. 克隆仓库

```bash
git clone <your-repo-url>
cd ai-fullstack-hackathon
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写你的API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写以下配置：
- `OPENAI_API_KEY` - OpenAI API密钥
- 或 `DASHSCOPE_API_KEY` - 通义千问API密钥
- 或 `DEEPSEEK_API_KEY` - DeepSeek API密钥

### 3. 安装后端依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv

# Windows激活
.\.venv\Scripts\Activate.ps1
# Linux/Mac激活
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 安装前端依赖

```bash
npm install
```

## 启动命令

### 方式一：同时启动前后端（推荐）

```bash
npm run dev
```

### 方式二：分别启动

**启动后端**：
```bash
npm run dev:backend
# 或
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：http://127.0.0.1:8000  
API文档：http://127.0.0.1:8000/docs

**启动前端**：
```bash
npm run dev:frontend
```

前端地址：http://127.0.0.1:5173

## 使用说明

### 基础流程

1. **配置 LLM Provider**
   - 启动后端后，访问前端界面
   - 点击右上角”LLM 设置”
   - 选择 Provider（OpenAI / 通义千问 / DeepSeek）
   - 填入 API Key 并保存

2. **上传教材**
   - 在左侧教材管理区上传 PDF/Markdown/TXT/Word 文件
   - 支持多本教材同时上传

3. **解析教材**
   - 点击”解析”按钮，系统自动识别章节结构
   - 解析结果保存到 `backend/data/parsed/{textbook_id}.json`

4. **构建图谱**
   - 点击”构建图谱”，调用 LLM 提取知识点
   - 生成的图谱保存到 SQLite（`backend/data/graph.db`）
   - 中间区域显示力导向布局的知识图谱
   - 点击节点查看详情（名称、定义、章节、页码、来源）

5. **整合教材**
   - 选择多本教材，点击”整合”
   - 系统使用多维度相似度算法识别重复/互补知识点
   - 调用 LLM 生成合并理由
   - 输出压缩比约 30% 的整合图谱

6. **RAG 问答**（🚧 待实现）
   - 在右侧问答面板输入问题
   - 获得带引用来源的回答

7. **多轮对话**（🚧 待实现）
   - 通过对话修改整合决策
   - 例如：”请保留免疫应答”、”把抗原和免疫原分开”

8. **生成报告**（🚧 待实现）
   - 导出完整的整合报告（Markdown 格式）

### API 端点

访问 http://127.0.0.1:8000/docs 查看完整 API 文档。

**核心端点**：
- `POST /api/textbooks/upload` - 上传教材
- `POST /api/textbooks/{textbook_id}/parse` - 解析教材
- `POST /api/graph/build/{textbook_id}` - 构建单书图谱
- `GET /api/graph/{textbook_id}` - 读取图谱
- `POST /api/merge/run` - 跨教材整合
- `GET /api/merge/{merge_id}` - 读取整合结果
- `GET /api/llm/providers` - 列出 LLM Providers
- `POST /api/llm/providers` - 切换 Provider

## 开发状态

### 已完成功能 ✅

**第一阶段：基础设施**
- [x] 项目骨架搭建
- [x] 前端文件上传组件
- [x] 后端文件上传接口
- [x] PDF/Markdown/TXT/Word 解析
- [x] 章节结构识别

**第二阶段：单书图谱**
- [x] LLM Provider 抽象层（支持 OpenAI/通义千问/DeepSeek 切换）
- [x] 知识点提取（调用 LLM，输出结构化 JSON）
- [x] 单书知识图谱构建
- [x] SQLite 数据持久化（graphs / nodes / edges 表）
- [x] 知识图谱可视化（react-force-graph-2d 力导向布局）
- [x] 节点点击查看详情

**第三阶段：跨教材整合**
- [x] 多维度相似度算法（名称/语义/章节/类别）
- [x] LLM 生成合并理由与置信度
- [x] 整合决策生成（merge / keep / remove）
- [x] 压缩比控制（目标 30%，范围 25%-40%）
- [x] SQLite 持久化（merged_graphs / merged_nodes / merged_edges 表）
- [x] Mock Fallback 机制（LLM 失败时降级）

### 待实现功能 🚧

**第四阶段：RAG 问答**
- [ ] 文本分块（chunk_size=600, overlap=80）
- [ ] FAISS 向量索引构建
- [ ] 带引用来源的回答
- [ ] 本地 embedding 模型 / 云端 API

**第五阶段：教师对话**
- [ ] 意图识别（保留/合并/拆分/解释）
- [ ] 修改决策并更新图谱
- [ ] 对话历史保存

**第六阶段：整合报告**
- [ ] 生成完整 Markdown 报告
- [ ] 包含概览、决策统计、典型案例、完整性说明
- [ ] 前端预览与下载

### 代码统计

```
后端：~2,800 行 Python
  - graph_builder.py: 307 行（知识点抽取）
  - graph_store.py: 318 行（SQLite 持久化）
  - merger.py: 699 行（跨教材整合）
  - parser.py: 298 行（教材解析）
  - llm/: 806 行（LLM Provider 抽象层）

前端：~1,400 行 JavaScript/JSX
  - App.jsx: 883 行（主应用）
  - KnowledgeGraph.jsx: 152 行（图谱可视化）
  - TextbookManager.jsx: 162 行（教材管理）
  - RightTabs.jsx: 98 行（功能面板）
```

## 部署

### 本地部署

按照上述”启动命令”运行即可。

### 线上部署

推荐使用魔搭创空间（ModelScope）或其他支持Python+Node.js的平台。

## 文档

- [需求分析](docs/需求分析.md)
- [系统设计](docs/系统设计.md)
- [Agent架构说明](docs/Agent架构说明.md)
- [整合报告](report/整合报告.md)

## 许可证

MIT License

## 联系方式

如有问题，请提交Issue或联系开发者。
