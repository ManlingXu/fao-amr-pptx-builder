#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    "${PYTHON:-python3}" -m venv .venv
fi
.venv/bin/python -c 'import sys; sys.exit("Python 3.11+ is required to run PPT Builder") if sys.version_info < (3,11) else None'
if ! .venv/bin/python -c 'import fastapi, uvicorn, pptx, msal, pydantic_settings, multipart, xlsxwriter' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -e .
fi
exec .venv/bin/python scripts/serve_studio.py "$@"
