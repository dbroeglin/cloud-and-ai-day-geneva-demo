# Deployment

Status: **Validated for deployment; deployment has not started.**

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

No deployed frontend endpoint is available yet. Allocation, real hosted-agent
inference, restart durability on Azure Tables, and remote telemetry are not yet
verified. Do not consider the demo cloud-ready until those checks pass.

PR previews remain a separate unverified requirement because no Git remote is
configured. No repository, PR, or GitHub security setting has been created or
changed by this run.
