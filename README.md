# Cloud & AI Day Geneva Event Companion

The deliberately small starting app for the 21 September 2026 meeting-to-pull-
request demo: sessions, immediate questions, voting, private feature suggestions,
and a read-only Copilot SDK event guide.

**French switching, question moderation, and Excel export are deliberately
absent.** They are the changes made during the live demonstration.

## Live demo

`https://ashy-pond-088bda60f.4.azurestaticapps.net/`

The deployed baseline includes working questions, votes, private suggestions,
and the real grounded event guide. Assistant calls observed during verification
took roughly 20-40 seconds. Deployment evidence, the agent playground, and
remaining GitHub workflow requirements are in [Deployment](docs/deploy.md).

## Run locally

Requires Node 24, uv, and Python 3.14 (uv can obtain the Python runtime).

```bash
uv sync --frozen
npm --prefix src/frontend ci
APP_ENV=local PYTHONPATH=src/backend:src/agents/event-guide \
  uv run uvicorn main:app --host 127.0.0.1 --port 8765
```

In another terminal:

```bash
npm --prefix src/frontend run dev
```

Open `http://127.0.0.1:5173`. Local questions and suggestions persist in
`.local/event-companion.sqlite3`. The assistant returns an explicit unavailable
message until a real Foundry project/agent is configured; there is no canned AI
fallback. Only the afternoon demo slot is confirmed; the other fixture sessions
are marked as samples.

## Check the app

```bash
uv run ruff check src/backend src/agents/event-guide tests
uv run pytest -q
npm --prefix src/frontend run build
npm --prefix src/frontend test
cd src/frontend
npx playwright install chromium
npm run test:e2e
```

The browser suite starts and stops its own local API/frontend. See
`docs/verify.md` for boundaries and Azure checks.

## Evaluate the hosted agent

The release evaluation uses only versioned synthetic public-agenda questions.
After the backend and hosted agent are deployed, run the fail-closed gate:

```bash
uv run python scripts/run_foundry_evals.py \
  --backend-origin "$BACKEND_ORIGIN" \
  --report-path .local/foundry-evals/event-guide-v1.json
```

It first validates the exact response/citation/refusal contract through the
public assistant API, then starts the Foundry hosted-agent evaluation declared
in `src/agents/event-guide/eval.yaml`. Do not use `--skip-foundry` for a
release decision; that option is only for offline contract testing.

## Deploy

Follow `.azure/deployment-plan.md` and `docs/deploy.md`. The Azure validation gate
must pass first. The infrastructure uses managed identities, not storage/model
keys. `az` and `azd` must use the same approved principal.

```bash
scripts/create-clean-env.sh geneva-companion-<suffix>-eus2
python3 scripts/azure_hooks.py preflight
bash scripts/validate-infra.sh
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd up --no-prompt
```

The clean-environment helper derives and configures the approved matching
resource group, tenant, and required Bicep inputs. It intentionally does not
reuse a previous Foundry account override. The frontend predeploy hook refreshes
the API origin after provisioning. Explicit ordered deployment is also available
through `bash scripts/deploy.sh`.
Do not print or commit local azd environment values or deployment tokens.

## Project map

- `src/frontend`: React/Vite UI.
- `src/backend`: FastAPI, public agenda MCP, Tables/SQLite persistence.
- `src/agents/event-guide`: Responses host, Copilot SDK, governed skills, telemetry.
- `skills/event-guide/SKILL.md`: authoring artifact, published to Foundry.
- `infra` and `scripts`: repeatable Azure provisioning and deployment hooks.
- `.github/skills/meeting-to-issues`: human-gated demo workflow.
- [Specification](docs/spec.md), [Plan](docs/plan.md), and [Implementation](docs/implementation.md): requirements and actual design.
- [Verification](docs/verify.md) and [Deployment](docs/deploy.md): checks, live endpoints, and operational boundaries.
- `docs/spec2cloud-issues.md`: stage failures, recoveries, and plugin improvements.

Feature suggestions are private to authorized operators. Do not put transcripts,
attendee details, credentials, or raw submissions in Git. `meeting/` is ignored.
After the event, review and remove demo data/resources manually after the planned
seven-day retention window; cleanup is not automatic and can destroy data.

No Git remote is currently configured. The checks workflow is authored, but CI,
branch protections, and PR preview environments are not activated or verified.
