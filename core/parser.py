"""
File parser — extracts a list of text lines from PDF or DOCX bytes.
"""

import io
import re
from typing import List

# Matches common PDF page-break artifacts that should not be treated as content.
_ARTIFACT_RE = re.compile(
    r'^('
    r'page\s+\d+\s+of\s+\d+'           # "Page 3 of 18"
    r'|\d+'                              # bare page number "3"
    r'|.*\s\d{1,2}[./]\d{1,2}[./]\d{2,4}$'  # line ending in a date  "Office 09.07.2021"
    r')$',
    re.IGNORECASE,
)

# Words that, when a line ends with one, strongly suggest the line wraps into the next.
_CONTINUATION_ENDINGS = frozenset({
    "a", "an", "the",
    "and", "or", "but", "nor",
    "of", "in", "for", "to", "with", "by", "at", "from", "as", "on",
    "that", "which", "who", "whom", "whose",
    "this", "these", "those",
    "including", "pursuant", "under", "per", "between", "within",
    "any", "all", "both", "either", "neither", "whether", "each",
    "its", "their", "such",
})


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

    try:
        pdf_file = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg or "notimplemented" in msg:
            raise ValueError("PDF is password-protected and cannot be parsed without a password")
        raise ValueError(f"Failed to open PDF: {e}") from e

    raw_lines = []
    try:
        with pdf_file:
            for page in pdf_file.pages:
                text = page.extract_text()
                if text:
                    for line in text.splitlines():
                        stripped = line.strip()
                        if stripped:
                            raw_lines.append(stripped)
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise ValueError("PDF is password-protected and cannot be parsed without a password")
        raise ValueError(f"Failed to read PDF content: {e}") from e

    lines = _join_paragraphs(raw_lines)

    if not lines:
        raise ValueError("PDF contains no extractable text (may be scanned or image-only)")

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

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Failed to open DOCX (file may be corrupted or not a valid .docx): {e}") from e

    raw_lines = []
    for para in doc.paragraphs:
        stripped = para.text.strip()
        if stripped:
            raw_lines.append(stripped)

    if not raw_lines:
        raise ValueError("DOCX contains no text")

    return _join_paragraphs(raw_lines)


# ---------------------------------------------------------------------------
# PDF paragraph reconstruction helpers
# ---------------------------------------------------------------------------

def _join_paragraphs(raw_lines: List[str]) -> List[str]:
    """
    Merge visually-wrapped lines back into logical paragraphs.

    Works for both PDF output (pdfplumber visual lines) and DOCX output from
    PDF converters that write each visual line as its own paragraph.

    Two passes:
      1. Drop lines that are clearly page artifacts (page numbers, dates).
      2. Merge consecutive lines that form a single wrapped sentence/paragraph.
    """
    filtered = [l for l in raw_lines if not _ARTIFACT_RE.match(l)]

    if not filtered:
        return []

    result = [filtered[0]]
    for line in filtered[1:]:
        if _is_continuation(result[-1], line):
            result[-1] = result[-1] + " " + line
        else:
            result.append(line)

    return result


def _is_continuation(prev: str, curr: str) -> bool:
    """
    Return True when curr is a wrapped continuation of prev rather than a new paragraph.

    Signals (any one is sufficient):
    - prev has an unclosed parenthesis     →  e.g. "(see Exhibit" / "A)."
    - curr starts with a lowercase letter  →  cannot open a new sentence
    - prev ends with a comma               →  clause is still open
    - prev ends with a known connector word (and, of, including, …)
    """
    if not prev or not curr:
        return False

    # Unclosed parenthetical — very common in legal text, e.g. "(see Exhibit A)"
    # split across a line break as "(see Exhibit" + "A)."
    if prev.count("(") > prev.count(")"):
        return True

    # Lowercase start is the strongest signal — cannot begin a new sentence
    if curr[0].islower():
        return True

    # Open clause — ends with comma
    if prev.rstrip().endswith(","):
        return True

    # Ends with a connector word (strip trailing punctuation before checking)
    last_word = prev.rstrip().rsplit(None, 1)[-1].lower().rstrip(",:;(")
    return last_word in _CONTINUATION_ENDINGS
