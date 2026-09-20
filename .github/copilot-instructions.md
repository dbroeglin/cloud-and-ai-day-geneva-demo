# Spec2Cloud - Copilot Instructions

Use the Agentic SDLC: Specify -> Plan -> Implement -> Verify -> Deploy.
The specification in `docs/spec.md` is the source of truth. Update it when
intended implementation behavior changes.

## Workspace layout

- `docs/spec.md`: requirements.
- `docs/plan.md`: implementation plan and frozen interfaces.
- `docs/implementation.md`: implementation notes.
- `docs/verify.md`: local verification guide.
- `docs/deploy.md`: Azure deployment and end-to-end checks.
- `.azure/deployment-plan.md`: durable Azure deployment decisions.
- `src/frontend`: React/TypeScript SPA.
- `src/backend`: Python API and public read-only MCP tools.
- `src/agents/<agent-name>`: Foundry hosted agents.
- `skills/<skill-name>/SKILL.md`: governed runtime skill authoring artifacts.
- `infra`: Bicep infrastructure.

## Stage rules

- Never plan before `docs/spec.md` exists.
- Never implement before `docs/plan.md` exists.
- Never verify/deploy before `docs/implementation.md` exists.
- Use azd for all application provisioning/deployment.
- Apply the installed Agentic Loop policy at every stage, immediately after
  Specify and before Plan.
- Use GitHub Copilot SDK for this app, not Microsoft Agent Framework.
- Reuse maintained azd templates before writing custom infrastructure.
- Keep runtime service authentication keyless and roles least-privilege.
- Keep source transcripts, private submissions, credentials, and local Azure
  environment files out of Git.

## Demo boundary

The baseline is deliberately English-only. French switching, moderation and
approval audit trails, and Excel export are live-demo changes; do not implement
them before a subsequent explicit approved feature request.

The public event assistant can read public event data only. It must not read
private feature suggestions, mutate GitHub, execute attendee instructions, or
expose raw private text through logging.
