# Deployment

Status: **Geneva2 deployed and verified, including the real event guide.**
Verified: 2026-09-21. GitHub CI and PR previews remain unconfigured.

## Current endpoints and evidence

- Environment / resource group: `geneva2` / `rg-geneva2`
- Frontend: `https://black-river-0cff3d10f.5.azurestaticapps.net/`
- Backend: `https://api-private-7ciez6535bjny.wittyglacier-75619f38.eastus2.azurecontainerapps.io/`
- Agent playground: `https://ai.azure.com/nextgen/r/G7oiry5hTTyV5q_aVUI80w,rg-geneva2,,cog-i4vfjub67nnxs,geneva2/build/agents/event-guide/build?version=1`
- Responses endpoint: `https://cog-i4vfjub67nnxs.services.ai.azure.com/api/projects/geneva2/agents/event-guide/endpoint/protocols/openai/responses?api-version=v1`

The current clean deployment uses account `cog-i4vfjub67nnxs` and project
`geneva2` in East US 2. Core provisioning completed in 19m14s; backend,
agent, and frontend deployment completed successfully. The hosted agent is
active at version 1, the backend revision is Active/Provisioned/Running, and
`FRONTEND_URI` is saved in local azd state.

| Live check | Observed result |
| --- | --- |
| UI -> API -> hosted Copilot SDK -> governed toolbox -> agenda | Real cited answer rendered in the mobile browser: demo starts at 13:27 on September 21, 2026, Europe/Zurich |
| Unsupported question | Explicit refusal, no citations or canned answer |
| Azure Tables | Question creation, duplicate-safe voting, private suggestion receipts, and idempotent retries passed |
| Backend restart | Question/vote and original suggestion receipt survived an actual revision restart |
| Remote Chromium suite | All three tests passed: real assistant/source navigation, 360px attendee flow, desktop agenda and warm ten-reader p95 below 1s |
| Official agent CLI and logs | Real cited response in 22.4s; runtime downloaded governed skill version 1 and called the governed toolbox |
| Runtime identity | Actual instance has account-scoped Foundry User/OpenAI User and shared Insights Metrics Publisher; no blueprint grants |
| Fresh distributed trace | `6fc5ffbbf9844d87b1dd8b178f00668c`, starting 07:38:15 UTC on September 21, contains backend, hosted agent, Copilot model/tool, Foundry, and agenda MCP spans |
| Subscription provider | `Microsoft.AlertsManagement` is Registered |

Observed assistant calls took roughly 20-40 seconds; the UI shows its waiting
state and the API retains its explicit 60-second deadline. These checks do not
establish capacity for 150 simultaneous AI conversations.

## Repeat deployment and verification

The selected environment is `geneva2`, with the target and resource choices
recorded in `.azure/deployment-plan.md`. Exact tenant and subscription
identifiers remain in ignored local azd state.

The user explicitly approved `azd config set auth.useAzCliAuth true` after the
preflight found mismatched `az`/`azd` identities. Both now use the previously
approved Azure CLI principal; the complete caller role check passes.

Azure validation, core preview, packaging, policy review, and caller checks
passed before deployment. For future infrastructure changes, repeat the
validation gate and inspect the preview before invoking Deploy:

```bash
bash scripts/create-clean-env.sh geneva-companion-<suffix>-eus2
python3 scripts/azure_hooks.py preflight
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd up --no-prompt
```

The explicit ordered equivalent is `bash scripts/deploy.sh`: provision, deploy
backend, deploy the hosted agent, and deploy the frontend. The bootstrap helper
sets the Bicep input configuration that the Foundry provider requires and does
not reuse a prior account override. Service hooks gate
backend/MCP readiness, publish skills/toolbox, reconcile runtime identities
through Bicep, and rebuild frontend assets using the actual API origin.

Before deploying moderation, register an Entra API application and configure
its tenant GUID, application/client GUID, and at least one event-team group or
object ID allowlist entry in the azd environment. Enable group claims in access
tokens when using group authorization. These identifiers are configuration, not
credentials; do not commit local environment files.

```bash
azd env set ENTRA_TENANT_ID '<tenant-guid>'
azd env set ENTRA_CLIENT_ID '<api-application-guid>'
azd env set ENTRA_MODERATOR_GROUP_IDS '<group-guid>[,<group-guid>...]'
# Or, use an object-ID allowlist:
azd env set ENTRA_MODERATOR_OBJECT_IDS '<object-guid>[,<object-guid>...]'
```

The moderation API fails closed until these values are configured. Operators
must acquire an Entra access token for this API; public attendee question,
approved-question, and voting routes do not require sign-in.

```bash
uv run python scripts/smoke_cloud.py --restart-backend
PLAYWRIGHT_BASE_URL=https://ashy-pond-088bda60f.4.azurestaticapps.net \
PLAYWRIGHT_API_BASE_URL=https://api-private-xbtaviuvufbqw.salmonsmoke-e9ff14ef.eastus2.azurecontainerapps.io \
  npm --prefix src/frontend run test:e2e
```

Run these sequentially: restarting the backend during browser tests invalidates
their result. The smoke and attendee tests intentionally persist synthetic demo
submissions. The deployed browser suite invokes the real model.

Before approving a future deployment, also run the synthetic Foundry evaluation
gate against the active backend:

```bash
uv run python scripts/run_foundry_evals.py \
  --backend-origin "$BACKEND_ORIGIN" \
  --report-path .local/foundry-evals/event-guide-v1.json
```

The report must show every deterministic metric at 100% and include a Foundry
evaluation/run ID. This evaluation has not yet been run against the `geneva2`
deployment as of September 21, 2026 because the Foundry eval run requires
explicit approval.

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
replacement, which verified the application path but not clean recreation.
On September 21, the user explicitly approved a full `azd down --purge --force`
test. The original teardown retried after DNS timeouts, the group and both
soft-deleted Foundry accounts were verified gone, and a new differently named
environment was created successfully. Two hidden prerequisites were fixed:
environment-derived resource-group validation and a Bicep output for the model
deployment name. The helper above makes the remaining required azd environment
configuration explicit and repeatable.

`Microsoft.AlertsManagement` was separately registered after the portal error.
Its relationship to the earlier agent 404 was not established.

No Git remote is configured: CI, branch protection, and real PR previews are
not active or verified. No repository was implicitly published. Sample agenda
sessions remain labelled as samples; only the afternoon demo slot is confirmed.
French switching, approval audit trails, and Excel export remain deliberately
absent.

The agent host reports Responses crash-resilience disabled. The baseline uses
bounded synchronous single-turn calls; this does not promise recovery of an
in-flight response after a hard agent crash. Durable attendee records are in
Azure Tables and were verified independently.
