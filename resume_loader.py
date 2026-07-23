"""Reads resume text out of a .txt, .pdf, or .docx file for the graph pipeline to consume."""

from __future__ import annotations

from pathlib import Path


class ResumeLoadError(Exception):
    """Raised when a resume file can't be found or parsed."""


def load_resume_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise ResumeLoadError(
            f"Resume file not found at {file_path}. Set RESUME_FILE_PATH in .env and place "
            f"the file there."
        )

    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)

    raise ResumeLoadError(f"Unsupported resume file type '{suffix}'. Use .txt, .pdf, or .docx.")


def _load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _load_docx(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs).strip()
