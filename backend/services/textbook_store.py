from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.schemas.textbooks import ParsedTextbook, TextbookMetadata, TextbookPublic


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT / "tmp" / "textbooks"
UPLOAD_DIR = BASE_DIR / "uploads"
PARSED_DIR = BASE_DIR / "parsed"
INDEX_PATH = BASE_DIR / "index.json"

ALLOWED_FORMATS = {
    ".pdf": "pdf",
    ".md": "md",
    ".txt": "txt",
}

CHAPTER_PATTERN = re.compile(
    r"(?im)^\s*(第\s*[0-9一二三四五六七八九十百千万零〇两]+\s*章[^\r\n]*|绪论|chapter\s+\d+[^\r\n]*)"
)


class TextbookError(Exception):
    status_code = 400


class UnsupportedTextbookFormat(TextbookError):
    status_code = 400


class TextbookNotFound(TextbookError):
    status_code = 404


class TextbookParseFailed(TextbookError):
    status_code = 500


def ensure_directories() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("{}", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    file_format = ALLOWED_FORMATS.get(suffix)
    if file_format is None:
        raise UnsupportedTextbookFormat("只支持 PDF、Markdown(.md) 和纯文本(.txt) 文件")
    return file_format


def public_metadata(metadata: TextbookMetadata) -> TextbookPublic:
    return TextbookPublic(**metadata.model_dump())


def load_index() -> dict[str, TextbookMetadata]:
    ensure_directories()
    try:
        raw_index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raw_index = {}

    return {
        textbook_id: TextbookMetadata(**metadata)
        for textbook_id, metadata in raw_index.items()
    }


def save_index(index: dict[str, TextbookMetadata]) -> None:
    ensure_directories()
    serialized = {
        textbook_id: metadata.model_dump()
        for textbook_id, metadata in index.items()
    }
    INDEX_PATH.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_textbooks() -> list[TextbookPublic]:
    index = load_index()
    textbooks = sorted(index.values(), key=lambda item: item.uploaded_at, reverse=True)
    return [public_metadata(metadata) for metadata in textbooks]


async def save_upload(file: UploadFile) -> TextbookPublic:
    if not file.filename:
        raise UnsupportedTextbookFormat("缺少文件名")

    ensure_directories()
    filename = Path(file.filename).name
    file_format = detect_format(filename)
    textbook_id = str(uuid.uuid4())
    storage_path = UPLOAD_DIR / f"{textbook_id}.{file_format}"

    size_bytes = 0
    with storage_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            output.write(chunk)

    timestamp = now_iso()
    metadata = TextbookMetadata(
        textbook_id=textbook_id,
        filename=filename,
        format=file_format,
        size_bytes=size_bytes,
        parse_status="uploaded",
        uploaded_at=timestamp,
        updated_at=timestamp,
        storage_path=str(storage_path),
    )

    index = load_index()
    index[textbook_id] = metadata
    save_index(index)
    return public_metadata(metadata)


def parse_uploaded_textbook(textbook_id: str) -> ParsedTextbook:
    index = load_index()
    metadata = index.get(textbook_id)
    if metadata is None:
        raise TextbookNotFound("未找到该教材")

    metadata.parse_status = "parsing"
    metadata.updated_at = now_iso()
    metadata.error_message = None
    index[textbook_id] = metadata
    save_index(index)

    try:
        source_path = Path(metadata.storage_path)
        if metadata.format == "pdf":
            parsed = parse_pdf(metadata, source_path)
        else:
            parsed = parse_text(metadata, source_path)

        parsed_path = PARSED_DIR / f"{textbook_id}.json"
        parsed_path.write_text(
            json.dumps(parsed.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        metadata.parse_status = "parsed"
        metadata.parsed_path = str(parsed_path)
        metadata.updated_at = now_iso()
        index[textbook_id] = metadata
        save_index(index)
        return parsed
    except Exception as exc:
        metadata.parse_status = "failed"
        metadata.error_message = str(exc)
        metadata.updated_at = now_iso()
        index[textbook_id] = metadata
        save_index(index)
        raise TextbookParseFailed(str(exc)) from exc


def parse_pdf(metadata: TextbookMetadata, source_path: Path) -> ParsedTextbook:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("缺少 PyMuPDF，请先安装 requirements.txt 中的 PyMuPDF") from exc

    pages: list[dict[str, int]] = []
    chapter_starts: list[dict[str, Any]] = []
    total_chars = 0

    with fitz.open(source_path) as document:
        total_pages = document.page_count
        for page_index in range(total_pages):
            page = document.load_page(page_index)
            text = page.get_text("text") or ""
            page_number = page_index + 1
            page_start_char = total_chars

            pages.append({"page_number": page_number, "char_count": len(text)})
            chapter_starts.extend(find_chapter_starts(text, page_number, page_start_char))
            total_chars += len(text)

    chapters = complete_chapters(chapter_starts, total_pages, total_chars)
    return ParsedTextbook(
        textbook_id=metadata.textbook_id,
        filename=metadata.filename,
        title=Path(metadata.filename).stem,
        format=metadata.format,
        total_pages=total_pages,
        total_chars=total_chars,
        pages=pages,
        chapters=chapters,
    )


def parse_text(metadata: TextbookMetadata, source_path: Path) -> ParsedTextbook:
    text = read_text_file(source_path)
    total_chars = len(text)
    chapter_starts = find_chapter_starts(text, page_number=1, page_start_char=0)
    chapters = complete_chapters(chapter_starts, total_pages=1, total_chars=total_chars)

    return ParsedTextbook(
        textbook_id=metadata.textbook_id,
        filename=metadata.filename,
        title=Path(metadata.filename).stem,
        format=metadata.format,
        total_pages=1,
        total_chars=total_chars,
        pages=[{"page_number": 1, "char_count": total_chars}],
        chapters=chapters,
    )


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return path.read_text(encoding="utf-8", errors="ignore")


def find_chapter_starts(
    text: str,
    page_number: int,
    page_start_char: int,
) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    for match in CHAPTER_PATTERN.finditer(text):
        title = re.sub(r"\s+", " ", match.group(1).strip())
        chapters.append(
            {
                "title": title,
                "start_page": page_number,
                "start_char": page_start_char + match.start(1),
            }
        )
    return chapters


def complete_chapters(
    chapter_starts: list[dict[str, Any]],
    total_pages: int,
    total_chars: int,
) -> list[dict[str, Any]]:
    if not chapter_starts:
        return [
            {
                "title": "全文",
                "start_page": 1,
                "end_page": total_pages,
                "start_char": 0,
                "char_count": total_chars,
            }
        ]

    chapters: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapter_starts):
        next_chapter = chapter_starts[index + 1] if index + 1 < len(chapter_starts) else None
        end_page = total_pages
        end_char = total_chars

        if next_chapter is not None:
            end_char = next_chapter["start_char"]
            end_page = (
                next_chapter["start_page"]
                if next_chapter["start_page"] == chapter["start_page"]
                else next_chapter["start_page"] - 1
            )

        chapters.append(
            {
                "title": chapter["title"],
                "start_page": chapter["start_page"],
                "end_page": max(chapter["start_page"], end_page),
                "start_char": chapter["start_char"],
                "char_count": max(0, end_char - chapter["start_char"]),
            }
        )

    return chapters
