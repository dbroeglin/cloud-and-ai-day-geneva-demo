# Plan: Geneva Event Companion Baseline

Status: Baseline deployed and verified, including private storage and the R2 agent.
Updated: 2026-09-20. Requirements: `docs/spec.md`.

Build a React/Vite Static Web App, one small FastAPI Container App that also
serves a public agenda MCP endpoint, and a Copilot SDK Foundry hosted agent.
Use Azure Tables for durable event records. Reuse the maintained Foundry
Responses/toolbox scaffold, adapting its model loop to the explicitly requested
Copilot SDK. Preserve the deliberately absent live-demo features.

## 1. Discovery and placement

Initial read-only discovery confirmed (historical planning evidence):

- Azure CLI and azd are authenticated; the corrected caller assignment gate
  passes after the explicitly authorized Foundry role grants.
- `rg-geneva-companion-dev-eus2` does not exist.
- `eastus2` supports the Foundry account/project and Container Apps resource
  types in this subscription. The current hosted-agent regional documentation
  includes East US 2 and both Responses and code deployment.
- Live catalog: `gpt-5.4-mini`, version `2026-03-17`, GA, Responses supported,
  `GlobalStandard` SKU available; its catalog default capacity is 10.
- Live quota: `OpenAI.GlobalStandard.gpt-5.4-mini` limit 1000, used 20, available
  980. Choose capacity 10 initially, with explicit AI rate-limit errors rather
  than hiding overload. This is not capacity for 150 simultaneous AI chats.
- Foundry provider is registered. No agent-specific ARM preview registrations
  were returned. Skills/toolbox are preview data APIs enabled through their
  documented feature headers; installed CLI commands are present.
- No Search/Foundry IQ or embedding deployment is required by public JSON
  grounding, so Search SKU checks are not applicable.
- No Git remote exists. Main SWA deployment is feasible without one. CI and real
  PR-preview verification remain blocked until a repository target is supplied;
  do not create or publish a repository implicitly.

The joint planning placement gate passes for `eastus2`; actual allocation and
data-plane availability still require deployment checks. No alternative region
was needed or ranked. Preferred and selected location are the same.

## 2. Template decision

The four choices required by Plan were considered under autonomous execution:

| Choice | Decision |
| --- | --- |
| Accept catalog suggestion: `Azure-Samples/azd-ai-starter-basic` | Not selected: less specific than the live protocol/toolbox sample. |
| Pick another maintained template | Selected: `microsoft-foundry/foundry-samples`, `samples/python/hosted-agents/bring-your-own/responses/bring-your-own-toolbox/azure.yaml`. |
| Minimal `azd init --minimal` | Not selected: would rebuild Foundry conventions unnecessarily. |
| None / skip initialization | Not selected: loses maintained scaffold behavior. |

The live catalog's Copilot sample currently uses Invocations. Do not adopt that
protocol merely because of its framework label. Reuse its BYOK SDK patterns as
reference, but start from the supported Responses/toolbox manifest and replace
the handwritten model loop with Copilot SDK.

Scaffold in a dedicated session artifact directory, then merge into the existing
repository without overwriting documentation, instructions, or Git state.
Use `azd ai agent init` with the verified manifest, `--agent-name event-guide`,
`--protocol responses`, `--deploy-mode code`, `--runtime python_3_14`,
`--entry-point main.py`, explicit model/environment, and Bicep ejection.
Use `azd init` only if the installed extension's generated structure requires it.
All application provisioning must remain inside azd.

Preserve maintained Foundry Bicep/modules and add the smallest app layer using
AVM where compatible. Reuse one ACR, one workspace, and one Insights resource.
Do not instantiate Cosmos, Search, extra models, or redundant monitoring.

## 3. Frozen cross-component contract

| Contract | Frozen value | Producer -> consumers | Verification |
| --- | --- | --- | --- |
| Services | `frontend`, `backend`, `ai-project`, `event-guide` | azure.yaml -> azd/hooks/CI | Manifest and hook checks |
| Paths | `src/frontend`, `src/backend`, `src/agents/event-guide` | Repo -> builds | Build contexts |
| Frontend deployment | `language: js`, `host: staticwebapp`, `dist: dist` | Vite -> azd | Real SWA fetch |
| Backend | FastAPI/Uvicorn port 8000; public `/api/*`, public read-only `/mcp` | ACA -> browser/toolbox | HTTP and MCP tests |
| Agent | Hosted Responses protocol `2.0.0`, server port 8088, API `v1` | Foundry -> backend | Real Responses invocation |
| Hosted path | `{project}/agents/event-guide/endpoint/protocols/openai/responses?api-version=v1` | Foundry -> backend | Authenticated smoke |
| Model | `gpt-5.4-mini`, `2026-03-17`, `GlobalStandard`, capacity 10 | ai-project -> agent | Live catalog/quota and invoke |
| Token scope | `https://ai.azure.com/.default` | Azure Identity -> project/toolbox/model | Keyless smoke |
| Toolbox | `event-companion`; emitted `TOOLBOX_EVENT_COMPANION_MCP_ENDPOINT` | azd -> agent env mapping | MCP initialize/list |
| Toolbox versions | Follow promoted default; resolve at a new request/session, never construct an unverified alias | Foundry -> agent | Promotion/discovery test |
| Connection | `${AZURE_AI_PROJECT_NAME}-event-agenda`, RemoteTool MCP, anonymous public agenda only | Bicep/hook -> toolbox | Exact connection target |
| MCP tool | `get_event_agenda`; input `{session_id?: string}`; output `{sources: EventSource[]}` | backend -> bridge/agent | Discovery/schema test |
| Runtime skill | `event-guide`; local `skills/event-guide/SKILL.md`, remote governed version | azd -> runtime `/tmp` | Download/discovery test |
| Assistant response | `{answer: string, citations: [{source_id: string, title: string}], refused: boolean, request_id: string}` | agent/backend -> UI | Contract tests |
| Refusal | `I cannot answer that from the published event information.` | grounding validator -> UI | Empty/forged evidence tests |
| Errors | `{error: {code: string, message: string}}`; 400/404/409/422/429/502/503/504 by cause | API -> UI | Error-path tests |
| Responses metadata | Only string `request_id`; no secrets, internal objects, or raw suggestion text | backend -> host/OTel | Payload validation |
| Agent memory | Single-turn API initially; independent runtime session per call, no shared attendee history | backend -> agent | Isolation test |
| Versions | Python 3.14 hosted code; Node 24; Copilot SDK 1.0.13; Responses server 2.1.0; Projects SDK 2.7.0; OpenAI >=3,<4; FastAPI 0.141.1; Tables SDK 12.7.0; MCP SDK 2.2.0 | Official package indexes -> manifests/lockfiles | Installed API checks and lock validation |

Resolve all transitive and secondary dependencies into lockfiles during
implementation. Version changes required by actual compatibility tests must
update this contract and consumers together. Preview API use is explicit even
when its client package has a stable version.

Resume reconciliation: Projects SDK 2.7.0 requires OpenAI 3+, so the sample's
OpenAI <3 upper bound was removed. Public PyPI lists Copilot SDK 1.0.14, but the
configured package feed currently offers only up to stable 1.0.13. Use 1.0.13
and inspect its installed APIs rather than bypassing that feed or pretending
the latest public release was installed.

### Environment variables

| Variable | Type / required | Producer -> consumers |
| --- | --- | --- |
| `AZURE_ENV_NAME` | string, required, `geneva-companion-dev-eus2` | azd -> Bicep/hooks |
| `AZURE_SUBSCRIPTION_ID` | GUID, required, local only | authenticated context -> azd/preflight |
| `AZURE_TENANT_ID` | GUID, required, local only | authenticated context -> azd |
| `AZURE_LOCATION` | string, required, `eastus2` | selected placement -> Bicep |
| `AZURE_AI_ACCOUNT_NAME_OVERRIDE` | optional account name, set for the approved R2 recovery | local azd state -> Bicep; leaves shared app resource names unchanged |
| `AZURE_RESOURCE_GROUP` | string, required, `rg-geneva-companion-dev-eus2` | plan -> azd |
| `AZURE_FOUNDRY_RESOURCE_GROUP` | same approved group, required | explicit override -> Foundry layer; prevents implicit suffix drift |
| `AZURE_CLIENT_ID` | GUID in ACA, optional locally | backend UAMI -> DefaultAzureCredential |
| `AZURE_STORAGE_TABLE_ENDPOINT` | HTTPS URL, required in Azure | storage output -> backend |
| `EVENT_TABLE_NAME` | string, default `EventCompanion` | Bicep/config -> backend |
| `EVENT_NAMESPACE` | string, default `geneva-2026-dev` | environment -> storage partitions |
| `FRONTEND_ORIGIN` | HTTPS origin, required in Azure | SWA output -> API CORS |
| `FRONTEND_URI` | verified primary frontend URL | post-deploy discovery -> local azd state/handoff |
| `VITE_API_BASE_URL` | HTTPS base URL, required for deployed build | backend output -> frontend build |
| `FOUNDRY_PROJECT_ENDPOINT` | HTTPS URL, required | Foundry output -> backend/agent/hooks |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | string, `gpt-5.4-mini` | ai-project -> agent |
| `FOUNDRY_AGENT_NAME` | string, `event-guide` | config -> backend |
| `TOOLBOX_MCP_ENDPOINT` | HTTPS URL, required in agent | toolbox emitted endpoint -> agent |
| `FOUNDRY_SKILL_NAME` | string, `event-guide` | config -> agent |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | non-secret routing config, required in Azure | shared Insights -> backend/agent |
| `OTEL_SERVICE_NAME` | string, per component | service config -> telemetry |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | loopback URL in agent, not public | local relay -> CLI child |
| `ENABLE_SENSITIVE_DATA` | boolean, default false for attendee-facing deployment | config -> capture/redaction |
| `APP_ENV` | `local` or `azure`, required | startup config -> explicit local/managed storage choice |

Only fixture/test code may use an in-memory store; production must fail startup
on missing Azure storage configuration. `.env.example` contains placeholders,
not actual subscription or tenant identifiers. No GitHub PAT or model key.

### REST and persistence

| Endpoint | Input | Output |
| --- | --- | --- |
| `GET /api/health` | None | Service liveness, not a fabricated dependency-health claim |
| `GET /api/event` | None | Public event metadata and sessions |
| `GET /api/sessions/{id}/questions` | Bounded optional continuation | Questions ordered by UTC creation |
| `POST /api/sessions/{id}/questions` | `{text, idempotency_key}` | Persisted question |
| `PUT /api/questions/{id}/votes/{voter_id}` | Session ID context as query parameter | Authoritative vote count |
| `POST /api/suggestions` | `{title, description, idempotency_key}` | Receipt `{id, created_at}` |
| `POST /api/assistant` | `{message, request_id}` | Validated assistant response |

Question shape: `{id, session_id, text, votes, created_at}`.
Dates are ISO UTC strings. IDs/idempotency keys/voter IDs are validated UUIDs.
Partition by environment/event/session; use deterministic row IDs for idempotent
creates. Reject reused keys with different payloads as 409. Store each vote and
increment its question counter in one same-partition transaction using ETags;
retry bounded conflicts, not arbitrary storage errors. Suggestions use an
isolated partition and have no public read route.

MCP outputs only public versioned agenda sources. The anonymous MCP boundary is
deliberate: it exposes the same public data as `GET /api/event`, not Azure table
access. Agent-to-Foundry/toolbox, table access, model inference, image pulls, and
telemetry remain managed-identity authenticated. No custom Entra application or
private-data no-auth connection is introduced.

### Observability and package API checks

Use the mandatory reference `configure_otel()` and `_copilot_telemetry()` patterns
adapted to the installed package APIs. The agent's CLI child emits OTLP to a
loopback-only relay; the relay redacts content and exports with the agent's
managed credential into the same Insights resource. Direct in-process spans
and usage metrics also use Azure Monitor exporters. Do not point OTLP directly
at Application Insights or leave a public telemetry-ingestion endpoint.

Before implementing the SDK interaction, inspect installed signatures for
`CopilotClient`, `create_session`, `send_and_wait`, permissions, provider
configuration, events, and context-manager cleanup. Whitelist only discovered
agenda tools; deny built-in filesystem, shell, web, and GitHub operations.

## 4. Minimal Azure resources and estimated cost

SWA Free; ACA Consumption backend at 0.25 vCPU/0.5 GiB, minimum one/maximum two
replicas for demo responsiveness; Standard LRS tables; Basic ACR; Foundry account
and project; one 0.5 vCPU/1 GiB hosted-agent sandbox per active session with a
five-minute idle timeout (the installed beta.12 minimum); one shared
Log Analytics/Insights pair.

Planning allowance: approximately USD 5-20 for a small seven-day demo, not a
spending cap or guaranteed quote. It assumes modest API traffic, roughly 1000
short agent turns, small storage, and limited telemetry. Foundry tokens, active
per-session hosting, logs, build minutes, and network egress vary with usage.
Do not run an unrestricted public load test against the model.

Official regional retail query confirmed ACR Basic at USD 0.1666/day (about
USD 1.17 for seven days), plus cloud-build usage. SWA Free is USD 0. ACA and
Table costs use the current consumption pricing references; free grants and
existing subscription consumption affect the actual bill. The allowance is
an engineering estimate, not a verified hosted-agent price quote. Document
cleanup instructions; do not automatically delete resources.

## 5. Implementation sequence

Progress: steps 1-8 are complete for the deployed application baseline.
The initial dependency conflict is resolved; current runtime deviations and
the exact evidence are in `docs/implementation.md`. The user approved aligning
azd authentication with the existing Azure CLI identity; that preflight passes.
Azure validation and real deployment checks pass; the separate GitHub
PR-preview requirement remains blocked without a remote.

1. Merge maintained scaffold, reconcile Bicep/service paths, create dependency
   manifests/locks, and inspect the installed SDK. No provisioning yet.
2. Implement event fixture, typed API, durable Table transaction/idempotency
   behavior, error surfaces, and public MCP tool.
3. Implement the simple English frontend, question/vote flows, private suggestion
   receipt, and compact event-assistant panel.
4. Implement Copilot SDK agent, governed skill downloads, toolbox bridge,
   deterministic citation validation/refusal, and correlated telemetry.
5. Wire keyless resource roles and hooks: caller preflight; infrastructure;
   skill create/update; connection registration; toolbox create/update;
   backend/image deployment; hosted-agent deployment/runtime-role reconciliation.
   Ensure public MCP is healthy before agent discovery checks.
6. Add versioned meeting-to-issues instructions and CI checks without creating
   live issues or an unapproved GitHub repository.
7. Run local behavior, concurrency, malformed-input, privacy, grounding, and
   build/infra checks. Write implementation/verification notes. Invoke
   azure-validate before any deployment and stop at failed gates.
8. Invoke Deploy/azure-deploy and run `azd up`. Verify the real frontend/API,
   persisted submissions, hosted-agent grounding and telemetry. Main deployment
   success is distinct from the blocked PR-preview gate.

## 6. Verification checklist

- Frontend build/typecheck and user-flow tests.
- API validation, unknown session, storage failure, conflicting idempotency,
  duplicate/concurrent vote, bounded paging, and write-only suggestion tests.
- No translation toggle, moderation status/approval route, or export endpoint.
- Agent API/lifecycle compatibility, tool whitelist, real skill discovery,
  empty-evidence refusal, forged-citation rejection, and tool failure.
- Bicep compilation and Azure what-if/validation via the applicable skill.
- Deployed HTTP smoke and actual browser flow; never use a static page alone as
  proof that the API or agent works.
- Real restart persistence and one model-backed cited answer.
- Single correlated trace across API, agent, toolbox/MCP, and model; prompt/tool
  capture only after redaction and with no private suggestions.
- Real same-repository PR preview after a remote is explicitly configured.

## 7. Assumptions and unresolved external dependency

All fourteen resolved defaults in `docs/spec.md` section 12 apply. Additional
Plan defaults: choose the maintained Responses/toolbox sample over Invocations;
code deploy on Python 3.14; minimal catalogue model capacity 10; public
anonymous agenda-only MCP; SWA Free with direct cross-origin API; no implicit
repository creation; limited seven-day cost allowance, not a spending ceiling.

The absence of a GitHub remote blocks automated PR-preview verification, not
local builds or the primary Azure frontend deployment. Do not weaken or mark
FR-015 complete without that separate verification.

After the approved full reset, the reused Foundry project name remained absent
from the data plane despite ARM success. A second project's management data APIs
worked, but its hosted runtime still returned `ProjectNotFound`. The approved
AI-only replacement now uses `cog-geneva-c4jyiykjqtot4-r2` /
`geneva-agent-demo` and passes real agent calls. Connections are project-prefixed
to avoid ownership collisions. The account-name override preserved shared
storage, backend, network, registry, and monitoring names. Old AI resources
remain; cleanup requires separate approval.

## Sources

Live Azure CLI catalog, usage, resource-provider, and role-assignment queries;
installed azd CLI help and sample catalog; official PyPI package metadata;
the bounded SWA research agent's primary-source report.

- `https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents`
- `https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-code`
- `https://github.com/microsoft-foundry/foundry-samples`
- `https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-schema`
- `https://learn.microsoft.com/en-us/azure/static-web-apps/review-publish-pull-requests`
- `https://learn.microsoft.com/en-us/azure/static-web-apps/plans`
- `https://prices.azure.com/api/retail/prices`

## 8. Approved private-connectivity migration contract

This historical migration contract was followed by the separately approved
full reset. The clean environment now uses this private topology; pre-reset
backends/environments no longer exist. See `docs/deploy.md` for current state.

The user approved private connectivity after an inherited management-group
Modify policy forced Storage public access off. The policy remains enforced.
No resources are deleted by this amendment.

| Contract | Frozen value |
| --- | --- |
| Resource group / region | Existing approved group / eastus2 |
| Replacement backend | `api-private-${suffix}`, where suffix is the existing `uniqueString(resourceGroup().id)` |
| Replacement environment | `cae-private-${suffix}` |
| VNet | `vnet-${suffix}`, one isolated VNet; no peering or changes to shared networks |
| Subnets | Separate delegated ACA infrastructure and Table private-endpoint subnets |
| Private DNS | `privatelink.table.core.windows.net`, linked only to this VNet |
| Storage | Existing account/table; public network Disabled; shared keys disabled |
| Identities / registry / monitoring | Reuse the current backend UAMI, Basic ACR, Insights, and workspace |
| Public application surface | SWA URL unchanged; replacement backend stays HTTPS/public for browser and public-agenda MCP calls |
| Changed outputs | Same canonical `AZURE_BACKEND_NAME`, `AZURE_CONTAINER_ENVIRONMENT_NAME`, `BACKEND_ORIGIN`, `VITE_API_BASE_URL`, now pointing to the replacement |
| MCP migration | Preserve toolbox history; update only the owned agenda target and promote a verified new version |
| Old resources | Retained until verified replacement; separate deletion approval required |

Implementation must validate current ACA subnet/delegation requirements and
networking costs before provisioning. Azure validation and real storage/browser
tests must run again. Subscription-only policy checks were insufficient; inspect
the inherited management-group policies as part of the amended validation.
