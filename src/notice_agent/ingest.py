"""Safe local ingestion for pasted text, .txt, .docx and .pdf notices."""

from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2000
MAX_UNCOMPRESSED_BYTES = 30 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt", ".docx", ".pdf"}


class UnsafeDocumentError(ValueError):
    """Raised when an uploaded file violates the local safety policy."""


def _validate_size(path: Path) -> None:
    size = path.stat().st_size
    if size <= 0 or size > MAX_FILE_BYTES:
        raise UnsafeDocumentError("文件为空或超过 5 MB 限制")


def _validate_docx_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise UnsafeDocumentError("DOCX 压缩包条目过多")
            if sum(item.file_size for item in entries) > MAX_UNCOMPRESSED_BYTES:
                raise UnsafeDocumentError("DOCX 解压后体积过大")
            for item in entries:
                name = item.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    raise UnsafeDocumentError("DOCX 包含不安全路径")
                if name.lower().endswith((".exe", ".js", ".vbs", ".bin")):
                    raise UnsafeDocumentError("DOCX 包含不允许的活动内容")
    except zipfile.BadZipFile as exc:
        raise UnsafeDocumentError("文件不是有效的 DOCX") from exc


def _read_docx(path: Path) -> str:
    _validate_docx_archive(path)
    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    if len(reader.pages) > 30:
        raise UnsafeDocumentError("PDF 超过 30 页限制")
    return "\n".join((page.extract_text() or "") for page in reader.pages[:30])


def read_notice_file(file_path: str | Path) -> str:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UnsafeDocumentError("仅支持 .txt、.docx、.pdf")
    _validate_size(path)
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    elif suffix == ".docx":
        text = _read_docx(path)
    else:
        text = _read_pdf(path)
    text = text.strip()
    if len(text) < 8:
        raise UnsafeDocumentError("未提取到足够文本；扫描版 PDF 需先进行 OCR")
    if len(text) > 20_000:
        text = text[:20_000]
    return text
