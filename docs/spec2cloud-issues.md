# Spec2Cloud issues: Cloud and AI Day Geneva companion

Run date: 2026-09-20. Demo date confirmed by the supplied runbook: 2026-09-21.

## Outcome

**Specify, Plan, and Implement complete; deployment is in progress.**
The caller RBAC assignment gate remains resolved.
The initial attempts were blocked before Specify. After the user's explicit
"run those commands" authorization at 14:16 CEST on 2026-09-20, both Foundry
role assignments in the handoff were created at the specified subscription
scope. A fresh inherited/group-derived assignment query confirmed their stable
role IDs alongside Owner, satisfying all four prerequisite capabilities.
Foundry data-plane propagation has not been exercised against an actual project.

The baseline application, tests, locked dependencies, and Azure lifecycle code
are committed. Core provisioning has partially created Azure foundation
resources and is being retried after connection-schema corrections. No GitHub
issues or repository were created. A working deployed frontend endpoint has
not yet been verified.

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
| Implement / Verify | Complete | Dependency conflicts resolved, baseline application committed as `95cb171`, infrastructure validated as `46fcd93`. 24 Python tests, 3 UI tests, 2 browser tests, a real SDK handshake, 3 Bicep entrypoints, and 22 hook tests pass. |
| Deploy | In progress | Deploy and azure-deploy invoked after the complete validation workflow. Real core provisioning exposed AppInsights connection constraints absent from Bicep/what-if validation; corrected without API keys and revalidated. Remote application checks remain pending. |
| Issue analysis | Updated through active deployment recovery | Current conversation and same-session history were analyzed. A partially created resource is not reported as a deployed application. |

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

## Resume conditions

The permission handoff has been executed with explicit user authorization, and
the complete caller assignment gate independently re-evaluated using live role
IDs without weakening its requirements. It passed. The stock upstream checker
still needs correction; do not rely on its two-requirement greenfield PASS.

The dependency, authentication, source, and static Azure validation gates now
pass. Continue the active deployment from its observed Azure state; do not
create a second environment or delete the partial foundation to hide a failure.
Complete the remote application, model, persistence, and telemetry checks before
claiming deployment success. Keep the GitHub PR-preview dependency separate.
