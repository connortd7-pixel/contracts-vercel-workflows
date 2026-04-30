from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.supabase_client import fetch_file_bytes, save_analysis_result
from core.parser import parse_file
from core.analyzer import analyze_contracts


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)

            contract_id = payload["contract_id"]
            version_a_id = payload["version_a_id"]
            version_b_id = payload["version_b_id"]
            file_a_path = payload["file_a"]
            file_b_path = payload["file_b"]
            version_a_attribution = payload.get("version_a_attribution", "company")
            version_b_attribution = payload.get("version_b_attribution", "counterparty")

            bytes_a = fetch_file_bytes(file_a_path)
            bytes_b = fetch_file_bytes(file_b_path)

            ext_a = file_a_path.rsplit(".", 1)[-1].lower()
            ext_b = file_b_path.rsplit(".", 1)[-1].lower()

            text_a = "\n".join(parse_file(bytes_a, ext_a))
            text_b = "\n".join(parse_file(bytes_b, ext_b))

            analysis = analyze_contracts(
                text_a,
                text_b,
                version_a_attribution=version_a_attribution,
                version_b_attribution=version_b_attribution,
            )

            try:
                save_analysis_result(contract_id, version_a_id, version_b_id, analysis)
            except NotImplementedError:
                pass  # Table not configured yet; result is still returned

            self._respond(200, {
                "status": "ok",
                "contract_id": contract_id,
                "version_a_id": version_a_id,
                "version_b_id": version_b_id,
                "analysis": analysis,
            })

        except KeyError as e:
            self._respond(400, {"error": f"Missing field: {e}"})
        except (ValueError, json.JSONDecodeError) as e:
            self._respond(400, {"error": str(e)})
        except FileNotFoundError as e:
            self._respond(404, {"error": str(e)})
        except PermissionError as e:
            self._respond(403, {"error": str(e)})
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
        pass
