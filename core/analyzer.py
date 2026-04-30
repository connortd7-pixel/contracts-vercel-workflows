"""
Semantic contract analyzer — sends diff change blocks to Claude for plain-English explanation.

Architecture: diff-first + Claude-explains.
  1. compute_diff() finds EVERY change deterministically (completeness guarantee).
  2. This module groups those changes into clause-level blocks with surrounding context.
  3. Claude explains each block — it cannot miss or invent changes.
"""

import json
import os
from typing import List, Dict, Any, Optional

# Unchanged lines included above/below each change block so Claude can identify the clause.
_CONTEXT_LINES = 4

# Merge change groups that are within this many lines of each other into one block.
_MERGE_GAP = 3


def analyze_diff(diff: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Produce a plain-English analysis of every changed clause in the diff.

    Args:
        diff: Output of compute_diff() — list of line dicts with status/before/after/tokens.

    Returns:
        List of change-analysis dicts, one per distinct change block:
            block_id        int    — sequential 1-based identifier
            clause_ref      str    — section/clause found in surrounding context
            change_type     str    — "modified" | "added" | "removed"
            summary         str    — one-sentence plain-English description
            detail          str    — 2-3 sentence legal significance
            before_snippet  str|None
            after_snippet   str|None

    Raises:
        ImportError:  anthropic package not installed.
        ValueError:   ANTHROPIC_API_KEY not set.
        RuntimeError: Claude returned an unparseable response.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic is required: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    blocks = _extract_change_blocks(diff)
    if not blocks:
        return []

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = (
        "You are a legal contract analyst reviewing a redline comparison between two contract versions. "
        "You will receive numbered change blocks. Each block shows surrounding context lines (for clause "
        "identification) and the specific text that changed.\n\n"
        "Rules:\n"
        "- Produce exactly one JSON entry per change block — no skipping, no merging, no extras.\n"
        "- Return ONLY a JSON array with no markdown fences, no preamble, no explanation.\n"
        "- Use the context lines to identify the clause/section reference (e.g. 'Section 3.2(a)', "
        "'Recital B', 'Schedule 1'). If genuinely unidentifiable write 'Unknown'.\n\n"
        "Output schema:\n"
        "[\n"
        "  {\n"
        '    "block_id": <integer>,\n'
        '    "clause_ref": "<section reference>",\n'
        '    "change_type": "<modified|added|removed>",\n'
        '    "summary": "<one sentence plain English>",\n'
        '    "detail": "<2-3 sentences on legal significance and practical impact>",\n'
        '    "before_snippet": "<original text or null>",\n'
        '    "after_snippet": "<revised text or null>"\n'
        "  }\n"
        "]"
    )

    user_text = _build_prompt(blocks)

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    ) as stream:
        message = stream.get_final_message()

    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    response_text = response_text.strip()

    # Strip markdown code fences if Claude included them despite instructions
    if response_text.startswith("```"):
        inner = response_text.splitlines()
        end = len(inner) - 1 if inner[-1].strip() == "```" else len(inner)
        response_text = "\n".join(inner[1:end])

    try:
        analyses = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Claude returned invalid JSON: {e}\n\nRaw response (first 500 chars):\n{response_text[:500]}"
        ) from e

    if not isinstance(analyses, list):
        raise RuntimeError(f"Expected JSON array from Claude, got {type(analyses).__name__}")

    # Backfill snippets from the raw diff in case Claude omitted them
    block_map = {b["block_id"]: b for b in blocks}
    for entry in analyses:
        bid = entry.get("block_id")
        if bid in block_map:
            if not entry.get("before_snippet"):
                entry["before_snippet"] = block_map[bid].get("before_text")
            if not entry.get("after_snippet"):
                entry["after_snippet"] = block_map[bid].get("after_text")

    return analyses


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_change_blocks(diff: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    n = len(diff)
    changed = sorted(i for i, l in enumerate(diff) if l["status"] != "unchanged")
    if not changed:
        return []

    # Merge nearby changed indices into contiguous groups
    groups: List[tuple] = []
    gs = changed[0]
    ge = changed[0]
    for idx in changed[1:]:
        if idx <= ge + _MERGE_GAP:
            ge = idx
        else:
            groups.append((gs, ge))
            gs = ge = idx
    groups.append((gs, ge))

    blocks = []
    for block_id, (start, end) in enumerate(groups, 1):
        ctx_start = max(0, start - _CONTEXT_LINES)
        ctx_end   = min(n, end + _CONTEXT_LINES + 1)

        context_before = [
            diff[i]["before"] or diff[i]["after"] or ""
            for i in range(ctx_start, start)
        ]
        changed_lines = diff[start : end + 1]
        context_after = [
            diff[i]["after"] or diff[i]["before"] or ""
            for i in range(end + 1, ctx_end)
        ]

        before_parts = [l["before"] for l in changed_lines if l.get("before")]
        after_parts  = [l["after"]  for l in changed_lines if l.get("after")]

        # Dominant change type for the block
        statuses = [l["status"] for l in changed_lines]
        if all(s == "added"   for s in statuses):
            block_type = "added"
        elif all(s == "removed" for s in statuses):
            block_type = "removed"
        else:
            block_type = "modified"

        blocks.append({
            "block_id":       block_id,
            "block_type":     block_type,
            "context_before": context_before,
            "changed_lines":  changed_lines,
            "context_after":  context_after,
            "before_text":    " ".join(before_parts) if before_parts else None,
            "after_text":     " ".join(after_parts)  if after_parts  else None,
        })

    return blocks


def _build_prompt(blocks: List[Dict[str, Any]]) -> str:
    lines = [
        f"There are {len(blocks)} change block(s) to analyze. "
        "Return exactly one JSON entry per block.\n"
    ]

    for b in blocks:
        lines.append(f"=== CHANGE BLOCK {b['block_id']} ===")

        if b["context_before"]:
            lines.append("[Context before change]")
            for l in b["context_before"]:
                if l:
                    lines.append(f"  {l}")

        lines.append("[Changed text]")
        for entry in b["changed_lines"]:
            s = entry["status"]
            if s == "modified":
                if entry.get("before"):
                    lines.append(f"  BEFORE: {entry['before']}")
                if entry.get("after"):
                    lines.append(f"  AFTER:  {entry['after']}")
            elif s == "removed":
                lines.append(f"  REMOVED: {entry['before']}")
            elif s == "added":
                lines.append(f"  ADDED: {entry['after']}")

        if b["context_after"]:
            lines.append("[Context after change]")
            for l in b["context_after"]:
                if l:
                    lines.append(f"  {l}")

        lines.append("")

    return "\n".join(lines)
