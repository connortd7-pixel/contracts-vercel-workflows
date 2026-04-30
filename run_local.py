"""
Local dev server — serves api/compare.py on http://localhost:8000/api/compare

Usage:
    python run_local.py          # default port 8000
    python run_local.py 9000     # custom port

Loads .env automatically if python-dotenv is installed; otherwise set env vars
manually before running.

Example request:
    curl -X POST http://localhost:8000/api/compare \
         -H "Content-Type: application/json" \
         -d '{"file_a": "contracts/v1.pdf", "file_b": "contracts/v2.docx"}'
"""

import sys
import os
from http.server import HTTPServer

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env")
except ImportError:
    pass

# Make sure core/ is importable
sys.path.insert(0, os.path.dirname(__file__))

from api.compare import handler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), handler)
    print(f"Listening on http://localhost:{PORT}/api/compare")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
