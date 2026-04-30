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
BUCKET_NAME = os.environ.get("SUPABASE_BUCKET", "YOUR_BUCKET_NAME")
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
        if e.code == 404:
            raise FileNotFoundError(f"File not found in Supabase Storage: {file_path}") from e
        if e.code == 401:
            raise PermissionError("Supabase authentication failed — check SUPABASE_KEY") from e
        raise RuntimeError(f"Supabase Storage returned HTTP {e.code} for {file_path}") from e
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
