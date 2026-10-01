"""aKUl desktop app - compare the limits of several API keys at once.

Runs a tiny local HTTP server (bound to 127.0.0.1 on an ephemeral port) that
serves the comparison UI and a ``/api/check`` JSON endpoint, then points a
pywebview window at it. This mirrors the sibling PhraseToPlaylist desktop app.

Endpoints
---------
``GET  /``              the comparison UI
``GET  /healthz``       readiness probe used at startup
``POST /api/check``     body: ``{"text": "...", "provider": "auto"}`` ->
                        a full comparison payload built by ``comparison.py``
``GET  /api/providers`` the provider list + env var names, for the dropdown
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_NAME = "aKUl"
APP_SUBTITLE = "compare API key limits"

if getattr(sys, "frozen", False):
    _BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    HTML_FILE = os.path.join(_BASE, "index.html")
    PARENT_DIR = _BASE
else:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    HTML_FILE = os.path.join(_HERE, "index.html")
    PARENT_DIR = os.path.dirname(_HERE)

if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from keylimits import checker, providers  # noqa: E402
from keylimits.comparison import build_comparison, serialize_key  # noqa: E402

MAX_KEYS = 64
MAX_BODY = 1 << 20  # 1 MiB


def parse_keys(text: str):
    """One key per line; '#' comments and blank lines are ignored."""
    keys = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.append(line)
        if len(keys) >= MAX_KEYS:
            break
    return keys


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # silence stderr access logs
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        try:
            with open(HTML_FILE, "rb") as handle:
                body = handle.read()
        except OSError:
            body = b"<!doctype html><title>aKUl</title><p>UI file missing."
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send_html()
        elif path == "/healthz":
            self._send_json({"ok": True})
        elif path == "/api/providers":
            self._send_json(
                {
                    "providers": [
                        {"name": p.name, "label": p.label, "env_vars": list(p.env_vars)}
                        for p in providers.all_providers()
                    ]
                }
            )
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/check":
            self._send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._send_json({"error": "payload too large"}, 413)
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._send_json({"error": "invalid JSON body"}, 400)
            return

        keys = parse_keys(payload.get("text", ""))
        if not keys:
            self._send_json({"error": "Add at least one API key."}, 400)
            return

        provider = (payload.get("provider") or "auto").strip() or "auto"
        base_url = (payload.get("base_url") or "").strip() or None
        try:
            workers = max(1, min(16, int(payload.get("workers") or 5)))
        except (TypeError, ValueError):
            workers = 5
        try:
            timeout = max(1.0, min(120.0, float(payload.get("timeout") or 30)))
        except (TypeError, ValueError):
            timeout = 30.0

        try:
            results = checker.check_many(
                keys,
                provider,
                workers=workers,
                timeout=timeout,
                base_url=base_url,
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)
            return

        self._send_json(build_comparison([serialize_key(r) for r in results]))


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def wait_until_ready(port, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def main():
    server, port = start_server()
    if not wait_until_ready(port):
        raise SystemExit("Local server did not start.")

    import webview

    window = webview.create_window(
        APP_NAME,
        f"http://127.0.0.1:{port}/",
        width=1180,
        height=820,
        min_size=(900, 600),
        background_color="#0b1014",
        text_select=True,
    )
    try:
        webview.start()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()