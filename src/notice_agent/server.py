"""Small local web prototype with no external API dependency."""

from __future__ import annotations

import argparse
import json
import mimetypes
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .agent import CampusNoticeAgent

ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"


class Handler(BaseHTTPRequestHandler):
    server_version = "CampusNoticeAgent/1.0"
    agent = CampusNoticeAgent()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json({"status": "ok"})
            return
        if path == "/api/sample":
            self._json(
                {
                    "text": (
                        "【教务处】2026年下半年全国大学英语四、六级考试报名将于"
                        "11月20日17:00截止。请需要报名的本科生登录教务系统核对学籍信息"
                        "并完成缴费，逾期不再补报。"
                    )
                }
            )
            return
        if path == "/":
            path = "/index.html"
        candidate = (WEB_ROOT / path.lstrip("/")).resolve()
        if WEB_ROOT not in candidate.parents or not candidate.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/analyze":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"error": "无效的 Content-Length"}, status=400)
            return
        if length <= 0 or length > 64_000:
            self._json({"error": "请求为空或超过 64 KB"}, status=413)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(payload.get("text", ""))
            raw_date = payload.get("date")
            reference_date = date.fromisoformat(raw_date) if raw_date else date.today()
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._json({"error": "请求必须是 UTF-8 JSON，日期格式为 YYYY-MM-DD"}, 400)
            return
        result = self.agent.analyze(text, reference_date=reference_date)
        self._json(result.to_dict())

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        # Never log the request body: it may contain personal notification text.
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动校讯行动助手网页")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
