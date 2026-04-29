"""
Differ — produces a structured line-by-line diff with token-level changes.

Output schema per line:
{
    "line_number":  int,            # 1-based, references the longer document
    "status":       str,            # "unchanged" | "modified" | "added" | "removed"
    "before":       str | None,     # original line text  (None if added)
    "after":        str | None,     # revised line text   (None if removed)
    "tokens": [                     # only present when status == "modified"
        { "text": str, "type": str }  # type: "unchanged" | "added" | "removed"
    ]
}
"""

import difflib
from typing import List, Dict, Any


def compute_diff(lines_a: List[str], lines_b: List[str]) -> List[Dict[str, Any]]:
    """
    Compare two lists of lines and return a structured diff.

    Args:
        lines_a: Lines from the original document (before).
        lines_b: Lines from the revised document (after).

    Returns:
        List of diff entries, one per logical line change.
    """
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
    result = []
    line_number = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                line_number += 1
                result.append({
                    "line_number": line_number,
                    "status": "unchanged",
                    "before": lines_a[i1 + offset],
                    "after": lines_b[j1 + offset],
                    "tokens": [],
                })

        elif tag == "replace":
            # Pair up as many lines as possible; remainder are add/remove
            a_chunk = lines_a[i1:i2]
            b_chunk = lines_b[j1:j2]
            pairs = min(len(a_chunk), len(b_chunk))

            for offset in range(pairs):
                line_number += 1
                before = a_chunk[offset]
                after = b_chunk[offset]
                result.append({
                    "line_number": line_number,
                    "status": "modified",
                    "before": before,
                    "after": after,
                    "tokens": _token_diff(before, after),
                })

            # Handle any extra lines in either chunk
            for offset in range(pairs, len(a_chunk)):
                line_number += 1
                result.append({
                    "line_number": line_number,
                    "status": "removed",
                    "before": a_chunk[offset],
                    "after": None,
                    "tokens": [],
                })
            for offset in range(pairs, len(b_chunk)):
                line_number += 1
                result.append({
                    "line_number": line_number,
                    "status": "added",
                    "before": None,
                    "after": b_chunk[offset],
                    "tokens": [],
                })

        elif tag == "delete":
            for offset in range(i2 - i1):
                line_number += 1
                result.append({
                    "line_number": line_number,
                    "status": "removed",
                    "before": lines_a[i1 + offset],
                    "after": None,
                    "tokens": [],
                })

        elif tag == "insert":
            for offset in range(j2 - j1):
                line_number += 1
                result.append({
                    "line_number": line_number,
                    "status": "added",
                    "before": None,
                    "after": lines_b[j1 + offset],
                    "tokens": [],
                })

    return result


def _token_diff(before: str, after: str) -> List[Dict[str, str]]:
    """
    Produce a word-level token diff between two lines.
    Used to power inline redline highlighting in the combined view.

    Args:
        before: Original line text.
        after:  Revised line text.

    Returns:
        List of token objects with "text" and "type" fields.
    """
    words_a = before.split()
    words_b = after.split()
    matcher = difflib.SequenceMatcher(None, words_a, words_b, autojunk=False)
    tokens = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            tokens.append({
                "text": " ".join(words_a[i1:i2]),
                "type": "unchanged",
            })
        elif tag == "replace":
            tokens.append({
                "text": " ".join(words_a[i1:i2]),
                "type": "removed",
            })
            tokens.append({
                "text": " ".join(words_b[j1:j2]),
                "type": "added",
            })
        elif tag == "delete":
            tokens.append({
                "text": " ".join(words_a[i1:i2]),
                "type": "removed",
            })
        elif tag == "insert":
            tokens.append({
                "text": " ".join(words_b[j1:j2]),
                "type": "added",
            })

    # Re-insert spaces between tokens for readable rendering
    spaced = []
    for i, tok in enumerate(tokens):
        if i > 0 and tokens[i - 1]["text"] and tok["text"]:
            spaced.append({"text": " ", "type": "unchanged"})
        spaced.append(tok)

    return spaced
