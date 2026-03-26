import hashlib
import hmac
import html
import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlparse


def get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def load_mock_users() -> list[dict[str, str]]:
    raw = os.environ.get("AUTH_MOCK_USERS_JSON")
    if raw:
        return json.loads(raw)

    return [
        {
            "label": "Known user",
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
        },
        {
            "label": "Disabled user",
            "external_id": "22222222-2222-2222-2222-222222222222",
            "username": "disabled.user",
            "email": "disabled.user@example.test",
            "first_name": "Disabled",
            "last_name": "User",
        },
        {
            "label": "Unknown user",
            "external_id": "33333333-3333-3333-3333-333333333333",
            "username": "unknown.user",
            "email": "unknown.user@example.test",
            "first_name": "Unknown",
            "last_name": "User",
        },
    ]


def callback_signature(user: dict[str, str], secret: str, ts: str) -> str:
    payload = "\n".join(
        [
            user["external_id"],
            user["username"],
            user.get("email", ""),
            user.get("first_name", ""),
            user.get("last_name", ""),
            ts,
        ]
    )
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


class AuthMockHandler(BaseHTTPRequestHandler):
    server_version = "LSSAuthMock/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._write_text(HTTPStatus.OK, "ok")
            return

        if parsed.path == "/":
            self._write_text(
                HTTPStatus.OK,
                "LSS auth_mock is running. Open /login?return_to=http://localhost:8000/auth/callback/ or start from LSS.",
            )
            return

        if parsed.path == "/login":
            self._handle_login(parsed)
            return

        self._write_text(HTTPStatus.NOT_FOUND, "not found")

    def _handle_login(self, parsed) -> None:
        params = parse_qs(parsed.query)
        return_to = params.get("return_to", [""])[0]
        if not return_to:
            self._write_text(HTTPStatus.BAD_REQUEST, "missing return_to")
            return

        user_key = params.get("user", [""])[0]
        users = load_mock_users()
        if user_key:
            user = next((entry for entry in users if entry["external_id"] == user_key), None)
            if user is None:
                self._write_text(HTTPStatus.BAD_REQUEST, "unknown user")
                return
            self._redirect_to_callback(return_to, user)
            return

        self._write_login_page(return_to, users)

    def _redirect_to_callback(self, return_to: str, user: dict[str, str]) -> None:
        ts = str(int(time.time()))
        secret = get_env("AUTH_MOCK_SHARED_SECRET", "change-me")
        payload = {
            "external_id": user["external_id"],
            "username": user["username"],
            "email": user.get("email", ""),
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "ts": ts,
        }
        payload["sig"] = callback_signature(user, secret, ts)
        location = f"{return_to}?{urlencode(payload)}"
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.end_headers()

    def _write_login_page(self, return_to: str, users: list[dict[str, str]]) -> None:
        links = []
        for user in users:
            user_href = f"/login?return_to={quote(return_to, safe='')}&user={quote(user['external_id'], safe='')}"
            links.append(
                "<li>"
                f"<a href=\"{html.escape(user_href)}\">{html.escape(user['label'])}</a>"
                f" ({html.escape(user['username'])})"
                "</li>"
            )

        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LSS auth mock</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background: #f4f0ea;
      color: #1f2933;
      margin: 0;
      padding: 3rem 1.5rem;
    }}
    main {{
      max-width: 42rem;
      margin: 0 auto;
      background: #fffaf4;
      border: 1px solid #d8c7b5;
      border-radius: 12px;
      padding: 2rem;
      box-shadow: 0 10px 30px rgba(48, 36, 24, 0.08);
    }}
    h1 {{
      margin-top: 0;
    }}
    ul {{
      line-height: 1.8;
    }}
    a {{
      color: #0f766e;
      text-decoration: none;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <h1>LSS auth mock</h1>
    <p>Select a mock user to send back to Lyrics Slide Show.</p>
    <ul>
      {"".join(links)}
    </ul>
  </main>
</body>
</html>
"""
        self._write_html(HTTPStatus.OK, body)

    def _write_html(self, status: HTTPStatus, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _write_text(self, status: HTTPStatus, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    host = get_env("AUTH_MOCK_HOST", "0.0.0.0")
    port = int(get_env("AUTH_MOCK_PORT", "8001"))
    server = ThreadingHTTPServer((host, port), AuthMockHandler)
    print(f"auth_mock listening on http://{host}:{port}", flush=True)
    server.serve_forever()
