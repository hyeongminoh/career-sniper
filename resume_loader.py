"""Reads resume text out of a .txt, .pdf, or .docx file — either one already saved on disk
(used by the CLI) or an in-memory upload like Streamlit's `st.file_uploader` result (used by
the UI). Both paths share the same per-format parsing so the two never drift apart.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO


class ResumeLoadError(Exception):
    """Raised when a resume file can't be found or parsed."""


def load_resume_text(file_path: str) -> str:
    """Reads resume text from a file already saved on disk."""
    path = Path(file_path)
    if not path.exists():
        raise ResumeLoadError(
            f"Resume file not found at {file_path}. Set RESUME_FILE_PATH in .env and place "
            f"the file there."
        )
    with path.open("rb") as f:
        return parse_resume_stream(f, path.name)


def parse_resume_stream(file_obj: BinaryIO, filename: str) -> str:
    """Reads resume text from an in-memory file-like object (e.g. a Streamlit upload).
    `filename` is only used to determine the format — nothing is read from disk."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        raw = file_obj.read()
        return raw.decode("utf-8") if isinstance(raw, bytes) else raw
    if suffix == ".pdf":
        return _parse_pdf(file_obj)
    if suffix == ".docx":
        return _parse_docx(file_obj)

    raise ResumeLoadError(f"Unsupported resume file type '{suffix}'. Use .txt, .pdf, or .docx.")


def _parse_pdf(file_obj: BinaryIO) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_obj)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _parse_docx(file_obj: BinaryIO) -> str:
    from docx import Document

    document = Document(file_obj)
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs).strip()
