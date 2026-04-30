# contracts-vercel-workflows

PDF and DOCX contract comparison API, deployed on Vercel. Triggered by button click from a Lovable frontend, with results stored in Supabase.

## Architecture

```
Lovable UI → POST /api/analyze → Vercel Python Function
                                      ↓
                               Fetch files from Supabase Storage
                                      ↓
                               Parse PDF / DOCX → plain text
                                      ↓
                               Claude API (full-document analysis)
                                      ↓
                               Store result → Supabase (contract_analyses)
                                      ↓
                               Lovable renders review (changes, overview, consideration, gaps)

Lovable UI → POST /api/compare → Vercel Python Function
                                      ↓
                               Fetch files from Supabase Storage
                                      ↓
                               Parse PDF / DOCX → lines
                                      ↓
                               Line diff + token diff
                                      ↓
                               Lovable renders side-by-side or redline view
```

## Project Structure

```
├── api/
│   ├── analyze.py          # Vercel serverless endpoint (POST /api/analyze)
│   └── compare.py          # Vercel serverless endpoint (POST /api/compare)
├── core/
│   ├── supabase_client.py  # Fetch files from / save results to Supabase
│   ├── parser.py           # PDF + DOCX → list of lines
│   ├── differ.py           # Line-level + token-level diff logic
│   └── analyzer.py         # Claude-powered contract analysis
├── tests/
│   └── test_differ.py      # Unit tests
├── .env.example            # Environment variable template
├── requirements.txt
└── vercel.json
```

## Local Setup

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/contracts-vercel-workflows.git
cd contracts-vercel-workflows

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Supabase credentials
```

## Environment Variables

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase → Settings → API → service_role secret |
| `SUPABASE_BUCKET` | Supabase → Storage → your bucket name |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |

Set these in Vercel under Project → Settings → Environment Variables.

## API

### `POST /api/analyze`

Fetches both contract versions from Supabase Storage, sends them to Claude for a complete AI-powered review, saves the result to `contract_analyses`, and returns the full analysis. This endpoint covers US-07 (document comparison) and US-08 (consideration analysis) in a single call. US-09 (plain-language summary) is retired — its output is now the `overview` field.

**Request body:**
```json
{
  "contract_id": "a1000000-0001-0001-0001-000000000001",
  "version_a_id": "uuid",
  "version_b_id": "uuid",
  "file_a": "a1000000-0001-0001-0001-000000000001/draft-snapshot-v1-filename.pdf",
  "file_b": "a1000000-0001-0001-0001-000000000001/versions/filename.pdf",
  "version_a_attribution": "company",
  "version_b_attribution": "counterparty"
}
```

`version_a_attribution` and `version_b_attribution` are optional (default: `"company"` / `"counterparty"`).

**Response:**
```json
{
  "status": "ok",
  "contract_id": "...",
  "version_a_id": "...",
  "version_b_id": "...",
  "analysis": {
    "changes": [
      {
        "clause_ref": "Section 3.2 — Payment Terms",
        "change_type": "modified",
        "summary": "Payment window extended from 30 to 60 days.",
        "detail": "...",
        "before_text": "Payment due within 30 days of invoice.",
        "after_text": "Payment due within 60 days of invoice.",
        "party_favored": "counterparty",
        "significance": "high"
      }
    ],
    "overview": "...",
    "consideration": {
      "assessment": "...",
      "fairness_rating": "slightly_counterparty_favorable"
    },
    "gaps": [
      {
        "gap_ref": "General",
        "description": "No dispute resolution clause is included.",
        "recommendation": "Add an arbitration or mediation clause.",
        "severity": "high"
      }
    ]
  }
}
```

**Supabase table required:** run the `CREATE TABLE` statement in `core/supabase_client.py → save_analysis_result` before deploying.

---

### `POST /api/compare`

**Request body:**
```json
{
  "file_a": "contracts/original.pdf",
  "file_b": "contracts/revised.docx"
}
```

**Response:**
```json
{
  "status": "ok",
  "file_a": "contracts/original.pdf",
  "file_b": "contracts/revised.docx",
  "lines": [
    {
      "line_number": 4,
      "status": "modified",
      "before": "The agreement shall terminate on Dec 31.",
      "after": "The agreement shall terminate on Jan 15.",
      "tokens": [
        { "text": "The agreement shall terminate on", "type": "unchanged" },
        { "text": " ", "type": "unchanged" },
        { "text": "Dec 31.", "type": "removed" },
        { "text": " ", "type": "unchanged" },
        { "text": "Jan 15.", "type": "added" }
      ]
    }
  ]
}
```

**Line status values:** `unchanged` | `modified` | `added` | `removed`  
**Token type values:** `unchanged` | `added` | `removed`

## Running Tests

```bash
python -m pytest tests/ -v
```

## Deployment

```bash
npm i -g vercel
vercel        # follow prompts to link to your Vercel account
```

Set environment variables in the Vercel dashboard before deploying to production.

## TODOs (pending Supabase access)

- [ ] Fill in `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_BUCKET`, `ANTHROPIC_API_KEY` in `.env`
- [ ] Run the `CREATE TABLE contract_analyses` statement from `core/supabase_client.py → save_analysis_result`
- [ ] Implement `save_diff_result()` in `core/supabase_client.py` with your table schema
- [ ] Confirm Supabase Storage bucket name and file path conventions with Lovable team
