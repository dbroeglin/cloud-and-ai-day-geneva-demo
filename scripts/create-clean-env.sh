#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/create-clean-env.sh geneva2

Creates the Geneva Event Companion azd environment in East US 2 and configures
the required Foundry Bicep inputs. The environment name must follow:
geneva2
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

environment_name="${1:-}"
if [[ "$environment_name" != "geneva2" ]]; then
  usage >&2
  exit 2
fi

resource_group="rg-${environment_name}"
subscription_id="$(az account show --query id -o tsv)"
tenant_id="$(az account show --query tenantId -o tsv)"

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env new "$environment_name" \
  --subscription "$subscription_id" \
  --location eastus2
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AZURE_RESOURCE_GROUP "$resource_group"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AZURE_FOUNDRY_RESOURCE_GROUP "$resource_group"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AZURE_TENANT_ID "$tenant_id"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env config set \
  infra.parameters.foundryProjectName "$environment_name"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env config set infra.parameters.location eastus2
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env config set \
  infra.parameters.resourceGroupName "$resource_group"

echo "Configured clean azd environment: ${environment_name}"
