"""Minimal HTTP server for the agent. POST / with JSON { session_id, user_input }."""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Allow running as python -m agent.server or from project root
if __name__ == "__main__":
    sys.path.insert(0, sys.path[0] or ".")

from agent.main import handle


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/" and self.path != "":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            req = json.loads(body) if body else {}
        except Exception as e:
            self._send(400, {"error": str(e)})
            return
        session_id = req.get("session_id", "").strip()
        user_input = req.get("user_input", "").strip()
        if not session_id or not user_input:
            self._send(400, {"error": "session_id and user_input required"})
            return
        try:
            out = handle(session_id, user_input)
            self._send(200, out)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        if self.path in ("/", "", "/health"):
            self._send(200, {"status": "ok", "service": "rental-agent"})
            return
        self.send_error(404)

    def _send(self, code, obj):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def run(port=8000):
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Agent HTTP server on http://0.0.0.0:{port} (POST / with session_id, user_input)")
    server.serve_forever()


if __name__ == "__main__":
    from agent import config
    run(config.SERVER_PORT)
