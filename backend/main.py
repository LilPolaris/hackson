from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .services import chat, graph_builder, graph_store, merger, parser, rag, report
from .services.llm import check_provider_config, fetch_provider_models, provider_registry, set_active_provider

# 加载环境变量
load_dotenv()


APP_NAME = "AI Fullstack Hackathon API"
DATA_DIR = Path(__file__).resolve().parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PARSED_DIR = DATA_DIR / "parsed"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
graph_store.init_db()


app = FastAPI(title=APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextbookRequest(BaseModel):
    textbook_id: str = Field(default="demo-textbook")
    filename: str | None = None


class MergeRequest(BaseModel):
    textbook_ids: list[str] = Field(default_factory=lambda: ["math-a", "math-b"])


class RagRequest(BaseModel):
    query: str = Field(default="请检索相关知识点")
    top_k: int = Field(default=5, ge=1, le=20)


class ChatRequest(BaseModel):
    message: str = Field(default="请评价当前整合方案")
    history: list[dict[str, Any]] = Field(default_factory=list)


class ReportRequest(BaseModel):
    topic: str = Field(default="多教材知识整合报告")
    textbook_ids: list[str] = Field(default_factory=list)


class LLMConfigRequest(BaseModel):
    active: str
    config: dict[str, Any] | None = None


@app.get("/")
def root() -> dict[str, str]:
    return {"name": APP_NAME, "status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# 新增：教材列表接口
@app.get("/api/textbooks")
def list_textbooks() -> dict[str, Any]:
    """获取所有已上传的教材列表"""
    textbooks = []
    if UPLOAD_DIR.exists():
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                parsed_file = DATA_DIR / "parsed" / f"{file_path.stem}.json"
                textbooks.append({
                    "textbook_id": file_path.stem,
                    "filename": file_path.name,
                    "format": file_path.suffix.lstrip('.'),
                    "size_bytes": file_path.stat().st_size,
                    "parse_status": "parsed" if parsed_file.exists() else "uploaded",
                })
    return {"textbooks": textbooks}


def _safe_child(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


@app.post("/api/textbooks/upload")
async def upload_textbook_api(file: UploadFile = File(...)) -> dict[str, Any]:
    """上传教材文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_filename = Path(file.filename).name
    target = UPLOAD_DIR / safe_filename
    content = await file.read()
    target.write_bytes(content)

    return {
        "success": True,
        "message": "File uploaded successfully",
        "textbook_id": target.stem,
        "filename": safe_filename,
        "size": len(content),
        "path": str(target.relative_to(DATA_DIR.parent)),
    }


@app.delete("/api/textbooks/{textbook_id}")
def delete_textbook_api(textbook_id: str) -> dict[str, Any]:
    """删除教材文件、解析结果和该教材的图谱缓存。"""
    allowed_exts = (".pdf", ".md", ".markdown", ".txt", ".docx")
    deleted_files: list[str] = []

    for ext in allowed_exts:
        candidate = UPLOAD_DIR / f"{textbook_id}{ext}"
        if candidate.exists() and candidate.is_file() and _safe_child(candidate, UPLOAD_DIR):
            candidate.unlink()
            deleted_files.append(str(candidate.relative_to(DATA_DIR)))

    parsed_file = PARSED_DIR / f"{textbook_id}.json"
    if parsed_file.exists() and parsed_file.is_file() and _safe_child(parsed_file, PARSED_DIR):
        parsed_file.unlink()
        deleted_files.append(str(parsed_file.relative_to(DATA_DIR)))

    db_deleted = graph_store.delete_graph(textbook_id)
    if not deleted_files and not any(db_deleted.values()):
        raise HTTPException(status_code=404, detail=f"Textbook {textbook_id} not found")

    return {
        "success": True,
        "textbook_id": textbook_id,
        "deleted_files": deleted_files,
        "deleted_records": db_deleted,
    }


@app.post("/api/textbooks/{textbook_id}/parse")
def parse_textbook_api(textbook_id: str) -> dict[str, Any]:
    """解析指定教材"""
    file_path = None
    for ext in ['.pdf', '.md', '.txt', '.docx']:
        candidate = UPLOAD_DIR / f"{textbook_id}{ext}"
        if candidate.exists():
            file_path = candidate
            break

    if not file_path:
        raise HTTPException(status_code=404, detail=f"Textbook {textbook_id} not found")

    result = parser.parse_textbook({
        "textbook_id": textbook_id,
        "filename": file_path.name,
        "file_path": str(file_path),
    })
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Parse failed")
    return result


# 保留旧接口以兼容
@app.post("/upload")
async def upload_textbook(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_filename = Path(file.filename).name
    target = UPLOAD_DIR / safe_filename
    content = await file.read()
    target.write_bytes(content)

    return {
        "message": "File uploaded",
        "filename": safe_filename,
        "size": len(content),
        "path": str(target.relative_to(DATA_DIR.parent)),
    }


@app.post("/parse")
def parse_textbook(request: TextbookRequest) -> dict[str, Any]:
    result = parser.parse_textbook(request.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Parse failed")
    return result


@app.post("/api/graph/build/{textbook_id}")
def build_graph_api(textbook_id: str) -> dict[str, Any]:
    return graph_builder.build_graph({"textbook_id": textbook_id})


@app.get("/api/graph/{textbook_id}")
def get_graph_api(textbook_id: str) -> dict[str, Any]:
    return graph_builder.get_graph(textbook_id)


# LLM Provider endpoints are used directly by the settings modal.
@app.get("/api/llm/providers")
@app.get("/llm/providers", include_in_schema=False)
def list_providers() -> dict[str, Any]:
    return provider_registry()


@app.post("/api/llm/providers/health")
@app.post("/llm/providers/health", include_in_schema=False)
def check_provider_health(req: LLMConfigRequest) -> dict[str, Any]:
    try:
        return check_provider_config(req.active, req.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/llm/providers/models")
@app.post("/llm/providers/models", include_in_schema=False)
def fetch_provider_model_list(req: LLMConfigRequest) -> dict[str, Any]:
    try:
        return fetch_provider_models(req.active, req.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/llm/providers")
@app.post("/llm/providers", include_in_schema=False)
def update_provider(req: LLMConfigRequest) -> dict[str, Any]:
    try:
        set_active_provider(req.active, req.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "active": req.active, "registry": provider_registry()}


@app.get("/graph")
def get_graph(textbook_id: str = "demo-textbook") -> dict[str, Any]:
    return get_graph_api(textbook_id)


@app.post("/graph/build")
def build_graph(request: TextbookRequest) -> dict[str, Any]:
    return build_graph_api(request.textbook_id)


@app.post("/merge")
def merge_textbooks(request: MergeRequest) -> dict[str, Any]:
    return merger.merge_textbooks(request.textbook_ids)


@app.post("/api/merge/run")
def merge_textbooks_api(request: MergeRequest) -> dict[str, Any]:
    return merger.merge_textbooks_v2(request.textbook_ids)


@app.get("/api/merge/{merge_id}")
def get_merge_result(merge_id: str) -> dict[str, Any]:
    result = graph_store.load_merged_graph(merge_id)
    if not result:
        raise HTTPException(status_code=404, detail="Merge result not found")
    return result


@app.post("/rag")
def rag_query(request: RagRequest) -> dict[str, Any]:
    return rag.retrieve(request.query, request.top_k)


@app.post("/chat")
def chat_with_agent(request: ChatRequest) -> dict[str, Any]:
    return chat.reply(request.message, request.history)


@app.post("/report")
def generate_report(request: ReportRequest) -> dict[str, Any]:
    return report.generate_report(request.topic, request.textbook_ids)
