# Spec2Cloud issues: Cloud and AI Day Geneva companion

Run date: 2026-09-20. Demo date confirmed by the supplied runbook: 2026-09-21.

## Outcome

**Specify, Plan, Implement, and deployed baseline verification complete.**
The deployment was subsequently fully purged and recreated under a different
environment/account/project name; the live app and event guide still work.
Current endpoints and evidence are in `docs/deploy.md`. CI/PR previews remain
unconfigured without a Git remote. The earlier failures below are retained as
chronological evidence, not current blockers.

The caller RBAC assignment gate remains resolved.
The initial attempts were blocked before Specify. After the user's explicit
"run those commands" authorization at 14:16 CEST on 2026-09-20, both Foundry
role assignments in the handoff were created at the specified subscription
scope. A fresh inherited/group-derived assignment query confirmed their stable
role IDs alongside Owner, satisfying all four prerequisite capabilities.
Foundry data-plane access has now been exercised with the R2 agent identity,
governed skills/toolbox, and real inference. No GitHub issues or repository
were created.

### Initial blocked attempt

Resume attempt on 2026-09-20 after the user's 14:14 CEST "go": queried the
signed-in user and inherited/group-derived assignments again, this time matching
the prerequisite role IDs directly. Assignments were unchanged. Resource
creation and role-assignment checks passed, but both installed-policy Foundry
role checks remained missing. Verdict: **BLOCKED**, exit code 2. No subsequent
stage or permission-changing command was started.

The installed `spec2cloud` and `agentic-loop` skills were invoked. The latter
requires this permission gate before step 1, so its stop condition takes
precedence over continuing the four-stage pipeline. The Foundry skill was also
invoked to diagnose the prerequisite-role discrepancy.

## Stage outputs and blockers

| Stage | Status | Output / issue |
| --- | --- | --- |
| Source intake and preflight | Assignment gate passed after explicit authorization | Runbook requirements retrieved through authenticated M365. Initial Foundry role gaps were resolved by the two user-authorized grants. A fresh stable-ID check passed; stock-checker defects below remain unfixed. |
| Specify | Complete | `docs/spec.md` defines the baseline/demo boundary, fourteen explicit defaults, and Agentic Loop contracts. The loaded policy was applied immediately after generation and before Plan. Commit `bed502a`. |
| Plan | Complete | `docs/plan.md` and `.azure/deployment-plan.md` contain verified eastus2 placement, model quota/SKU, minimal tiers, maintained template choice, and frozen interfaces. Commit `89173b1`. |
| Implement / Verify | Complete | Baseline committed as `95cb171`; later live fixes included. Current checks: 25 Python tests, 3 UI tests, 3 deployed browser tests, real SDK handshake, 3 Bicep entrypoints, and 31 hook tests pass. |
| Deploy | Baseline complete | Approved reset and AI-only R2 replacement completed. Private Table persistence/restart, real cited answer/refusal, remote UI, instance RBAC, and fresh correlated telemetry passed. No CI/PR-preview claim. |
| Issue analysis | Updated through final R2 verification | Current conversation and available same-session history were analyzed; historical success before teardown was not reused as evidence for the final deployment. |

## Permission evidence and handoff

This was treated as a greenfield deployment into the active Azure CLI
subscription, using the signed-in user. No existing resource group, Foundry
account, or project was selected.

Effective assignments were queried with both `--include-inherited` and
`--include-groups`. Observed role names:

- Owner
- User Access Administrator
- Azure AI Developer
- Cognitive Services Contributor
- Cognitive Services Data Reader
- Cognitive Services OpenAI Contributor
- Cognitive Services Content Understanding Contributor

Owner satisfies the control-plane creation and role-assignment prerequisites.
The installed policy additionally requires these two named roles, neither of
which was present under its old or current name during the initial attempts.
Both are now assigned following the explicit user authorization:

| Principal | Greenfield scope | Current role | Stable role ID |
| --- | --- | --- | --- |
| Signed-in deploying user | Active subscription | Foundry Account Owner | `e47c6f54-e4a2-4754-9501-8e0985b135e1` |
| Signed-in deploying user | Active subscription | Foundry Project Manager | `eadc314b-1a2d-4efa-be10-5d325db5065e` |

The full local handoff, containing the resolved principal, subscription scope,
and ready-to-run owner commands, is saved as
`files/rbac-preflight-handoff.txt` in this Copilot session's artifact directory.
Identity and subscription identifiers are intentionally omitted from this
repository report.

**Important distinction:** the account-owner requirement is a named-role
requirement of the installed policy, not an additional management capability
missing from Azure Owner. Live role definitions show that Foundry Account Owner
has **no data actions**. Foundry Project Manager supplies project data actions;
Account Owner alone cannot replace it. The original blocked attempts did not
self-grant privileges; the later grants executed the user's explicit request.

## Agentic Loop skill defects

These findings are an upstream issue draft. Installed skill files were not
modified.

### 1. Greenfield check can report a false PASS

In `references/check_rbac_preflight.py`, `build_scopes()` only includes account
and project checks when their IDs are supplied (lines 186-216). The requirement
loop skips other scope kinds (lines 299-301). Consequently, the documented
greenfield invocation checks only two control-plane requirements:

```text
RBAC pre-flight: PASS -- 2 required role assignments satisfied.
```

That output was reproduced against the active subscription after the complete
policy check had already failed. It was not accepted as permission to proceed.
To evaluate the written greenfield contract without changing the skill, this run
used its existing assignment-resolution and comparison functions and evaluated
the Foundry prerequisite rows against inherited subscription assignments too.
That read-only check returned `BLOCKED`, exit code 2, with both missing roles.

Proposed upstream fix: evaluate all greenfield prerequisites at the inheritance
scope before resource creation; evaluate concrete scopes for brownfield runs.
Keep the same complete-gap report and fail-closed behavior.

### 2. Display-name matching breaks after the Foundry role rename

The requirement and equivalence tables use `Azure AI Account Owner` and
`Azure AI Project Manager` (lines 85-107); assignment normalization retains role
names rather than stable role IDs (lines 219 onward).

Azure returned no role definitions for those old names. The current names are
Foundry Account Owner and Foundry Project Manager; the role IDs are unchanged.
Live Azure role-definition queries confirmed the IDs in the handoff above.

Proposed upstream fix: match stable role-definition IDs, resolve current display
names for reports, and emit remediation commands using IDs.

### 3. Account Owner is not equivalent to Project Manager

The equivalence table at line 107 treats Account Owner as satisfying Project
Manager. The written contract also claims Account Owner has data actions.
Both conflict with the queried role definitions:

| Role | Observed data actions |
| --- | --- |
| Foundry Account Owner | Empty |
| Foundry Project Manager | `Microsoft.CognitiveServices/*`, with explicit exclusions |
| Foundry Owner | `Microsoft.CognitiveServices/*`, with an explicit exclusion |

Proposed upstream fix: distinguish management actions from data actions, remove
the unsafe equivalence, and evaluate combinations of effective permissions.
Avoid requesting redundant Account Owner grants when an existing Owner already
covers management capabilities. Any accepted replacement must preserve the
required project data actions, exclusions, scope, and assignment conditions.

### Proposed regression coverage

- Owner alone must not pass the full greenfield Foundry prerequisite gate.
- Renamed roles with unchanged IDs must match identically.
- Account Owner alone must not satisfy project data-plane access.
- Effective inherited and group-derived assignments must count.
- Valid control-plane plus project data-plane coverage must pass.
- Authorization/query failures must return ERROR, never PASS.

Authoritative references consulted:

- Live `az role definition list` and `az role assignment list` results.
- Installed `microsoft-foundry/rbac/rbac.md`.
- Microsoft Learn, "Role-based access control for Microsoft Foundry":
  `https://learn.microsoft.com/en-us/azure/foundry/concepts/rbac-foundry`.

## Intake evidence preserved for the next attempt

The authenticated M365 response identified the source as
"Cloud and AI Day Geneva - Demo Plan - Meeting to Pull Request".
Its baseline requirements, distinct from live-demo changes, are:

- A deliberately small single-page event companion.
- Sessions from JSON, arranged by room and time.
- A question box with immediately visible submissions.
- A feature-suggestion form with durable persistence behind an API.
- Azure Static Web Apps hosting and per-pull-request previews.
- French-language switching, the moderation queue/approval trace, and Excel
  export must remain absent from the baseline: those are demo changes.

The user's explicit GitHub Copilot SDK and Agentic Loop requirements extend the
runbook, which does not itself specify that SDK. The eventual design must retain
the baseline/demo boundary while applying the mandated Foundry hosted agent,
Responses API, Skills API, toolbox MCP, keyless identity, and observability
contracts. No design reconciliation was attempted after the failed gate.

Do not commit the source runbook, live meeting transcript, private source links,
or raw audience submissions. Keep the future `meeting/` transcript folder
git-ignored.

## Tooling and orchestration issues

| Observation | Recovery / future improvement |
| --- | --- |
| Direct web opening of the SharePoint link returned no usable content. | Authenticated M365 retrieval succeeded. Prefer authenticated retrieval for private runbooks. |
| M365 returned an empty convenience `reply` and the useful response inside a large `rawResponse` payload. | Decoded the nested JSON and read assistant message text. The initial strict JSON parser failed on a tool-output suffix; `JSONDecoder.raw_decode` recovered the response. |
| Printing the full decoded M365 response caused another oversized tool result. | Extracted only message text rather than response metadata and duplicate payloads. |
| The Foundry dependency script was initially invoked relative to the repository, where it does not exist (exit 127). | Re-ran from the installed skill root. It succeeded and reported azd and the Foundry extension ready. Skill runners should resolve script paths against the skill base directory. |
| Cloud and local session-history queries returned no indexed turns for this active session. | Analyzed the current conversation and its actual tool outcomes instead; did not invent history or attribute failures to unexecuted stages. |
| Stock greenfield preflight returned PASS while the written policy check returned BLOCKED. | Preserved BLOCKED, investigated read-only, and documented the mismatch instead of proceeding or patching third-party skill files. |
| User-scoped Azure skills have no GitHub source/version metadata. | `gh skill update --dry-run` reports them as untracked even while ending with "All skills are up to date." Record freshness as unknown and verify examples against live CLI/API behavior. |
| MCP authoring companion was missing. | Upstream preview succeeded; installed `python-mcp-server-generator` at source commit `4f4796f0bf30e105700f97ed8408c12b6aa95e06` under the unattended install policy. |
| Foundry catalog's Copilot sample uses Invocations, while policy requires Responses by default. | Selected the maintained framework-neutral Responses/toolbox sample and planned to replace its handwritten model loop with Copilot SDK. Do not switch protocols solely to match a framework label. |
| The older deployment-plan template says not to commit it. | Applied the explicit Agentic Loop durable-artifact override, keeping the sanitized plan tracked and real azd environment values ignored. |
| The model reference suggests setting internal `AI_PROJECT_DEPLOYMENTS` directly. | Followed the maintained Foundry guidance instead: model deployments belong in `azure.yaml`, with internal encoding owned by the extension. |
| `azd ai agent init` created a nested `event-guide` folder and ignored shell subscription/location values for the generated azd environment. | Read its actual output, merged from that exact directory, then persisted target settings using `azd env set`, starting with resource group. No provisioning happened with missing settings. |
| `--agent-name event-guide` changed agent identity but not the sample service key or source path. | Recorded the drift for explicit reconciliation before implementation. |
| Generated ACR defaults conflict with the minimum viable plan. | `includeAcr` is false and its module uses Premium. Record the required Basic registry/backend wiring; do not claim the raw scaffold matches the final architecture. |
| Current Projects SDK and sample OpenAI constraint are incompatible. | Blocking resolver failure described below. This run introduced the conflicting combination; the source sample uses an older compatible Projects lock. |
| No Git remote exists. | Main SWA deployment remains technically possible; CI and actual PR-preview verification are explicitly incomplete. No repository was created or published. |

## Implement blocker: dependency compatibility

The initial manifest pins `azure-ai-projects==2.7.0` (current PyPI release)
but also carries `openai<3` from the selected sample's `requirements.in`.
The sample lock uses Projects SDK 2.4.0; updating one side of that compatibility
pair without rechecking the other introduced the conflict.

Observed command: `uv sync --python 3.14`.
Observed result: exit code 1, no solution because Projects 2.7.0 requires
OpenAI >=3.0.0. Python 3.14.4 was obtained and `.venv` created, but application
dependencies were not installed and no `uv.lock` was produced.

Independent official package metadata confirms:

- `azure-ai-projects==2.7.0` requires `openai>=3.0.0`.
- `azure-ai-agentserver-responses==2.1.0` requires
  `azure-ai-agentserver-core>=2.1.0,<2.2.0`.
- The core package does not declare an OpenAI dependency.

Required next investigation: align the manifest with a compatible current
SDK/OpenAI set and inspect installed client/response APIs, including the
sample's HTTPX compatibility warning. Do not silently downgrade a frozen
version or bypass the dependency gate. The explicit stage-failure pause rule
was followed; source implementation and deployment did not proceed.

Plugin improvement: resolve the entire runtime dependency graph before
declaring package versions frozen. Sample upper bounds and current package
metadata must be reconciled together; checking only individual latest versions
is insufficient.

### Resolution and additional implementation findings

OpenAI 3.16.1 and Projects SDK 2.7.0 now resolve together. The configured package
feed lacks Copilot SDK 1.0.14 even though public PyPI lists it. Refreshing the
resolver cache did not change this; inspecting the actual configured index
showed 1.0.13 as its newest stable release. The implementation uses 1.0.13 and
records the exception rather than bypassing the feed.

Installed API inspection found further differences from sample guidance:

- MCP SDK 2.2 renamed `FastMCP` to `MCPServer`, uses `httpx2` in its client
  transport, and exposes tool schemas as `input_schema`.
- Copilot SDK session creation is keyword-only; prompt sending accepts a string;
  the response is `SessionEvent | None` with `data.content`; client and session
  support async context managers. A real bundled-runtime handshake passed.
- Responses server 2.1 can configure its own exporters and defaults to sensitive
  content capture. It now uses the app's explicit keyless/redacting telemetry
  setup instead, with content capture disabled for attendee data.
- The SDK runtime cache otherwise defaults to the user's home. Its default is
  redirected to `/tmp` for the hosted read-only filesystem contract.

Local verification caught and fixed an empty-cursor validation hole, SQLite
connection cleanup, a frontend command run from the wrong directory, and the
missing Playwright browser. The accidental empty root npm lockfile was removed.
No production fallback or failed test was relabeled as success.

## Deployment findings and recovery

| Finding | Evidence / action |
| --- | --- |
| Different `az` and `azd` callers | New preflight detected a principal mismatch. The user explicitly approved `auth.useAzCliAuth=true`; the complete shared-caller/role gate then passed. Earlier permission checks should have compared both callers before any stage. |
| Root Foundry provider conflicts with named layers | Actual `azd provision core --preview` rejected the schema-valid combination. Moved `microsoft.foundry` to the `core` layer. Preview passed. |
| Implicit resource-group suffix | First preview targeted a new `-foundry` group instead of the documented group. Set `AZURE_FOUNDRY_RESOURCE_GROUP` explicitly and re-previewed the approved target before creation. |
| Early ACR access | Backend pull permission was originally created with its revision. Added the same deterministic grant to core provisioning so propagation can be checked before the first image pull. |
| Installed minimum hosted idle time | Agent extension beta.12 rejects 120 seconds; the manifest and plans now use the supported minimum of 300 seconds. |
| Frontend packaging precedes outputs | A predeploy hook rebuilds with the actual API origin and rejects stale bundles. This was exercised with real Vite builds. |
| AppInsights authentication discriminator | First real provision rejected generic `AAD`: this connection category requires `ProjectManagedIdentity` or `ApiKey`. Selected project managed identity, retaining keyless access. |
| AppInsights required metadata | Retry required `metadata.ApplicationInsightsConnectionString`. Added the shared routing configuration and `ApiType: Azure`. No API-key credentials or local authentication were enabled. |
| Stale Bicep enum | Bicep 0.42.1 warns BCP036 for `ProjectManagedIdentity` even though the live service explicitly requires it. Warning is documented; no untyped cast or API-key workaround hides it. |
| What-if is not full service validation | Compiles and previews passed before the connection-category failures. Add category-specific payload contract tests using current first-party guidance, not only generic ARM schemas. |

Microsoft Learn's Entra trace-ingestion documentation confirms project-managed
identity and Monitoring Metrics Publisher for project/agent identities. The
official connection sample still demonstrates API keys; it was not copied as
an authentication fallback.

Sources for the connection correction:

- `https://learn.microsoft.com/azure/foundry/observability/how-to/trace-ingestion-entra-authentication`
- Actual Azure validation responses for the AppInsights connection.

All failed provisioning attempts target this run's dedicated resource group.
No resources were deleted or broad cleanup attempted. Application endpoint,
real model/skill/toolbox operation, Azure restart persistence, and correlated
telemetry remain explicit post-deployment gates.

### Additional live findings after the foundation succeeded

| Finding | Evidence and correction |
| --- | --- |
| ARM output casing changed | Live deployment output keys appeared as `backenD_ORIGIN`, `applicationinsightS_CONNECTION_STRING`, etc. The hook now normalizes only Bicep-declared outputs, removes obsolete aliases, and rejects conflicting values. Values are not logged. |
| `azd up` initialization required another configuration surface | It required `infra.parameters.foundryProjectName`, `location`, and `resourceGroupName`, despite the existing azd environment. Set them to the already-approved values; did not create a new environment. |
| Repository-wide remote-build archive failed | Publishing hit `archive/tar: write too long`. Narrowed the backend to a service-local context, atomically staged the shared telemetry copy/requirements, and excluded temporary files. Subsequent ACR publishing succeeded. |
| Storage SDK constructor changed | Azure-mode startup failed because Tables SDK 12.7 requires keyword-only `credential`. Corrected the call and added a test constructing the real SDK client in Azure mode without performing data-plane I/O. SQLite-only tests had not covered this surface. |
| Platform CORS omitted PUT | Actual OPTIONS returned no Allow-Methods header. The azd pattern module exposed only origins. Switched the backend revision to the AVM resource module with explicit methods/trace headers, preserving identity, image, and scale settings. |
| Toolbox guardrail override was invalid | The sample's `Microsoft.Default` override caused HTTP 400 during MCP initialization. The model actually uses built-in `Microsoft.DefaultV2`; its default is not an account ARM policy resource for a separate toolbox override. Removed only the broken optional override, retained/verified model guardrails, and created/promoted a new immutable toolbox version through the documented REST gap. No history was deleted and no custom guardrail or filter-off setting was introduced. |
| Entra blueprint is not an Azure RBAC principal | ARM rejected `#microsoft.graph.agentIdentityBlueprintPrincipal`. Current Entra documentation says permissions belong to the acting agent identity and blueprints cannot receive Azure RBAC. The hook now selects the real instance identity only and rejects parent/blueprint substitutions. |
| Subscription-only policy review missed inherited controls | The declared Storage setting was Enabled, but its actual setting was Disabled. Resource activity showed a management-group Modify policy enforcing this. Correct MI identity, token audience, table existence, and Table Data Contributor were all verified; the real service error was 403 AuthorizationFailure. No permission escalation or storage-key workaround was attempted. |
| Browser assertion could match the draft | A text-only visibility assertion found the unsaved textarea value while persistence failed. Strengthened it to require the successful POST and a rendered question card before voting. |

The frontend and original backend deployed with successful azd exits. A real
hosted agent invocation returned the correct cited 13:27 answer in 22 seconds.
Application Insights contains the same trace across the hosted agent, Copilot
CLI model/tool spans, backend MCP, and Foundry service. These successes do not
hide the failed Azure storage/browser gate.

### Approved compliant networking response

The user explicitly approved a VNet, Table private endpoint/DNS, and a
VNet-integrated replacement backend. Storage public access stays Disabled;
shared keys stay disabled. No policy exemption or public-access override.
The replacement preserves storage/data, identity, ACR, model/project, and
monitoring. Old backend/environment resources remain until separate cleanup
approval.

The amended templates, 28 hook tests, 25 application tests, frontend build,
3 component tests, and 2 local browser tests pass. The actual private-core
preview contains no deletes. Additional networking charges and the frozen
migration boundary are recorded in the plan. Reverification of real private
DNS, storage transactions, restart durability, and remote browser behavior is
required before calling the app ready.

Upstream improvements:

- Policy discovery must include inherited management-group effects, especially
  Modify, rather than treating an empty/subscription-only list as clearance.
- Validate actual Azure-mode SDK constructors, not only local substitutes.
- Treat resource provisioning/health and application data-plane readiness as
  different gates; both can be green while the data path is blocked.
- Use current Entra eligibility rules instead of assigning every identity-like
  ID returned by agent metadata.
- Keep output normalization at the provisioning boundary and make intended
  endpoint migrations explicit and scope-bound.
- Test the full governed MCP call, not just metadata or `tools/list`.

Identity reference:
`https://learn.microsoft.com/entra/agent-id/agent-service-principals#key-differences`

### Subscription networking capability

The VNet-integrated environment waited and then failed in
`ConfigureAllocatedClusterHandler`: the subscription was not registered for
`Microsoft.Network/AllowBringYourOwnPublicIpAddress`. Provider registration and
regional API support had passed, but they did not prove this capability was
enabled.

The live feature state was NotRegistered. The documented registration request
returned Registered immediately, and Microsoft.Network was re-registered to
propagate the change. No policy was modified and no resource was deleted.
The preprovision gate now checks this capability, with tests rejecting Pending,
Registering, NotRegistered, and missing states. A subsequent preview has no
deletes; reconciliation of the failed environment remains a live deployment
check, not a preview success claim.

Upstream improvement: include service-specific subscription feature gates in
the joint placement check before creating a VNet-integrated environment.

### Replacement app provisioning stalled and failed

After the feature was registered, the environment reported Succeeded, but its
first application remained InProgress with no revision. ACR publishing had
completed; ARM remained in the Container App Create operation. The rollout
eventually failed after 20m13s with `ContainerAppOperationError` and an empty
detail string.

The environment's static IP was null, no public IP/load balancer appeared in
its managed group, and its networking detector reported missing telemetry.
These observations do not establish the exact root cause. A top-level
Succeeded flag and a detector's "no failures detected" message are insufficient
when the underlying telemetry is absent. Preserve the working original
resources and require explicit approval before recreating the empty failed
replacement.

The user then explicitly approved a full environment down/purge and fresh
recreation. This is no longer a preservation-only migration: both original and
failed replacement resources in the tagged demo environment may be removed.
The repository and subscription-wide prerequisites remain outside teardown.

Native `azd down --force --purge` refused to delete the Foundry layer because
its ownership record was empty. A supported layer refresh succeeded but did not
restore ownership. The current inventory and environment tag matched the
resources created by this run. The user separately approved exact-group manual
deletion and purge of its Foundry account; no ownership flag was fabricated and
no unrelated group was selected.

Upstream improvement: preserve or recover verified layer ownership across
failed provisioning/postprovision operations, so supported teardown does not
require a separately approved manual fallback.

### Clean recreation and AI-only recovery

The exact approved group, both managed environment groups, and soft-deleted
Foundry account were verified absent before native azd environment recreation.
The clean private environment obtained real networking; its backend deployed in
2m14s and actual Table/browser flows worked. No public Storage override or
shared-key fallback was introduced.

| Finding | Evidence and outcome |
| --- | --- |
| ARM Succeeded did not mean project data readiness | The recreated original project repeatedly returned `ProjectNotFound`. A second project in the same account exposed working skills/agent management APIs. |
| Connection ownership collisions | Reused names belonged to the earlier workspace. Project-prefixed AppInsights, registry, and agenda connection names resolved publication; the toolbox hook renders only its declared project placeholder and rejects unresolved variables. |
| Active agent did not mean runtime readiness | The second project's dedicated endpoint returned 404 `ProjectNotFound` through both the backend and official CLI. Reapplying the explicit Responses/Entra endpoint configuration did not fix it. Root cause remains unconfirmed. |
| Approved AI-only replacement | The user selected a uniquely named account/project. A reviewed no-delete preview and account-name override preserved the working app/data/network/registry. R2 provision and rollout completed; real runtime invocation now succeeds. Old AI resources remain pending separate cleanup approval. |
| Missing AlertsManagement registration | Portal error matched live NotRegistered state. Registration completed and was verified Registered. No established link to the runtime 404. |
| Assistant validation had no browser coverage | Added a deployed-only Chromium test requiring HTTP success, actual cited 13:27 output, source navigation, and mobile layout. It skips locally rather than inventing a fake AI answer. |

Final evidence on September 20: rollout exit 0 in 4m48s; full smoke passed real
Table writes/retries/voting, restart persistence, real cited answer, and
unsupported-question refusal. All three deployed Chromium tests passed. The
official CLI also returned a cited answer; session logs show actual governed
skill download and R2 toolbox calls. Fresh Insights trace
`9ba64ee2f5d535466ce6ed1c7441fc60` connects the API, hosted agent, Copilot
model/tool calls, and Foundry service. The actual instance identity's scoped
model/Foundry/telemetry roles were verified.

Upstream improvement: separate project-management readiness, agent activation,
and actual hosted-endpoint invocation gates. Bound recovery attempts and
preserve a working application while diagnosing only the failed component.
Do not infer a control-plane success implies runtime readiness, or attribute
success to an unrelated provider registration.

### Clean-environment reproducibility test

On September 21, the user explicitly approved `azd down --purge --force` and a
new environment name. The first teardown attempt hit DNS lookup timeouts while
deleting the model/resource group, but Azure completed group deletion. Both
soft-deleted Foundry accounts were then explicitly purged and verified absent.
This was a full teardown, not reuse of the prior R2 account.

| Reproducibility finding | Permanent correction |
| --- | --- |
| Caller preflight rejected every resource group except the retired literal name | It now validates the explicit `rg-${AZURE_ENV_NAME}` contract, requiring the Foundry and application groups to match. Tests cover a new accepted environment and an unrelated rejected scope. |
| Fresh `azd env new` lacks tenant context required by the keyless preflight | `scripts/create-clean-env.sh` obtains the current Azure subscription/tenant and persists the required local environment values. |
| Foundry provider requires Bicep input configuration, not merely environment variables | The helper writes the three documented `infra.parameters.*` settings through `azd env config set`. |
| Postprovision expected the model deployment name only present in prior local state | `infra/main.bicep` now emits `AZURE_AI_MODEL_DEPLOYMENT_NAME` from the configured deployment, so guardrail/toolbox publication has an actual provisioning output. |

The new environment provisioned successfully in 5m10s and deployed in 6m39s.
Its smoke test passed Azure Table writes, restart persistence, real cited answer,
and refusal. All three deployed browser tests passed. The official agent
endpoint returned the cited answer in 18.2 seconds, and trace
`6fc5ffbbf9844d87b1dd8b178f00668c` links the browser API, hosted agent, Copilot
model/tool, and agenda MCP. This confirms a clean deployment works with the
versioned repository plus documented/bootstrap azd configuration—not with hidden
state from the deleted deployment.

## Assumptions made

1. [NEEDS CLARIFICATION: Which Azure subscription and caller should this run use? -- assumed: the current Azure CLI subscription and signed-in user, for read-only preflight only.]
2. [NEEDS CLARIFICATION: Reuse existing Azure resources or create new ones? -- assumed: greenfield; the repository contains no deployment configuration and no target resource scopes were provided.]
3. [NEEDS CLARIFICATION: What history should support the issues report if the active session is not indexed yet? -- assumed: the visible current conversation and tool results are the evidence for this attempt.]

The event date and intentionally omitted demo features are source evidence, not
assumptions. These first-attempt assumptions are supplemented by all fourteen
Specify defaults in `docs/spec.md` section 12 and the Plan defaults in
`docs/plan.md` section 7. Those documents enumerate the runtime, template,
hosting, data, scale, identity, retention, region, and demo-automation choices.
Region/model/quota were subsequently checked live before environment persistence.
No hard budget ceiling or Swiss/EU residency obligation was invented.

## Remaining handoff

The permission handoff has been executed with explicit user authorization, and
the complete caller assignment gate independently re-evaluated using live role
IDs without weakening its requirements. It passed. The stock upstream checker
still needs correction; do not rely on its two-requirement greenfield PASS.

The deployed application gates now pass. GitHub CI/PR previews require an
explicit repository target and real PR verification. Old broken AI resources
must not be removed without separate approval. Keep the three planned live-demo
features absent, retain sample-agenda labels, and do not publish private
runbook or meeting content.
