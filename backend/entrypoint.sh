#!/bin/sh
set -eu
python scripts/migrate.py
if [ "${SEED_DEMO:-false}" = true ]; then
  python scripts/seed_demo.py || echo 'Demo seed failed' >&2
fi
exec uvicorn src.app:app --host 0.0.0.0 --port 8000
