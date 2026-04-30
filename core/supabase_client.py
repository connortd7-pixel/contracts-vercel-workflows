"""
Supabase client — fetches raw file bytes from Supabase Storage.

Replace the placeholder values below once you have access to your
Supabase project:
  SUPABASE_URL  → Settings > API > Project URL
  SUPABASE_KEY  → Settings > API > service_role secret key
  BUCKET_NAME   → Storage > bucket name where contracts are stored
"""

import os
import json
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# CONFIG — replace placeholders with real values (or set as env vars)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://YOUR_PROJECT.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SERVICE_ROLE_KEY")
BUCKET_NAME = os.environ.get("SUPABASE_BUCKET", "contract-documents")
# ---------------------------------------------------------------------------


def fetch_file_bytes(file_path: str) -> bytes:
    """
    Download a file from Supabase Storage and return its raw bytes.

    Args:
        file_path: Path inside the bucket, e.g. "contracts/v1.pdf"

    Returns:
        Raw file bytes.
    """
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{file_path}"

    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if e.code == 404:
            raise FileNotFoundError(f"File not found in Supabase Storage: {file_path}") from e
        if e.code == 401:
            raise PermissionError("Supabase authentication failed — check SUPABASE_KEY") from e
        if e.code == 400:
            raise RuntimeError(
                f"Supabase Storage rejected the request (HTTP 400) — bucket name is likely wrong. "
                f"SUPABASE_BUCKET='{BUCKET_NAME}', path='{file_path}'. "
                f"Supabase says: {body}"
            ) from e
        raise RuntimeError(
            f"Supabase Storage returned HTTP {e.code} for {file_path}. Supabase says: {body}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Supabase at {SUPABASE_URL}: {e.reason}") from e


def save_analysis_result(
    contract_id: str,
    version_a_id: str,
    version_b_id: str,
    analysis: dict,
) -> None:
    """
    Persist a contract analysis result to the `contract_analyses` Supabase table.

    -- SQL: run once in your Supabase project to create the table:
    --
    -- CREATE TABLE contract_analyses (
    --   id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    --   contract_id    uuid        NOT NULL REFERENCES contracts(id),
    --   version_a_id   uuid        NOT NULL REFERENCES versions(id),
    --   version_b_id   uuid        NOT NULL REFERENCES versions(id),
    --   changes        jsonb       NOT NULL,
    --   overview       text        NOT NULL,
    --   consideration  jsonb       NOT NULL,
    --   gaps           jsonb       NOT NULL,
    --   created_at     timestamptz NOT NULL DEFAULT now()
    -- );

    Args:
        contract_id:   UUID of the parent contract.
        version_a_id:  UUID of Version A.
        version_b_id:  UUID of Version B.
        analysis:      Dict with keys changes, overview, consideration, gaps.
    """
    url = f"{SUPABASE_URL}/rest/v1/contract_analyses"
    payload = json.dumps({
        "contract_id":   contract_id,
        "version_a_id":  version_a_id,
        "version_b_id":  version_b_id,
        "changes":       analysis["changes"],
        "overview":      analysis["overview"],
        "consideration": analysis["consideration"],
        "gaps":          analysis["gaps"],
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            _ = response.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotImplementedError(
                "save_analysis_result: the `contract_analyses` table does not exist yet. "
                "Run the CREATE TABLE statement in the function docstring inside your Supabase project."
            ) from e
        if e.code == 401:
            raise PermissionError("Supabase authentication failed — check SUPABASE_KEY") from e
        raise RuntimeError(f"Supabase returned HTTP {e.code} writing analysis") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Supabase at {SUPABASE_URL}: {e.reason}") from e


def save_diff_result(result_key: str, diff_json: dict) -> None:
    """
    Persist the diff result to Supabase so the Lovable frontend can read it.

    TODO: Replace with your actual table name and column structure once
    you have access to Supabase. Options:
      - Insert into a `diffs` table (recommended)
      - Upload as a JSON file back to Storage

    Args:
        result_key: Unique identifier for this comparison job.
        diff_json:  The structured diff payload to store.
    """
    # PLACEHOLDER — implement once Supabase schema is defined
    # Example using supabase-py:
    #
    # from supabase import create_client
    # client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # client.table("YOUR_TABLE_NAME").insert({
    #     "id": result_key,
    #     "result": diff_json,
    # }).execute()
    raise NotImplementedError("save_diff_result: Supabase table not configured yet.")
