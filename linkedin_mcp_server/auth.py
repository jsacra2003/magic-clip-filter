"""LinkedIn OAuth 2.0 Authorization Code Flow.

Run once to obtain and save your access token:
    uv run python -m linkedin_mcp_server.auth

Prerequisites in .env:
    LINKEDIN_CLIENT_ID
    LINKEDIN_CLIENT_SECRET
    LINKEDIN_REDIRECT_URI  (default: http://localhost:8080/callback — must match your LinkedIn App settings)
"""
import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_SCOPES = "openid profile email w_member_social"
_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback")

_auth_code: str | None = None
_done = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>Authentication successful! You can close this tab.</h2>")
        _done.set()

    def log_message(self, *args):
        pass


def run():
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise SystemExit(
            "ERROR: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env\n"
            "Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps"
        )

    state = secrets.token_urlsafe(16)
    auth_url = _AUTH_URL + "?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _REDIRECT_URI,
        "state": state,
        "scope": _SCOPES,
    })

    port = int(urllib.parse.urlparse(_REDIRECT_URI).port or 8080)
    server = http.server.HTTPServer(("localhost", port), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    print("\nOpening browser for LinkedIn login...")
    print(f"If it doesn't open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    _done.wait(timeout=120)
    server.shutdown()

    if not _auth_code:
        raise SystemExit("Authentication timed out or was cancelled.")

    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "redirect_uri": _REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    access_token = data.get("access_token")
    if not access_token:
        raise SystemExit(f"Failed to obtain access token: {data}")

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    set_key(env_path, "LINKEDIN_ACCESS_TOKEN", access_token)
    expires_days = data.get("expires_in", 0) // 86400
    print(f"✅ Access token saved to .env (valid for ~{expires_days} days)")


if __name__ == "__main__":
    run()
