#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv export --frozen --no-dev --no-emit-project --format requirements-txt \
  --output-file src/backend/requirements.txt --quiet
cp src/backend/requirements.txt src/agents/event-guide/requirements.txt
