# Spec2Cloud issues: Cloud and AI Day Geneva companion

Run date: 2026-09-20. Demo date confirmed by the supplied runbook: 2026-09-21.

## Outcome

**BLOCKED before Specify by the mandatory Agentic Loop caller RBAC gate.**
No application, infrastructure, role assignment, GitHub issue, or deployment was
created. `azd up` was not run. There is no deployed frontend endpoint.

The installed `spec2cloud` and `agentic-loop` skills were invoked. The latter
requires this permission gate before step 1, so its stop condition takes
precedence over continuing the four-stage pipeline. The Foundry skill was also
invoked to diagnose the prerequisite-role discrepancy.

## Stage outputs and blockers

| Stage | Status | Output / issue |
| --- | --- | --- |
| Source intake and preflight | Blocked | Runbook requirements retrieved through authenticated M365. Caller control-plane access passed; the installed policy's Foundry prerequisites were absent. The stock check also has the defects below. |
| Specify | Not started | `docs/spec.md` not generated. Do not turn incomplete intake into an approved specification. Apply Agentic Loop immediately after Specify when the run resumes. |
| Plan | Not started | `docs/plan.md` and `.azure/deployment-plan.md` not generated. No template, model placement, region, SKU, or implementation contract was selected. |
| Implement / Verify | Not started | No source code, package manifests, infrastructure, or application tests generated. No implementation verification gate was reached. |
| Deploy | Not started | `deploy` not invoked; `azd up` not executed. No provisioning or endpoint checks attempted. |
| Issue analysis | Complete for this attempt | This report records observed failures, recoveries, and upstream improvement proposals, not hypothetical later-stage failures. |

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
which was present under its old or current name:

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
Account Owner alone cannot replace it. No privileges were self-granted.

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

## Assumptions made

1. [NEEDS CLARIFICATION: Which Azure subscription and caller should this run use? -- assumed: the current Azure CLI subscription and signed-in user, for read-only preflight only.]
2. [NEEDS CLARIFICATION: Reuse existing Azure resources or create new ones? -- assumed: greenfield; the repository contains no deployment configuration and no target resource scopes were provided.]
3. [NEEDS CLARIFICATION: What history should support the issues report if the active session is not indexed yet? -- assumed: the visible current conversation and tool results are the evidence for this attempt.]

The event date and intentionally omitted demo features are source evidence, not
assumptions. No cost ceiling, residency obligation, region, SKU, model quota,
package version, or deployment environment name was assumed or persisted.

## Resume conditions

An authorized owner must resolve the permission handoff. The upstream checker
must also be corrected or the documented complete contract independently
re-evaluated against live role IDs and permissions without weakening it.
Re-run preflight; only a complete PASS permits Specify.

Then execute Specify, apply the Agentic Loop post-Specify policy before Plan,
perform placement and skill-freshness checks, implement and verify the baseline,
and finally invoke Deploy and `azd up`. Update this report with actual outcomes.
