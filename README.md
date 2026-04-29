# contracts-vercel-workflows

PDF and DOCX contract comparison API, deployed on Vercel. Triggered by button click from a Lovable frontend, with results stored in Supabase.

## Architecture

```
Lovable UI → POST /api/compare → Vercel Python Function
                                      ↓
                               Fetch files from Supabase Storage
                                      ↓
                               Parse PDF / DOCX → lines
                                      ↓
                               Line diff + token diff
                                      ↓
                               Store result JSON → Supabase
                                      ↓
                               Lovable renders side-by-side or redline view
```

## Project Structure

```
├── api/
│   └── compare.py          # Vercel serverless endpoint (POST /api/compare)
├── core/
│   ├── supabase_client.py  # Fetch files from / save results to Supabase
│   ├── parser.py           # PDF + DOCX → list of lines
│   └── differ.py           # Line-level + token-level diff logic
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

Set these in Vercel under Project → Settings → Environment Variables.

## API

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

- [ ] Fill in `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_BUCKET` in `.env`
- [ ] Implement `save_diff_result()` in `core/supabase_client.py` with your table schema
- [ ] Update `api/compare.py` to call `save_diff_result()` after computing the diff
- [ ] Confirm Supabase Storage bucket name and file path conventions with Lovable team
