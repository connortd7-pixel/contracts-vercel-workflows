from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.supabase_client import fetch_file_bytes
from core.parser import parse_file
from core.differ import compute_diff


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)
            file_a_path = payload["file_a"]  # e.g. "contracts/v1.pdf"
            file_b_path = payload["file_b"]  # e.g. "contracts/v2.docx"

            bytes_a = fetch_file_bytes(file_a_path)
            bytes_b = fetch_file_bytes(file_b_path)

            ext_a = file_a_path.rsplit(".", 1)[-1].lower()
            ext_b = file_b_path.rsplit(".", 1)[-1].lower()

            lines_a = parse_file(bytes_a, ext_a)
            lines_b = parse_file(bytes_b, ext_b)

            diff = compute_diff(lines_a, lines_b)

            result = {
                "status": "ok",
                "file_a": file_a_path,
                "file_b": file_b_path,
                "lines": diff,
            }

            self._respond(200, result)

        except KeyError as e:
            self._respond(400, {"error": f"Missing field: {e}"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default access logs; Vercel handles logging
