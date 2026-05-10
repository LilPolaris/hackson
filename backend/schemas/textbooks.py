from typing import Literal

from pydantic import BaseModel


TextbookFormat = Literal["pdf", "md", "txt"]
ParseStatus = Literal["uploaded", "parsing", "parsed", "failed"]


class TextbookMetadata(BaseModel):
    textbook_id: str
    filename: str
    format: TextbookFormat
    size_bytes: int
    parse_status: ParseStatus
    uploaded_at: str
    updated_at: str
    storage_path: str
    parsed_path: str | None = None
    error_message: str | None = None


class TextbookPublic(BaseModel):
    textbook_id: str
    filename: str
    format: TextbookFormat
    size_bytes: int
    parse_status: ParseStatus
    uploaded_at: str
    updated_at: str
    error_message: str | None = None


class TextbookListResponse(BaseModel):
    textbooks: list[TextbookPublic]


class TextbookPage(BaseModel):
    page_number: int
    char_count: int


class TextbookChapter(BaseModel):
    title: str
    start_page: int
    end_page: int | None = None
    start_char: int
    char_count: int | None = None


class ParsedTextbook(BaseModel):
    textbook_id: str
    filename: str
    title: str
    format: TextbookFormat
    total_pages: int
    total_chars: int
    pages: list[TextbookPage]
    chapters: list[TextbookChapter]
