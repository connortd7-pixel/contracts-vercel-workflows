import json
import os
import re


SYSTEM_PROMPT = """You are a senior legal contract analyst reviewing a contract on behalf of the company.
Version A is the company's draft. Version B is the counterparty's revision.
Your job is to produce a complete, structured review in a single JSON response.

The response must contain exactly four top-level keys: "changes", "overview", "consideration", and "gaps".

Rules that apply to the entire response:
- Return ONLY valid JSON. No markdown fences, no preamble, no explanation outside the JSON.
- Use section/article numbers as they appear in the document for all references (e.g. "Section 3.2", "Article 8 — Payment"). Never use line or page numbers.
- The two parties are always "the company" and "the counterparty". Never use offeror/offeree, Party A/Party B, or the parties' proper names.

--- SECTION 1: changes ---
An array of every discrete change between Version A and Version B.
Do not omit any change. Do not invent changes that are not present.
One entry per sentence-level change — do not merge multiple changes in the same section into a single entry.

Each entry:
  clause_ref      string       — section/article number and title
  change_type     string       — "modified" | "added" | "removed"
  summary         string       — one sentence plain English description of what changed
  detail          string       — 2-3 sentences on legal significance and practical impact for the company
  before_text     string|null  — original language, or null if the change is an addition
  after_text      string|null  — revised language, or null if the change is a removal
  party_favored   string       — "company" | "counterparty" | "neutral"
  significance    string       — "high" | "medium" | "low"

--- SECTION 2: overview ---
A plain-language executive summary of what the contract covers and what the counterparty's revision does overall.
Written for a contracts staff member who has not yet read the document in detail.
Cover: the nature and purpose of the agreement, the key obligations of each party, the overall tenor of the counterparty's changes (e.g. risk-shifting, cost-reduction, scope-narrowing), and anything that stands out as materially different from a standard agreement of this type.
Return as a single string of 150-250 words.

--- SECTION 3: consideration ---
An assessment of whether the exchange of value in the contract is fair and balanced.
Evaluate: whether compensation or payment terms are commensurate with the obligations, whether risk allocation (liability caps, indemnification, insurance) is proportionate, and whether any counterparty changes have materially shifted the balance of consideration.
Fields:
  assessment      string  — 100-150 word narrative
  fairness_rating string  — one of: "balanced" | "slightly_company_favorable" | "slightly_counterparty_favorable" | "significantly_company_favorable" | "significantly_counterparty_favorable"

--- SECTION 4: gaps ---
An array of issues not addressed by either version that a well-drafted contract of this type would typically include, plus any ambiguities in the current language that could create disputes.
These are not changes — they are absences or unclear provisions.
Each entry:
  gap_ref         string  — the section or topic area this gap relates to, or "General"
  description     string  — one sentence identifying the gap or ambiguity
  recommendation  string  — one sentence on how to address it
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
        max_tokens=8000,
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
