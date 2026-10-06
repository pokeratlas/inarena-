from __future__ import annotations

import argparse
import json
import sys

from .db import connect, database_backend, ensure_schema, schema_version
from .migration_runner import postgres_migration_status


def _status() -> dict:
    backend = database_backend()
    if backend == "postgresql":
        conn = connect()
        try:
            status = postgres_migration_status(conn)
            conn.rollback()
            return {
                "backend": backend,
                "current": status.current,
                "target": status.target,
                "pending": list(status.pending),
                "up_to_date": status.up_to_date,
            }
        finally:
            conn.close()

    current = schema_version()
    return {
        "backend": backend,
        "current": current,
        "target": current,
        "pending": [],
        "up_to_date": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="INARENA database migrations")
    parser.add_argument(
        "command",
        choices=("upgrade", "status", "check"),
        nargs="?",
        default="upgrade",
    )
    args = parser.parse_args()

    if args.command == "upgrade":
        ensure_schema()

    result = _status()
    print(json.dumps(result, separators=(",", ":")))
    if args.command == "check" and not result["up_to_date"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
