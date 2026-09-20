# Geneva Event Companion - Azure Deployment Plan

Status: Blocked - implementation dependency resolution failed
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
- [ ] Implementation and local verification.
- [ ] Azure validation; status becomes Ready for Validation only when prepared.
- [ ] Deployment through deploy/azure-deploy and `azd up`.
- [ ] Actual endpoint, persistence, hosted agent, and telemetry checks.

## Current implementation blocker

Scaffold generation and the merge succeeded; local azd settings were persisted
after the validated placement decision. `uv sync --python 3.14` then exited 1:
`azure-ai-projects==2.7.0` requires `openai>=3.0.0`, but the initial manifest
also specifies `openai<3`. No application lockfile or service code exists yet.
See `docs/implementation.md` for the exact partial state and unresolved
scaffold differences. Do not provision this unfinished template.

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
Standard LRS tables; ACR Basic; hosted sandbox 0.5 vCPU/1 GiB, two-minute idle
timeout; one workspace and one Insights instance. No Search SKU is applicable.
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
