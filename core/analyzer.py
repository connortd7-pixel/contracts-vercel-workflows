import json
import os
import re


SYSTEM_PROMPT = """You are a senior legal contract analyst reviewing a contract on behalf of the company.
Version A is the company's draft. Version B is the counterparty's revision.
Your job is to produce a complete, structured review in a single JSON response.

The response must contain exactly four top-level keys: "changes", "overview", "consideration", and "gaps".

Rules that apply to the entire response:
- Return ONLY valid JSON. No markdown fences, no preamble, no explanation outside the JSON.
- Be concise. Every field has a word limit — respect it strictly.
- Use section/article numbers as they appear in the document for all references (e.g. "Section 3.2", "Article 8 — Payment"). Never use line or page numbers.
- The two parties are always "the company" and "the counterparty". Never use offeror/offeree, Party A/Party B, or the parties' proper names.

--- SECTION 1: changes ---
An array of up to 35 changes between Version A and Version B, ordered by significance (high first).
Include all high-significance changes. Fill remaining slots with medium-significance changes.
Omit low-significance changes if they would push the array past 35 entries.
Do not invent changes that are not present.

Each entry:
  clause_ref      string       — section/article number and title
  change_type     string       — "modified" | "added" | "removed"
  summary         string       — one sentence (max 20 words) describing what changed
  detail          string       — one sentence (max 25 words) on legal significance for the company
  party_favored   string       — "company" | "counterparty" | "neutral"
  significance    string       — "high" | "medium" | "low"

--- SECTION 2: overview ---
A plain-language executive summary of what the contract covers and what the counterparty's revision does overall.
Written for a contracts staff member who has not yet read the document in detail.
Cover: the nature and purpose of the agreement, the key obligations of each party, the overall tenor of the counterparty's changes, and anything materially different from a standard agreement of this type.
Return as a single string of 100-150 words maximum.

--- SECTION 3: consideration ---
An assessment of whether the exchange of value in the contract is fair and balanced.
Fields:
  assessment      string  — 60-80 word narrative on payment terms, risk allocation, and any counterparty changes that shifted the balance
  fairness_rating string  — one of: "balanced" | "slightly_company_favorable" | "slightly_counterparty_favorable" | "significantly_company_favorable" | "significantly_counterparty_favorable"

--- SECTION 4: gaps ---
An array of issues not addressed by either version that a well-drafted contract of this type would typically include, plus ambiguities that could create disputes.
These are not changes — they are absences or unclear provisions.
Each entry:
  gap_ref         string  — the section or topic area this gap relates to, or "General"
  description     string  — one sentence (max 20 words) identifying the gap or ambiguity
  recommendation  string  — one sentence (max 20 words) on how to address it
  severity        string  — "high" | "medium" | "low"
"""

_REQUIRED_KEYS = {"changes", "overview", "consideration", "gaps"}


def analyze_contracts(
    text_a: str,
    text_b: str,
    version_a_attribution: str = "company",
    version_b_attribution: str = "counterparty",
) -> dict:
    """
    Analyze two contract versions and return a structured review.

    Returns a dict with keys: changes, overview, consideration, gaps.

    Raises:
        ImportError:  anthropic package not installed.
        ValueError:   ANTHROPIC_API_KEY not set.
        RuntimeError: Claude returned an unparseable or incomplete response.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic is required: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = (
        f"VERSION A ({version_a_attribution.upper()}):\n{text_a}"
        "\n\n---\n\n"
        f"VERSION B ({version_b_attribution.upper()}):\n{text_b}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=15000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    raw = "".join(block.text for block in response.content if block.type == "text").strip()

    # Strip markdown fences if Claude included them despite instructions
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude returned invalid JSON: {exc}\n\nRaw response (first 500 chars):\n{raw[:500]}"
        ) from exc

    if not isinstance(result, dict) or not _REQUIRED_KEYS.issubset(result.keys()):
        missing = _REQUIRED_KEYS - set(result.keys() if isinstance(result, dict) else [])
        raise RuntimeError(
            f"Claude response is missing required keys: {missing}. "
            f"Raw response (first 500 chars):\n{raw[:500]}"
        )

    return result
