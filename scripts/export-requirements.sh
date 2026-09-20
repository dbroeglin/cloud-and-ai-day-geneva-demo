#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
temporary=$(mktemp src/backend/.requirements.XXXXXX)
trap 'rm -f -- "$temporary"' EXIT
uv export --frozen --no-dev --no-emit-project --no-header --format requirements-txt \
  --output-file "$temporary" --quiet
if ! cmp -s "$temporary" src/backend/requirements.txt; then
  chmod 644 "$temporary"
  mv "$temporary" src/backend/requirements.txt
fi
rm -f -- "$temporary"
if ! cmp -s src/backend/requirements.txt src/agents/event-guide/requirements.txt; then
  temporary=$(mktemp src/agents/event-guide/.requirements.XXXXXX)
  cp src/backend/requirements.txt "$temporary"
  chmod 644 "$temporary"
  mv "$temporary" src/agents/event-guide/requirements.txt
fi
if ! cmp -s src/agents/event-guide/telemetry.py src/backend/telemetry.py; then
  temporary=$(mktemp src/backend/.telemetry.XXXXXX)
  cp src/agents/event-guide/telemetry.py "$temporary"
  chmod 644 "$temporary"
  mv "$temporary" src/backend/telemetry.py
fi
