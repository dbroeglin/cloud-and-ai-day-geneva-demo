# Deployment

Status: **Deployed baseline working, including the real event guide.**
Verified: 2026-09-20. GitHub workflow definitions are now versioned; live
workflow execution still requires the repository environments described below.

## Current endpoints and evidence

- Frontend: `https://salmon-forest-057e78a0f.2.azurestaticapps.net/`
- Backend: `https://api-private-c4jyiykjqtot4.bluegrass-7557b998.eastus2.azurecontainerapps.io/`
- Agent playground: `https://ai.azure.com/nextgen/r/G7oiry5hTTyV5q_aVUI80w,rg-geneva-companion-dev-eus2,,cog-geneva-c4jyiykjqtot4-r2,geneva-agent-demo/build/agents/event-guide/build?version=1`
- Responses endpoint: `https://cog-geneva-c4jyiykjqtot4-r2.services.ai.azure.com/api/projects/geneva-agent-demo/agents/event-guide/endpoint/protocols/openai/responses?api-version=v1`

The approved AI-only replacement uses account `cog-geneva-c4jyiykjqtot4-r2`
and project `geneva-agent-demo`. Its rollout exited successfully in 4m48s.
The hosted agent is active, the backend revision is Healthy/Provisioned, and
both use the new project endpoint. `FRONTEND_URI` is saved in local azd state.

| Live check | Observed result |
| --- | --- |
| UI -> API -> hosted Copilot SDK -> governed toolbox -> agenda | Real cited answer rendered in the mobile browser: demo starts at 13:27 on September 21, 2026, Europe/Zurich |
| Unsupported question | Explicit refusal, no citations or canned answer |
| Azure Tables | Question creation, duplicate-safe voting, private suggestion receipts, and idempotent retries passed |
| Backend restart | Question/vote and original suggestion receipt survived an actual revision restart |
| Remote Chromium suite | All three tests passed: real assistant/source navigation, 360px attendee flow, desktop agenda and warm ten-reader p95 below 1s |
| Official agent CLI and logs | Real cited response; runtime downloaded governed skill version 1 and called the R2 toolbox |
| Runtime identity | Actual instance has account-scoped Foundry User/OpenAI User and shared Insights Metrics Publisher; no blueprint grants |
| Fresh distributed trace | `9ba64ee2f5d535466ce6ed1c7441fc60`, starting 19:36:58 UTC on September 20, contains backend, hosted agent, Copilot model/tool, and Foundry spans |
| Subscription provider | `Microsoft.AlertsManagement` is Registered |

Observed assistant calls took roughly 20-40 seconds; the UI shows its waiting
state and the API retains its explicit 60-second deadline. These checks do not
establish capacity for 150 simultaneous AI conversations.

## Repeat deployment and verification

The selected environment is `geneva-companion-dev-eus2`, with the target and
resource choices recorded in `.azure/deployment-plan.md`. Exact tenant and
subscription identifiers remain in ignored local azd state.

The user explicitly approved `azd config set auth.useAzCliAuth true` after the
preflight found mismatched `az`/`azd` identities. Both now use the previously
approved Azure CLI principal; the complete caller role check passes.

Azure validation, core preview, packaging, policy review, and caller checks
passed before deployment. For future infrastructure changes, repeat the
validation gate and inspect the preview before invoking Deploy:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd up --no-prompt
```

The explicit ordered equivalent is `bash scripts/deploy.sh`: provision, deploy
backend, deploy the hosted agent, and deploy the frontend. Retain the approved
account override in the local azd environment; do not change shared naming
tokens to replace only AI resources. Service hooks gate
backend/MCP readiness, publish skills/toolbox, reconcile runtime identities
through Bicep, and rebuild frontend assets using the actual API origin.

```bash
uv run python scripts/smoke_cloud.py --restart-backend
PLAYWRIGHT_BASE_URL=https://salmon-forest-057e78a0f.2.azurestaticapps.net \
PLAYWRIGHT_API_BASE_URL=https://api-private-c4jyiykjqtot4.bluegrass-7557b998.eastus2.azurecontainerapps.io \
  npm --prefix src/frontend run test:e2e
```

Run these sequentially: restarting the backend during browser tests invalidates
their result. The smoke and attendee tests intentionally persist synthetic demo
submissions. The deployed browser suite invokes the real model.

## Recovery history and remaining boundaries

The initial deployment exposed AppInsights connection schema, build-context,
SDK-constructor, CORS, guardrail, and runtime-identity integration defects.
These were corrected and recorded in `docs/spec2cloud-issues.md`.

An inherited management-group policy disabled public Storage access. The
approved private endpoint, private DNS, and VNet-integrated backend now provide
working data access without keys or policy exemptions. An initial private
environment failed even after the required networking feature was registered;
its root cause was not established. The user approved full teardown/purge.
Native azd ownership recovery failed, so separately approved exact-group
deletion and Foundry purge were performed and verified before clean recreation.
The current private environment obtained real networking and working storage.

After recreation, the reused Foundry namespace returned `ProjectNotFound`.
A second project supported management data APIs but its hosted runtime still
returned the same 404. The user then approved the AI-only R2 namespace
replacement. It preserved the working app, storage, network, registry, and
monitoring, and now passes real assistant requests. The old broken AI resources
are retained; their deletion needs separate approval and may affect costs.

`Microsoft.AlertsManagement` was separately registered after the portal error.
Its relationship to the earlier agent 404 was not established.

The workflow definitions are versioned and CI checks are active. Branch
protection and real PR previews remain unverified until the repository
environments are configured. No repository settings were changed implicitly.
Sample agenda sessions remain labelled as samples; only the afternoon demo slot
is confirmed.
French switching, moderation, and Excel export remain deliberately absent.

The agent host reports Responses crash-resilience disabled. The baseline uses
bounded synchronous single-turn calls; this does not promise recovery of an
in-flight response after a hard agent crash. Durable attendee records are in
Azure Tables and were verified independently.

## GitHub Actions deployment

The repository contains three workflow surfaces:

- `checks.yml` runs the full local validation suite for pull requests and when
  called by the deployment workflow.
- `deploy.yml` reuses those checks, authenticates to Azure with GitHub OIDC,
  previews core infrastructure, then runs `scripts/deploy.sh` on `main`.
- `preview.yml` builds the frontend against the stable development API and
  creates or closes a Static Web Apps pull-request environment.

Create a protected GitHub environment named `azure-dev` with these values:

| Name | Kind | Purpose |
| --- | --- | --- |
| `AZURE_CLIENT_ID` | Secret | Microsoft Entra application/service-principal client ID used by OIDC |
| `AZURE_TENANT_ID` | Secret | Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Secret | Azure subscription ID |
| `AZURE_ENV_NAME` | Variable | azd environment name, normally `geneva-companion-dev-eus2` |
| `AZURE_LOCATION` | Variable | Frozen deployment region, `eastus2` |
| `AZURE_RESOURCE_GROUP` | Variable | Approved resource group |
| `AZURE_FOUNDRY_RESOURCE_GROUP` | Variable | Same approved resource group for the Foundry layer |
| `AZURE_BACKEND_NAME` | Variable | Deterministic backend resource name |
| `AZURE_AI_ACCOUNT_NAME_OVERRIDE` | Variable | Approved Foundry account override, when required |

Grant that application the same unconditioned provisioning roles required by
the preflight gate. The hook accepts either the existing interactive Azure
user or this OIDC service principal, but it still verifies the token tenant,
principal object ID, role definitions, role assignments, and registered
network capability before provisioning.

Create a protected `azure-preview` environment with:

| Name | Kind | Purpose |
| --- | --- | --- |
| `PREVIEW_API_BASE_URL` | Variable | Stable development backend HTTPS origin |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Secret | Deployment token for the existing Static Web App |

The preview workflow is intentionally frontend-only; it does not provision
Azure resources for each pull request.
