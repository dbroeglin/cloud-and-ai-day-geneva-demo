# Verification

## Local evidence

Run the commands in the README. The Python suite covers API contracts, retries,
concurrent voting, Table transaction construction, SQLite restart persistence,
public MCP discovery, the real Responses-host envelope, grounded refusals,
installed SDK API shape, and telemetry redaction.

The browser suite tests actual API/UI behavior at 360px and desktop widths,
including question submission, voting, reload persistence, private suggestion
receipts, and the warm local ten-reader p95 target of less than one second.
It does not substitute for an Azure storage or real model invocation.

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
