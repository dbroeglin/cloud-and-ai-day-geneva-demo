#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Run only after the parent workflow passes Azure validation.
# Explicit phases; the frontend predeploy hook also replaces any eagerly packaged bundle.
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy backend --no-prompt
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy event-guide --no-prompt
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy frontend --no-prompt
