# Verification

Status: local checks and all deployed application gates passed on September 20,
2026. The separate GitHub PR-preview gate is not satisfied without a remote.
Current endpoint/results and the fresh distributed trace are in `docs/deploy.md`.

## Local evidence

Run the commands in the README. The Python suite covers API contracts, retries,
concurrent voting, Table transaction construction, SQLite restart persistence,
public MCP discovery, the real Responses-host envelope, grounded refusals,
installed SDK API shape, and telemetry redaction.

The browser suite tests actual API/UI behavior at 360px and desktop widths,
including question submission, voting, reload persistence, private suggestion
receipts, and the warm local ten-reader p95 target of less than one second.
It does not substitute for an Azure storage or real model invocation.
When `PLAYWRIGHT_BASE_URL` targets the deployed app, a third test performs a
real assistant request and requires its HTTP success, cited 13:27 answer, and
source navigation in the mobile UI. It is explicitly skipped locally because
local development has no mock assistant fallback.

`bash scripts/validate-infra.sh` compiles each Bicep entrypoint, checks installed
CLI schemas/resource contracts, and runs the hook tests.
`python3 scripts/azure_hooks.py preflight` checks both deployment identities and
effective Azure roles without granting permissions.

## Mandatory cloud gate

Before provisioning, invoke the Azure validation workflow and preview the core
deployment using the approved local azd environment:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision core --preview --no-prompt
```

Treat failed authorization, unsupported resources, missing capacity, and
unexpected destructive changes as blockers. A compiled Bicep file is not proof
of actual regional allocation or data-plane access.

After deployment, check:

1. Actual frontend assets load and contain the current API origin.
2. Health/event APIs respond; a question and vote survive a backend restart.
3. Retrying a private suggestion with the same key returns its original receipt.
4. Governed skill download and toolbox discovery work using the agent identity.
5. A real Copilot SDK/model turn produces a cited event answer; unsupported facts
   produce the specified refusal, not a fabricated fallback.
6. A single correlated trace includes backend, agent, MCP/tool, and model spans.
   Raw attendee text/private suggestions are absent.
7. A real same-repository PR creates a frontend preview after a Git remote is
   explicitly configured. This gate is currently unverified.

Record actual outcomes in `docs/deploy.md`; do not infer success from local mocks.

The September 20 cloud run passed gates 1-6, including
`uv run python scripts/smoke_cloud.py --restart-backend` and all three remote
Chromium tests. The current application suite has 25 passing Python tests;
the infrastructure checker compiles three Bicep entrypoints and passes 31 hook
tests. Existing dependency deprecations and the documented AppInsights Bicep
enum warning remain; neither was hidden by weakening checks.
