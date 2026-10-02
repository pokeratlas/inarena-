from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


def environment() -> str:
    return os.getenv("INARENA_ENV", "development").lower()


def _origin_env() -> str:
    return (
        os.getenv("INARENA_ALLOWED_ORIGINS")
        or os.getenv("INARENA_CORS_ORIGINS")
        or ""
    )


def allowed_origins() -> list[str]:
    raw = _origin_env()
    if raw.strip():
        return [
            value.strip().rstrip("/")
            for value in raw.split(",")
            if value.strip()
        ]
    if environment() in {"production", "staging"}:
        return []
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def cors_origins() -> list[str]:
    return allowed_origins()


def origin_allowed(origin: str | None) -> bool:
    if not origin:
        return environment() not in {"production", "staging"}
    normalized = origin.rstrip("/")
    origins = allowed_origins()
    return normalized in origins or (
        "*" in origins and environment() not in {"production", "staging"}
    )


def request_body_limit_bytes() -> int:
    raw = os.getenv("INARENA_MAX_REQUEST_BODY_BYTES", "1048576")
    try:
        return max(1024, min(int(raw), 10 * 1024 * 1024))
    except ValueError:
        return 1048576


def _limit(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def client_ip(scope: dict[str, Any], headers: dict[str, str] | None = None) -> str:
    headers = headers or {}
    if os.getenv("INARENA_TRUST_PROXY_HEADERS") == "1":
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    client = scope.get("client")
    if client:
        return str(client[0])
    return "unknown"


def rate_limit_identity(
    *,
    scope: dict[str, Any],
    headers: dict[str, str],
    session_id: str | None = None,
) -> str:
    raw = session_id or client_ip(scope, headers)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RateLimiter:
    def __init__(self) -> None:
        self._local: dict[tuple[str, str, int], int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._redis = None

    async def _redis_client(self):
        url = os.getenv("INARENA_REDIS_URL")
        if not url:
            return None
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as redis
        except ImportError:
            return None
        self._redis = redis.from_url(url, decode_responses=True)
        return self._redis

    async def _local_allow(
        self,
        category: str,
        identity: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int]:
        bucket = int(time.time()) // window
        key = (category, identity, bucket)
        async with self._lock:
            self._local[key] += 1
            count = self._local[key]
            if len(self._local) > 10_000:
                current = bucket
                self._local = defaultdict(
                    int,
                    {
                        k: v
                        for k, v in self._local.items()
                        if k[2] >= current - 1
                    },
                )
        retry_after = window - (int(time.time()) % window)
        return count <= limit, retry_after

    async def allow(
        self,
        category: str,
        identity: str,
        limit: int,
        window: int = 60,
    ) -> tuple[bool, int]:
        redis_client = await self._redis_client()
        if redis_client is not None:
            bucket = int(time.time()) // window
            key = f"inarena:ratelimit:{category}:{identity}:{bucket}"
            try:
                count = await redis_client.incr(key)
                if count == 1:
                    await redis_client.expire(key, window + 2)
                retry_after = window - (int(time.time()) % window)
                return int(count) <= limit, retry_after
            except Exception:
                pass
        return await self._local_allow(category, identity, limit, window)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None


rate_limiter = RateLimiter()


def rate_limit_for_category(category: str) -> int:
    if category == "auth":
        return _limit("INARENA_RATE_LIMIT_AUTH_PER_MINUTE", 30)
    if category == "operator":
        return _limit("INARENA_RATE_LIMIT_OPERATOR_PER_MINUTE", 60)
    if category == "player":
        return _limit("INARENA_RATE_LIMIT_PLAYER_PER_MINUTE", 180)
    if category == "websocket":
        return _limit("INARENA_RATE_LIMIT_WS_PER_MINUTE", 30)
    return 300


def classify_http_rate_limit(method: str, path: str) -> str | None:
    if path.startswith("/api/v1/operator"):
        return "operator"
    if path in {"/api/v1/auth/telegram", "/api/v1/auth/refresh"}:
        return "auth"
    if method in {"POST", "PUT", "PATCH", "DELETE"} and (
        path.startswith("/api/v1/tables")
        or path.startswith("/api/v1/tournaments")
    ):
        return "player"
    return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Cache-Control", "no-store")
        if environment() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next) -> Response:
        category = classify_http_rate_limit(request.method, request.url.path)
        if category is None:
            return await call_next(request)

        headers = {k.lower(): v for k, v in request.headers.items()}
        identity = rate_limit_identity(
            scope=request.scope,
            headers=headers,
            session_id=headers.get("x-session-id"),
        )
        allowed, retry_after = await rate_limiter.allow(
            category,
            identity,
            rate_limit_for_category(category),
        )
        if not allowed:
            request_id = getattr(request.state, "request_id", None)
            headers_out = {"Retry-After": str(retry_after)}
            if request_id:
                headers_out["X-Request-ID"] = request_id
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate limit exceeded",
                    "retry_after": retry_after,
                    "request_id": request_id,
                },
                headers=headers_out,
            )
        return await call_next(request)


class RequestBodyLimitMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return

        limit = request_body_limit_bytes()
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > limit:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > limit:
                await self._reject(scope, receive, send)
                return
            chunks.append(body)
            more = bool(message.get("more_body", False))

        body = b"".join(chunks)
        delivered = False

        async def replay_receive():
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)

    async def _reject(self, scope, receive, send) -> None:
        request_id = scope.get("state", {}).get("request_id")
        headers = {"X-Request-ID": request_id} if request_id else None
        response = JSONResponse(
            status_code=413,
            content={
                "detail": "request body too large",
                "request_id": request_id,
            },
            headers=headers,
        )
        await response(scope, receive, send)


def cors_configuration() -> dict[str, Any]:
    return {
        "allow_origins": allowed_origins(),
        "allow_credentials": False,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Content-Type",
            "X-Session-ID",
            "Idempotency-Key",
            "X-Operator-Key",
            "X-Operator-Session",
            "X-Request-ID",
        ],
        "expose_headers": ["X-Request-ID", "Retry-After"],
        "max_age": 600,
    }
