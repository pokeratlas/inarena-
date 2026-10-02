from __future__ import annotations

from .db import database_backend, ensure_schema, schema_version


def main() -> None:
    ensure_schema()
    print(
        f"INARENA schema ready: backend={database_backend()} "
        f"version={schema_version()}"
    )


if __name__ == "__main__":
    main()
