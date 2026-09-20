# Geneva Event Companion - Azure Deployment Plan

Status: Validated
Updated: 2026-09-20
Source: `docs/spec.md`

## Scope and authorization

Greenfield application using azd and Bicep. The user requested autonomous
Spec2Cloud execution; resolve routine choices with documented minimal defaults.
No destructive changes or publication of a new public GitHub repository are
authorized. Two explicitly requested caller role grants have been completed;
the corrected stable-ID assignment preflight passes.

## Candidate architecture

Static Web Apps frontend; Container Apps Python API and public read-only MCP;
Table Storage; Copilot SDK Foundry hosted agent using Responses, Skills API, and
toolbox MCP; one ACR, one Application Insights, and one Log Analytics workspace.
No Search, embeddings, Cosmos, private networking, MAF, or Foundry Evals.

## Placement

| Field | Value |
| --- | --- |
| Preferred location | eastus2 (candidate only) |
| Validated deployment location | eastus2; live catalog/quota/provider checks and current hosted-agent regional support |
| Actual deployed location | None; nothing provisioned |
| Model | gpt-5.4-mini |
| Model version / SKU / capacity | 2026-03-17 / GlobalStandard / 10 |
| Quota evidence | Limit 1000, used 20, available 980 on 2026-09-20 |
| Resource group | rg-geneva-companion-dev-eus2; `az group exists` returned false |
| Environment | geneva-companion-dev-eus2 |
| Variance | None; preferred and selected region match |

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
- [ ] Deployment through deploy/azure-deploy and `azd up`.
- [ ] Actual endpoint, persistence, hosted agent, and telemetry checks.

## All validation checks pass

- [x] 1. AZD Installation - 1.34.1
- [x] 2. Schema Validation - installed azd/Foundry schemas and hook tests
- [x] 3. Environment Setup - geneva-companion-dev-eus2
- [x] 4. Authentication Check - approved shared Azure CLI authentication
- [x] 5. Subscription/Location Check - approved target, eastus2 placement
- [x] 6. Aspire Pre-Provisioning Checks - not an Aspire application
- [x] 7. Provision Preview - core layer creates only resources in the approved group
- [x] 8. Build Verification - Python, frontend, browser, and Bicep checks pass
- [x] 9. Docker Build Context Validation - root context and exported requirements
- [x] 10. Package Validation - all four services package successfully
- [x] 11. Azure Policy Validation - assigned initiatives target SQL/OSS databases, not this app
- [x] 12. Aspire Post-Provisioning Checks - not an Aspire application

## Role Assignment Verification

Status: Verified statically; live role propagation remains a post-deploy check.
Backend UAMI has Table Data Contributor at the storage account, Foundry User at
the AI account, Metrics Publisher at Insights, and AcrPull at the single
registry. Project identity has account Foundry access and registry pulls.
Runtime instance/blueprint principals receive account inference/Foundry roles
and Insights Metrics Publisher through the postdeploy Bicep layer. No caller
privileges are created by the application templates.

Pre-deploy hardening moves the backend AcrPull grant into the core provisioning
layer, before the first container revision. Its deterministic name matches the
AVM revision module's grant, so reruns are idempotent rather than duplicate role
assignments. Re-preview and compilation are required after this timing change.
Both were rerun successfully, together with the 22 hook tests and application
packaging checks. The mandatory validation workflow was replayed and completed.

## Validation discoveries

The first preview rejected a root Foundry provider combined with named layers.
The provider is now declared on the `core` layer, not the root. Preview then
passed. Explicit `AZURE_FOUNDRY_RESOURCE_GROUP` now pins the same approved
resource group, preventing the extension's default `-foundry` suffix from
silently changing the target. The final preview contains creates only.

## 7. Validation Proof

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
Azure CLI identity. The complete role gate passes. Azure validation and actual
allocation/data-plane checks are still required before deployment is complete.

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
