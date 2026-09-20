#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
temporary="$(mktemp -d)"
trap 'rm -f "$temporary/main.json" "$temporary/backend.json" "$temporary/runtime-rbac.json"; rmdir "$temporary"' EXIT
az bicep build --file infra/main.bicep --outfile "$temporary/main.json"
az bicep build --file infra/backend.bicep --outfile "$temporary/backend.json"
az bicep build --file infra/runtime-rbac/main.bicep --outfile "$temporary/runtime-rbac.json"
python3 - "$temporary/main.json" <<'PY'
import json
import sys
from pathlib import Path

template = json.loads(Path(sys.argv[1]).read_text())
expected = [{
    "name": "gpt-5.4-mini",
    "model": {"format": "OpenAI", "name": "gpt-5.4-mini", "version": "2026-03-17"},
    "sku": {"name": "GlobalStandard", "capacity": 10},
}]
assert expected in template["variables"].values(), "Ejected template lost the frozen model"
parameters = json.loads(Path("infra/main.parameters.json").read_text())["parameters"]
assert parameters["includeAcr"]["value"] is True, "Backend needs the shared registry"
assert parameters["principalId"]["value"] == "", "Caller grants must remain disabled"
assert "deployments" not in parameters, "azure.yaml must remain the model source of truth"
print("PASS: compiled model contract, shared ACR, and disabled caller grants")
PY
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_azure_hooks.py'
bash -n scripts/deploy.sh scripts/validate-infra.sh
git --no-pager diff --check -- infra azure.yaml scripts
