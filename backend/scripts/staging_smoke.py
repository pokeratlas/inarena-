from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from websockets.sync.client import connect as ws_connect


def request(base: str, path: str, *, method: str = "GET", body=None, headers=None):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=payload,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else None


def websocket_url(base: str, path: str) -> str:
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}{path}"


def main() -> int:
    parser = argparse.ArgumentParser(description="INARENA staging smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--operator-key", required=True)
    args = parser.parse_args()

    status, body = request(args.base_url, "/health")
    assert status == 200 and body["status"] == "ok", (status, body)

    status, body = request(args.base_url, "/ready")
    assert status == 200 and body["status"] == "ready", (status, body)
    assert body["checks"]["database"] == "ok"

    status, _ = request(args.base_url, "/api/v1/auth/session")
    assert status == 401, status

    status, _ = request(
        args.base_url,
        "/api/v1/operator/tables",
        method="POST",
        body={"name": "Staging Smoke"},
        headers={"X-Operator-Key": "wrong-key"},
    )
    assert status == 401, status

    status, session = request(
        args.base_url,
        "/api/v1/operator/auth",
        method="POST",
        body={"scopes": []},
        headers={"X-Operator-Key": args.operator_key},
    )
    assert status == 200, (status, session)
    token = session["token"]
    assert token.startswith("ops_")

    operator_headers = {"X-Operator-Key": token}
    status, table = request(
        args.base_url,
        "/api/v1/operator/tables",
        method="POST",
        body={"name": "Staging Smoke"},
        headers=operator_headers,
    )
    assert status == 201, (status, table)
    table_id = table["id"]

    with ws_connect(
        websocket_url(args.base_url, f"/ws/tables/{table_id}"),
        open_timeout=10,
        origin=os.getenv(
            "INARENA_SMOKE_ORIGIN",
            "http://staging.local",
        ),
    ) as socket:
        message = json.loads(socket.recv(timeout=10))
        assert message["type"] == "table_snapshot", message
        assert message["data"]["id"] == table_id, message

    status, closed = request(
        args.base_url,
        f"/api/v1/operator/tables/{table_id}/close",
        method="POST",
        headers=operator_headers,
    )
    assert status == 200, (status, closed)
    assert closed["status"] == "closed", closed

    print("INARENA staging smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
