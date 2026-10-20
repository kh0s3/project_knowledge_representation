"""Web access to the access layer. Run: python serve.py   then open http://127.0.0.1:8000/

  /                                  the web page (type a question, see the query and the answer)
  /api/ask?question=...              JSON: status, query, vars, rows (the query is run on the graph)
  /api/examples                      JSON: the example questions shown as buttons
Stop with Ctrl+C."""
import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import config
from access_layer import ask, load_examples, load_graph, Schema

SCHEMA = Schema.load()
PAGE = (config.HERE / "index.html").read_bytes()
_graph = None
_lock = threading.Lock()          # one question at a time: the model call and the cache file are not thread-safe


def get_graph():
    """Load the graph the first time a question needs to be run (it can take a while)."""
    global _graph
    if _graph is None:
        print("loading the graph (first question only)...")
        _graph = load_graph()
    return _graph


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        question = (qs.get("question") or [""])[0].strip()

        if url.path == "/health":
            return self._send(200, {"status": "ok"})

        if url.path == "/api/examples":
            return self._send(200, [e["question"] for e in load_examples()])

        if url.path == "/api/ask":
            if not question:
                return self._send(400, {"error": "missing ?question="})
            try:
                with _lock:
                    res = ask(question, g=get_graph(), schema=SCHEMA)
            except Exception as e:
                return self._send(500, {"error": str(e)})
            return self._send(200, res)

        if url.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")

        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")          # Docker sets HOST=0.0.0.0
    port = int(os.getenv("PORT", "8000"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))    # lets "docker stop" end it cleanly
    if os.getenv("PRELOAD") == "1":
        get_graph()
    print(f"open http://127.0.0.1:{port}/   (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
