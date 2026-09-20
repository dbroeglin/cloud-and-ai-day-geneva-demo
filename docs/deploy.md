# Deployment

Status: **Teardown/purge verified; clean recreation validated.**

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

## Latest rollout result

The networking capability was registered and the replacement environment
reported Succeeded. The replacement app then failed after 20m13s with
`ContainerAppOperationError` and no detailed error. Its revision list is empty.
The original backend remains Succeeded. Network diagnostics do not establish a
healthy replacement environment: no static IP/public IP/load balancer is exposed,
and the detector reports missing telemetry.

Do not describe this as ordinary progress or a working deployment. No duplicate
deployment was launched while the operation was running. Recreating only the
failed replacement is a possible recovery, not a confirmed fix, and requires
explicit approval. Existing data and the original resources remain preserved.

The user subsequently requested a full `azd down --force --purge` and recreation
of `geneva-companion-dev-eus2`. That explicit approval supersedes the earlier
preservation restriction for this environment only. Local source and
subscription-level role/feature prerequisites are retained. Endpoint URLs can
change; previous published URLs must not be advertised as ready after teardown.

Native `azd down` refused because the Foundry ownership record was empty.
A supported `azd env refresh --layer core` did not restore it. Ownership was
not fabricated. After reviewing the exact group inventory and environment tag,
the user explicitly approved equivalent manual deletion of only the demo
resource group and permanent purge of its soft-deleted Foundry account.
That scoped deletion is in progress; recreation waits for deletion/purge
verification and a clean local azd environment.

Reset is now verified complete: the main group and both managed environment
groups are absent, and the approved soft-deleted Foundry account was purged.
The old local azd environment was removed through the CLI and recreated with
the approved target values; no old agent, project, toolbox, or runtime identity
bindings remain. The clean `--no-state` preview contains creates only, packaging
passes, and the required networking feature is already Registered.
