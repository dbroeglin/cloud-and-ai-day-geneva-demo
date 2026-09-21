# Geneva Event Companion - Azure Deployment Plan

Status: Cleanly recreated and verified - private storage and a new Foundry namespace
Updated: 2026-09-21
Source: `docs/spec.md`

## Current result

The original environment was fully deleted and both soft-deleted Foundry accounts
purged under explicit user approval. A new environment,
`geneva-companion-redeploy-eus2`, then provisioned in 5m10s and deployed in
6m39s. The real assistant API and mobile UI return a cited 13:27 answer,
unsupported questions are refused, and Table records survive a backend restart.
Three remote browser tests pass. The actual agent identity's three scoped roles
and fresh end-to-end telemetry are verified. `FRONTEND_URI` is persisted in
ignored azd state. See `docs/deploy.md` for exact current endpoints and evidence.
GitHub CI/PR previews remain unconfigured.

The authorization/recovery narrative below is chronological history, not a
claim that deleted resources still exist or that prior failures remain unresolved.
The earlier R2 resources were removed in the approved purge. The current clean
environment relies on no prior resource name, Foundry account override, or
provisioning output. `Microsoft.AlertsManagement` remains Registered; no causal
link to the earlier hosted-agent 404 has been established.

## Scope and authorization

Greenfield application using azd and Bicep. The user requested autonomous
Spec2Cloud execution; resolve routine choices with documented minimal defaults.
The full reset described below is explicitly authorized; unrelated destructive
changes and publication of a new public GitHub repository remain out of scope.
The previously authorized caller role grants remain in place.

Superseding approval, 2026-09-20: the user explicitly requested
`azd down --force --purge` and recreation of the whole
`geneva-companion-dev-eus2` environment. This authorizes permanent removal of
this environment's Azure resources/data, including both old and replacement
backends/environments. The repository, subscription-wide caller grants, and
registered networking feature remain. No unrelated resource group is in scope.
After azd refused teardown due to an empty ownership record and supported
refresh did not restore it, the user explicitly approved deletion of this exact
verified group and purge of its Foundry account through Azure CLI. This is the
approved equivalent fallback, not an ownership-state override.

Reset verification: the main group and both named managed environment groups
are absent. The approved deleted Foundry account was purged and no longer
appears in the soft-deleted list. Only this local azd environment was removed
and recreated through `azd env remove/new`; the tracked plan and repository
remain. Fresh state contains no old project endpoint, agent version, toolbox
endpoint, runtime identity list, or reuse-existing-project flag.

Clean-recreation proof: the real preflight confirms role/feature prerequisites;
the `--no-state` core preview contains creates only; all services package; all
Bicep entrypoints and 31 hook tests pass. The backend readiness hook now requires
a real managed-identity Table read in addition to health and MCP, so a healthy
HTTP process cannot hide a blocked data path.

Foundry readiness recovery: the recreated `geneva-companion` project reports
Succeeded in ARM but its skills and agent data APIs repeatedly return
ProjectNotFound, including after a supported reconciliation. The cause is not
confirmed. Select `geneva-companion-demo` in the same verified account as a
bounded namespace recovery; the reviewed preview creates only that project and
its connections, without deleting or replacing the working network/backend.
This is not a claim that the new data API is ready before publication succeeds.
The new project's skills API now returns successfully. Connection names are
prefixed with the project name because the service rejects updates to shared
names owned by the prior workspace. Compilation, 31 hook tests, and the
no-delete preview passed for the project-specific connection change.

The hosted endpoint nevertheless returned ProjectNotFound through both the
backend and the official CLI despite an active agent and correct endpoint
configuration. Reapplying the endpoint configuration did not resolve it.
The user explicitly approved a uniquely named Foundry account/project recovery,
preserving the working app, storage, network, registry, and monitoring.

Selected account: `cog-geneva-c4jyiykjqtot4-r2`; domain availability was verified.
Selected project: `geneva-agent-demo`. Model/version/SKU remain unchanged,
capacity 10; live quota is 30 used of 1000. An explicit account-name override
changes only the AI account namespace, not the shared resource naming token.
The old AI resources remain until the new endpoint is verified; no deletion or
security-policy bypass is part of this bounded recovery.
The domain/quota check, all Bicep entrypoints, 31 hook tests, and the Azure
preview pass. The preview creates the new AI account/project and connections,
retains the old AI resources, and contains no deletes or app/data replacement.

Earlier in the run, the user approved adding a VNet/private endpoint and a
VNet-integrated replacement backend to comply with the inherited Storage
network policy. Existing resources remain; cleanup requires separate approval.
See `docs/spec.md` section 14 and `docs/plan.md` section 8 for the frozen
migration boundary. Do not enable public Storage access or bypass the policy.

## Candidate architecture

Static Web Apps frontend; Container Apps Python API and public read-only MCP;
Table Storage; Copilot SDK Foundry hosted agent using Responses, Skills API, and
toolbox MCP; one ACR, one Application Insights, and one Log Analytics workspace.
The application also uses Foundry Evals with a versioned synthetic public-agenda
dataset as a post-deployment/pre-approval gate. No Search, embeddings, Cosmos,
or MAF. The approved amendment adds only the private connectivity required by
the inherited Storage policy.

## Placement

| Field | Value |
| --- | --- |
| Preferred location | francecentral |
| Validated deployment location | francecentral; September 21, 2026 live catalog/capacity/provider checks found `gpt-5.4-mini` GlobalStandard capacity 980 and required providers |
| Actual deployed location | Pending: requested `geneva` deployment |
| Model | gpt-5.4-mini |
| Model version / SKU / capacity | 2026-03-17 / GlobalStandard / 10 |
| Quota evidence | Limit 1000, used 30 before the approved R2 capacity-10 addition on 2026-09-20 |
| Resource group | rg-geneva |
| Environment | geneva |
| Variance | Pending deployment |

Do not persist `AZURE_LOCATION` or model deployment settings until the complete
placement gate passes. Let the maintained Foundry azd extension manage its
internal model environment representation from `azure.yaml`.

## Planning checklist

- [x] Specify complete and mandatory post-Specify policy applied.
- [x] Caller assignment gate passed after explicit grant authorization.
- [x] Maintained template selected and merge approach documented.
- [x] Resource group collision, service availability, quota, and preview checks.
- [x] Minimal SKU choices and cost estimate.
- [x] Service/API/environment/schema/identity/runtime contract frozen.
- [x] Plan finalized under autonomous Spec2Cloud approval.
- [x] Implementation and local verification.
- [x] Azure validation; mandatory workflow completed through proof and error resolution.
- [x] Deployment through deploy/azure-deploy and azd provision/deploy.
- [x] Actual endpoint, persistence, hosted agent, and telemetry checks.
- [ ] Separate GitHub remote/CI/PR-preview requirement.

## All validation checks pass

- [x] 1. AZD Installation - 1.34.1
- [x] 2. Schema Validation - installed azd/Foundry schemas and hook tests
- [x] 3. Environment Setup - geneva-companion-dev-eus2
- [x] 4. Authentication Check - approved shared Azure CLI authentication
- [x] 5. Subscription/Location Check - approved target, eastus2 placement
- [x] 6. Aspire Pre-Provisioning Checks - not an Aspire application
- [x] 7. Provision Preview - core layer creates only resources in the approved group
- [x] 8. Build Verification - Python, frontend, browser, and Bicep checks pass
- [x] 9. Docker Build Context Validation - service-local context and atomically exported requirements
- [x] 10. Package Validation - all four services package successfully
- [x] 11. Azure Policy Validation - inherited Storage Modify policy identified; private path approved
- [x] 12. Aspire Post-Provisioning Checks - not an Aspire application

## Role Assignment Verification

Status: Verified statically and against the actual R2 agent's live assignments.
Real Table, agent/model, and telemetry calls also pass.
Backend UAMI has Table Data Contributor at the storage account, Foundry User at
the AI account, Metrics Publisher at Insights, and AcrPull at the single
registry. Project identity has account Foundry access and registry pulls.
The actual acting agent identity receives account inference/Foundry roles
and Insights Metrics Publisher through the postdeploy Bicep layer. No caller
privileges are created by the application templates.
Entra blueprint principals are not Azure RBAC eligible; the live service rejected
them and current Microsoft Entra documentation explicitly excludes them. Grants
remain on the real agent identity, never on a substitute project/account identity.

Pre-deploy hardening moves the backend AcrPull grant into the core provisioning
layer, before the first container revision. Its deterministic name matches the
AVM revision module's grant, so reruns are idempotent rather than duplicate role
assignments. Re-preview and compilation are required after this timing change.
Both were rerun successfully, together with the 22 hook tests and application
packaging checks. The mandatory validation workflow was replayed and completed.

## Historical validation discoveries

The first preview rejected a root Foundry provider combined with named layers.
The provider is now declared on the `core` layer, not the root. Preview then
passed. Explicit `AZURE_FOUNDRY_RESOURCE_GROUP` now pins the same approved
resource group, preventing the extension's default `-foundry` suffix from
silently changing the target. The final preview contains creates only.

The first real provision reached a Foundry connection validation error:
AppInsights connections accept `ProjectManagedIdentity` or `ApiKey`, not the
generic `AAD` discriminator. The connection is corrected to
`ProjectManagedIdentity`, preserving keyless authentication. Some foundation
resources now exist; re-preview and revalidation precede an idempotent retry.
Re-compilation, 22 hook tests, and the retry preview passed. The preview has no
deletes. Bicep 0.42.1 emits BCP036 because its connection enum omits the value
explicitly required by the live service; this known metadata warning is retained
and documented rather than bypassed with an API key or an untyped cast.
The subsequent service check required
`metadata.ApplicationInsightsConnectionString`. The shared non-secret routing
configuration is now supplied there, with `ApiType: Azure`; authentication
remains project-managed identity and local ingestion authentication stays
disabled. This is not an API-key credential fallback.
The metadata-complete template again passed compilation, 22 hook tests, and
an idempotent Azure preview with no deletes; the validation workflow was
completed before the next attempt.

## 7. Initial Validation Proof

All results below were observed on 2026-09-20, not inferred from documentation.

| Command / check | Result |
| --- | --- |
| `uv sync --python 3.14` after dependency reconciliation | Resolved and locked |
| `uv run ruff check src/backend src/agents/event-guide tests` | Passed |
| `uv run pytest -q` | 24 passed; dependency deprecation warnings only |
| `npm --prefix src/frontend run build` | Passed |
| `npm --prefix src/frontend test` | 3 passed |
| `npm run test:e2e` from `src/frontend` | 2 passed, including 360px flow and ten-reader local latency threshold |
| Real bundled Copilot SDK session create/close | Passed; no model invoked |
| `bash scripts/validate-infra.sh` | 3 Bicep entrypoints compile; schema/resource checks and 22 hook tests pass |
| `python3 scripts/azure_hooks.py preflight` | Approved shared caller, effective roles, and live role definitions pass |
| `azd provision core --preview --no-prompt` | Passed after layer-provider correction and explicit approved resource-group pin |
| `azd package --no-prompt` | All four services packaged successfully |
| Subscription policy assignment/definition lookup | Three SQL/OSS-database protection initiatives; no planned SQL/OSS resource type, no preview policy denial |
| Static role review | Resource-scoped table, registry, model/Foundry, and telemetry grants match the code |

Every azd command used the inline `AZURE_DEV_USER_AGENT=microsoft_foundry_skill`
setting. No application resources were created during validation.

The final pre-deploy pass also confirmed the current azd release (1.34.1), the
current `microsoft.foundry` bundle, authenticated caller, LF entrypoints,
service-specific Docker context exclusions, and SDK cache placement under
`/tmp`. The resource group still did not exist immediately before provisioning.

## Implementation readiness

The dependency conflict is resolved with Projects SDK 2.7.0/OpenAI 3.16.1 and
Copilot SDK 1.0.13 (latest stable offered by the configured package feed).
Application, MCP, agent, monitoring, Bicep, and lifecycle hooks are implemented.
Local API, browser, SDK handshake, Responses protocol, infrastructure compilation,
and hook checks pass. See `docs/implementation.md` for exact evidence.

The identity preflight initially caught a different azd caller. With explicit
user approval, `auth.useAzCliAuth=true` now aligns azd with the already-approved
Azure CLI identity. The complete role gate passes. Azure validation, allocation,
and actual data-plane checks subsequently passed; current proof is recorded in
`docs/deploy.md`.

## Known limitations

No Git remote is configured. GitHub Actions, branch protection, and PR preview
verification need a repository target; do not claim they are active.

## Selected template, tiers, and interfaces

Use the maintained `microsoft-foundry/foundry-samples` Responses toolbox sample
identified in `docs/plan.md`, merged from a dedicated scaffold directory. Do not
overwrite the existing repository. Adapt its model loop to Copilot SDK.
All service names, environment variables, schemas, protocols, identities, and
runtime versions are frozen in `docs/plan.md` section 3.

SWA Free; ACA Consumption 0.25 vCPU/0.5 GiB (one warm, at most two replicas);
Standard LRS tables; ACR Basic; hosted sandbox 0.5 vCPU/1 GiB, five-minute idle
timeout (installed beta.12's validated minimum); one workspace and one Insights
instance. No Search SKU is applicable.
Code deployment uses Python 3.14 and Responses protocol 2.0.0.

Estimated seven-day planning allowance: USD 5-20 for modest demo usage, not a
hard cap or a full verified price quote. ACR Basic retail price was verified at
USD 0.1666/day. Tokens, active hosted sessions, telemetry, builds, and network
usage vary; see `docs/plan.md` section 4.

## Identity and hooks

Keep actual tenant/subscription identifiers in ignored local azd state. Use the
same explicitly authorized identity and subscription as the completed preflight.
Never persist access tokens, storage/model keys, or GitHub credentials.
The public agenda MCP has no private-data access and intentionally uses no-auth;
all privileged Azure access and agent-to-toolbox calls use managed identities.
SWA publishing may use a transient deployment token internally in azd; never
print, persist in this plan, commit, or reuse it as a runtime credential.

Preprovision must re-evaluate the complete caller role contract by stable IDs.
Postprovision orders governed skill publication, connection registration, then
toolbox publication. Deployment must make the backend/MCP ready before testing
agent discovery. Runtime inference/telemetry assignments must be reproducible
after the hosted identity is created. Validate before invoking Deploy.

## Assumptions

All fourteen assumptions in `docs/spec.md` section 12 are adopted. Additional
Plan defaults are recorded in `docs/plan.md` section 7: selected maintained
Responses sample, Python 3.14 code deployment, capacity 10, public agenda-only
MCP, Free SWA with an external API, no implicit repository publication, and a
small seven-day planning allowance rather than a budget ceiling.

Subscription-specific allocation is only proven when provisioning succeeds.
No Swiss/EU residency is asserted. A prebuilt artifact was not supplied, so the
reproducible source/azd tree is the delivery artifact.

## Historical private-connectivity validation

The amended network templates compile, 28 lifecycle-hook tests pass, and the
Azure core preview succeeds with no deletes. It preserves the old app/environment
and creates the approved replacement environment, VNet, and Table private endpoint.
The source explicitly declares Storage public access Disabled to match the
inherited management-group policy.

VNet: `10.42.0.0/24`; delegated ACA subnet: `10.42.0.0/27`; private endpoint
subnet: `10.42.0.32/28`. The Table private DNS zone is linked only to this VNet.
No peering, firewall, NAT gateway, policy exemption, or shared-key fallback.

Read-only live provider checks confirm Microsoft.Network and Microsoft.App
registration and East US 2 support for the selected network/environment APIs.
Private DNS is global. The original subscription-only policy enumeration missed
the management-group Modify policy; activity-log evidence is now included in
the validation, and the design complies with that policy.

Additional fixed networking estimate: USD 33.35 per 730-hour month, about
USD 7.68 for seven days, based on current retail inputs: private endpoint
0.01/hour, managed Standard load balancer 0.025/hour, two managed IPv4 addresses
0.005/hour each, and private DNS 0.50/zone-month. Data processing and DNS queries
are additional. Revised small-demo allowance is approximately USD 13-30 for
seven days plus retained-resource overlap; this is not a hard cap.

The user approved these networking additions. The old backend/environment remain
until a separate cleanup approval. Canonical output changes and the governed MCP
target are handled by an explicit, scope-bound migration record in ignored azd
state. The frontend origin remains unchanged.

Amendment proof, 2026-09-20: all templates compile; 28 hook tests and 25
application tests pass; frontend build and 3 component tests pass; 2 local browser
tests pass; all four services package; the private core preview has no deletes.
The full Azure validation workflow was replayed against this approved amendment.

## Historical networking capability recovery

The replacement environment reached Failed because the subscription lacked
`Microsoft.Network/AllowBringYourOwnPublicIpAddress`. The feature was
NotRegistered. The supported registration request returned Registered, and
Microsoft.Network was re-registered to propagate it. No security policy was
changed and no resource was deleted.

The preprovision hook now checks this exact feature state and refuses Pending,
Registering, or NotRegistered before another environment deployment. Retry
validation must confirm the failed environment can be reconciled without
deletion; any destructive recovery remains separately approval-gated.
Recovery proof: the updated hook's 29 tests pass, the real feature/identity gate
passes, and the core preview shows modification of the failed environment with
no deletes. The storage private endpoint remains Succeeded and Auto-Approved.

The environment retry subsequently reported Succeeded, but the replacement
Container App failed after 20m13s with `ContainerAppOperationError` and empty
details. It has no revisions. The environment exposes no static IP; its managed
resource group lists no public IPs/load balancers, and the networking detector
reports missing telemetry. These are suspicious observations, not a confirmed
root cause. The original app remains Succeeded. No destructive recovery is
authorized unless the user explicitly approves the exact failed replacement
resources; Storage, private endpoint/DNS, original app/environment, Foundry,
and frontend must be preserved.
