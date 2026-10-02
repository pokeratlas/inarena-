from __future__ import annotations

import json
import logging
import os
import re
import sys
import uuid
from typing import Any


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def configure_logging() -> logging.Logger:
    level_name = (os.getenv("INARENA_LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("inarena")
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    for handler in logger.handlers:
        handler.setLevel(level)

    return logger


def resolve_request_id(value: str | None) -> str:
    if value and _REQUEST_ID_RE.fullmatch(value):
        return value
    return uuid.uuid4().hex


def structured_log(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    )


def release_metadata() -> dict[str, str]:
    release = (
        os.getenv("INARENA_RELEASE")
        or os.getenv("GITHUB_SHA")
        or os.getenv("VERCEL_GIT_COMMIT_SHA")
        or "development"
    )
    return {
        "release": release,
        "environment": os.getenv("INARENA_ENV", "development"),
    }
