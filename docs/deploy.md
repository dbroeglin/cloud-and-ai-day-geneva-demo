# Deployment

Status: **Frontend/backend deployed; approved private connectivity migration pending.**

The selected environment is `geneva-companion-dev-eus2`, with the target and
resource choices recorded in `.azure/deployment-plan.md`. Exact tenant and
subscription identifiers remain in ignored local azd state.

The user explicitly approved `azd config set auth.useAzCliAuth true` after the
preflight found mismatched `az`/`azd` identities. Both now use the previously
approved Azure CLI principal; the complete caller role check passes.

Azure validation, core preview, packaging, policy review, and caller checks
passed. Invoke the Deploy skill and run:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd up --no-prompt
```

The explicit ordered equivalent is `bash scripts/deploy.sh`: provision, deploy
backend, deploy the hosted agent, and deploy the frontend. Service hooks gate
backend/MCP readiness, publish skills/toolbox, reconcile runtime identities
through Bicep, and rebuild frontend assets using the actual API origin.

The initial core provision partially created foundation resources, then Foundry
rejected `authType: AAD` for the AppInsights connection. It is corrected to the
supported `ProjectManagedIdentity`; no API key is introduced. Revalidation and
an idempotent retry are required. No resources were deleted.

Those connection errors were resolved and the foundation is now provisioned.
The frontend is published at
`https://lemon-water-023fc110f.2.azurestaticapps.net/`; the original backend is
healthy and its public MCP works. The hosted Copilot SDK agent is active and
returned a real cited answer under its runtime identity. Its blueprint is not
an Azure RBAC-eligible principal, so grants are corrected to the actual agent
identity, following current Entra guidance.

Remote browser tests correctly failed data operations: an inherited
management-group policy forces Storage public network access off. Identity,
audience, data role, and table existence were verified; the service returns
403 AuthorizationFailure from the original public-network backend. The user
approved a private endpoint/VNet-integrated replacement, without bypassing the
policy or deleting old resources. The amended deployment passed validation.

The published URL is not yet attendee-ready: persisted-data operations still
require the approved private path. Hosted-agent inference has passed, but Azure
Table restart durability, full remote browser flows, and correlated telemetry
must pass after the migration before the demo is called cloud-ready.

PR previews remain a separate unverified requirement because no Git remote is
configured. No repository, PR, or GitHub security setting has been created or
changed by this run.
