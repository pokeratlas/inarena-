#!/bin/sh
set -eu

python -m app.migrate upgrade
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
