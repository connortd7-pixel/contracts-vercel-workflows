"""
File parser — extracts a list of text lines from PDF or DOCX bytes.
"""

import io
from typing import List


def parse_file(file_bytes: bytes, extension: str) -> List[str]:
    """
    Parse raw file bytes into a list of non-empty text lines.

    Args:
        file_bytes: Raw bytes of the file.
        extension:  File extension without dot — "pdf" or "docx".

    Returns:
        List of stripped, non-empty lines in document order.

    Raises:
        ValueError: If the extension is not supported.
    """
    if extension == "pdf":
        return _parse_pdf(file_bytes)
    elif extension == "docx":
        return _parse_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{extension}")


def _parse_pdf(file_bytes: bytes) -> List[str]:
    """
    Extract lines from a PDF using pdfplumber.
    Iterates pages in order; within each page extracts lines top-to-bottom.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required: pip install pdfplumber")

    lines = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
    return lines


def _parse_docx(file_bytes: bytes) -> List[str]:
    """
    Extract lines from a DOCX using python-docx.
    Each paragraph becomes one line; empty paragraphs are skipped.
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required: pip install python-docx")

    doc = Document(io.BytesIO(file_bytes))
    lines = []
    for para in doc.paragraphs:
        stripped = para.text.strip()
        if stripped:
            lines.append(stripped)
    return lines
