from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


_logger = logging.getLogger("inarena.http")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def configure_logging() -> None:
    level_name = os.getenv("INARENA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level)
    _logger.setLevel(level)


def release_metadata() -> dict[str, str]:
    return {
        "release": os.getenv("INARENA_RELEASE", os.getenv("GIT_SHA", "unknown")),
        "environment": os.getenv("INARENA_ENV", "development"),
    }


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id")
    if supplied and _SAFE_REQUEST_ID.fullmatch(supplied):
        return supplied
    return uuid.uuid4().hex


def log_http_event(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    payload: dict[str, Any] = {
        "event": "http_request",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status": status_code,
        "duration_ms": round(duration_ms, 2),
        **release_metadata(),
    }
    _logger.info(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            log_http_event(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            raise

        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - started) * 1000
        log_http_event(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        return response
