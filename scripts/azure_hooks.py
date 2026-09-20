#!/usr/bin/env python3
"""Fail-closed azd lifecycle hooks. No credentials or caller grants are persisted."""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
AGENT = "event-guide"
TOOLBOX = "event-companion"
CONNECTION = "event-agenda"
OWNER = "8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
CONTRIBUTOR = "b24988ac-6180-42a0-ab88-20f7382dd24c"
RBAC_ADMIN = "f58310d9-a9f6-439a-9e8d-f62e7b41a168"
USER_ACCESS_ADMIN = "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"
FOUNDRY_OWNER = "c883944f-8b7b-4483-af10-35834be79c4a"
ACCOUNT_OWNER = "e47c6f54-e4a2-4754-9501-8e0985b135e1"
PROJECT_MANAGER = "eadc314b-1a2d-4efa-be10-5d325db5065e"
ROLE_NAMES = {
    OWNER: "Owner",
    ACCOUNT_OWNER: "Foundry Account Owner",
    PROJECT_MANAGER: "Foundry Project Manager",
    "53ca6127-db72-4b80-b1b0-d745d6d5456d": "Foundry User",
    "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd": "Cognitive Services OpenAI User",
    "0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3": "Storage Table Data Contributor",
    "3913510d-42f4-4e42-8a64-420c390055eb": "Monitoring Metrics Publisher",
    "7f951dda-4ed3-4680-a7ca-43fe172d538d": "AcrPull",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(*args):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip() or "No diagnostic output."
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {details}")
    return result.stdout


def azd(*args, as_json=True):
    # Inline user-agent assignment applies only to this azd process.
    command = ["env", "AZURE_DEV_USER_AGENT=microsoft_foundry_skill", "azd", *args]
    if as_json:
        command += ["--output", "json"]
    result = run(*command)
    return json.loads(result) if as_json else result


def az(*args):
    return json.loads(run("az", *args, "--output", "json", "--only-show-errors"))


def environment():
    values = azd("env", "get-values")
    require(isinstance(values, dict), "azd returned an invalid environment.")
    return values


def needed(values, key):
    value = values.get(key, "")
    require(
        isinstance(value, str) and bool(value.strip()),
        f"Missing {key}; complete azd provisioning first.",
    )
    return value.strip()


def save(key, value):
    azd("env", "set", key, value, as_json=False)


def https_url(value, origin=False):
    parsed = urlsplit(value)
    require(
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment,
        "Expected an HTTPS URL without embedded credentials or fragments.",
    )
    if origin:
        require(
            parsed.path in ("", "/") and not parsed.query,
            "Expected an HTTPS origin, not an API path.",
        )
    return value.rstrip("/") if origin else value


def check_role_contract(assignments):
    # Conditional grants are not proof of permission to create every app resource/role.
    roles = {
        item["roleDefinitionId"].rsplit("/", 1)[-1].lower()
        for item in assignments
        if not item.get("condition")
    }
    missing = []
    if not (OWNER in roles or (CONTRIBUTOR in roles and roles & {RBAC_ADMIN, USER_ACCESS_ADMIN})):
        missing.append("Owner, or Contributor plus RBAC Administrator/User Access Administrator")
    if not roles & {ACCOUNT_OWNER, FOUNDRY_OWNER}:
        missing.append("Foundry Account Owner or Foundry Owner")
    if not roles & {PROJECT_MANAGER, FOUNDRY_OWNER}:
        missing.append("Foundry Project Manager or Foundry Owner")
    require(
        not missing,
        "Caller RBAC preflight failed: " + "; ".join(missing) + ". No roles were granted.",
    )


def check_azd_identity(principal, tenant):
    token = azd(
        "auth", "token", "--scope", "https://management.azure.com/.default", "--tenant-id", tenant
    )["token"]
    payload = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    require(
        claims.get("oid", "").lower() == principal.lower()
        and claims.get("tid", "").lower() == tenant.lower(),
        "az and azd are authenticated as different principals or tenants; stop.",
    )


def preflight():
    values = environment()
    subscription = needed(values, "AZURE_SUBSCRIPTION_ID")
    tenant = needed(values, "AZURE_TENANT_ID")
    account = az("account", "show", "--subscription", subscription)
    require(account["tenantId"].lower() == tenant.lower(), "az and azd tenant contexts differ.")
    require(
        account["user"]["type"] == "user",
        "This preflight requires the approved authenticated user, not a service principal.",
    )
    principal = az("ad", "signed-in-user", "show")["id"]
    check_azd_identity(principal, tenant)
    assignments = az(
        "role",
        "assignment",
        "list",
        "--subscription",
        subscription,
        "--assignee",
        principal,
        "--scope",
        f"/subscriptions/{subscription}",
        "--include-inherited",
        "--include-groups",
        "--fill-principal-name",
        "false",
    )
    check_role_contract(assignments)
    for role_id, name in ROLE_NAMES.items():
        definitions = az(
            "role", "definition", "list", "--subscription", subscription, "--name", role_id
        )
        require(
            len(definitions) == 1
            and definitions[0]["name"].lower() == role_id
            and definitions[0]["roleName"] == name,
            f"Role definition changed or is unavailable: {name}.",
        )
    require(
        needed(values, "AZURE_LOCATION") == "eastus2", "This frozen placement requires eastus2."
    )
    require(
        needed(values, "AZURE_RESOURCE_GROUP") == "rg-geneva-companion-dev-eus2",
        "Resource-group selection differs from the approved target.",
    )
    print(
        "PASS: caller context, inherited/group roles, and live role definitions. No caller grants."
    )


def tree_digest(path):
    digest = hashlib.sha256()
    require((path / "SKILL.md").is_file(), "The governed skill must contain SKILL.md.")
    for file in sorted(path.rglob("*")):
        require(not file.is_symlink(), "Skill bundles must not contain symlinks.")
        if file.is_file():
            digest.update(file.relative_to(path).as_posix().encode())
            digest.update(b"\0")
            digest.update(file.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def publish_skill(endpoint):
    local = ROOT / "skills" / AGENT
    local_digest = tree_digest(local)
    skills = azd("ai", "skill", "list", "--project-endpoint", endpoint)
    require(isinstance(skills, list), "Unexpected skill list response.")
    exists = any(skill["name"] == AGENT for skill in skills)
    if exists:
        with tempfile.TemporaryDirectory(prefix="geneva-skill-") as temp:
            azd(
                "ai",
                "skill",
                "download",
                AGENT,
                "--project-endpoint",
                endpoint,
                "--output-dir",
                temp,
            )
            if tree_digest(Path(temp)) == local_digest:
                return
    azd(
        "ai",
        "skill",
        "update" if exists else "create",
        AGENT,
        "--project-endpoint",
        endpoint,
        "--file",
        str(local),
        "--no-prompt",
    )


def check_connection(values):
    project_id = needed(values, "AZURE_AI_PROJECT_ID")
    resource = az(
        "rest",
        "--method",
        "get",
        "--url",
        f"https://management.azure.com{project_id}/connections/{CONNECTION}?api-version=2025-04-01-preview",
    )
    props = resource["properties"]
    target = https_url(needed(values, "BACKEND_ORIGIN"), origin=True) + "/mcp"
    require(
        props["category"] == "RemoteTool"
        and props["authType"] == "None"
        and props["target"] == target,
        "Bicep-owned event-agenda connection differs from the public agenda contract; "
        "reprovision core.",
    )
    return resource["id"], target


def check_toolbox_version(version, connection_id, target, complete=True):
    tools = version.get("tools", [])
    skills = version.get("skills", [])
    require(
        len(tools) <= 1 and len(skills) <= 1,
        "Unexpected toolbox entries; refusing to alter unrelated work.",
    )
    for tool in tools:
        require(
            tool.get("type") == "mcp"
            and tool.get("server_label") == CONNECTION
            and tool.get("project_connection_id", "").lower() == connection_id.lower()
            and tool.get("server_url") == target,
            "Existing toolbox MCP definition differs from the frozen contract. "
            "The installed CLI cannot replace its sole tool without deleting history; "
            "stop for explicit migration.",
        )
    for skill in skills:
        require(
            skill.get("type") == "skill_reference"
            and skill.get("name") == AGENT
            and not skill.get("version"),
            "Existing toolbox skill differs from the unpinned event-guide reference.",
        )
    if complete:
        require(
            len(tools) == 1 and len(skills) == 1,
            "Toolbox must contain one agenda connection and one governed skill.",
        )
        require(
            version.get("policies", {}).get("rai_config", {}).get("rai_policy_name")
            == "Microsoft.Default",
            "Toolbox must retain Microsoft.Default content filtering.",
        )


def publish():
    values = environment()
    endpoint = https_url(needed(values, "FOUNDRY_PROJECT_ENDPOINT"))
    publish_skill(endpoint)
    connection_id, target = check_connection(values)
    listed = azd("ai", "toolbox", "list", "--project-endpoint", endpoint)
    require(isinstance(listed.get("toolboxes"), list), "Unexpected toolbox list response.")
    exists = any(item["name"] == TOOLBOX for item in listed["toolboxes"])
    if not exists:
        azd(
            "ai",
            "toolbox",
            "create",
            TOOLBOX,
            "--from-file",
            "src/tools.yaml",
            "--project-endpoint",
            endpoint,
            "--no-prompt",
        )
    else:
        shown = azd("ai", "toolbox", "show", TOOLBOX, "--project-endpoint", endpoint)
        current = shown["version"]
        check_toolbox_version(current, connection_id, target, complete=False)
        # Branch from the promoted version, not an unrelated unpublished draft.
        branch = current["version"]
        changed = False
        if not current.get("tools"):
            added = azd(
                "ai",
                "toolbox",
                "connection",
                "add",
                TOOLBOX,
                CONNECTION,
                "--from-version",
                branch,
                "--project-endpoint",
                endpoint,
                "--no-prompt",
            )
            branch = added["version"]
            changed = True
        if not current.get("skills"):
            added = azd(
                "ai",
                "toolbox",
                "skill",
                "add",
                TOOLBOX,
                AGENT,
                "--from-version",
                branch,
                "--project-endpoint",
                endpoint,
                "--no-prompt",
            )
            branch = added["version"]
            changed = True
        if changed:
            candidate = azd(
                "ai",
                "toolbox",
                "show",
                TOOLBOX,
                "--version",
                branch,
                "--project-endpoint",
                endpoint,
            )
            check_toolbox_version(candidate["version"], connection_id, target)
            azd(
                "ai",
                "toolbox",
                "publish",
                TOOLBOX,
                branch,
                "--project-endpoint",
                endpoint,
                "--no-prompt",
            )
    shown = azd("ai", "toolbox", "show", TOOLBOX, "--project-endpoint", endpoint)
    check_toolbox_version(shown["version"], connection_id, target)
    generated_endpoint = https_url(shown["endpoint"])
    require(
        generated_endpoint.startswith(endpoint.rstrip("/") + "/toolboxes/"),
        "Toolbox endpoint belongs to another project.",
    )
    save("TOOLBOX_EVENT_COMPANION_MCP_ENDPOINT", generated_endpoint)
    print(
        "PASS: skill, Bicep connection, and toolbox metadata published. "
        "MCP discovery waits for backend deployment."
    )


def rpc_result(body, content_type, request_id):
    if "text/event-stream" in content_type:
        messages = []
        for block in body.replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(
                line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")
            )
            if data:
                messages.append(json.loads(data))
    else:
        messages = [json.loads(body)]
    for message in messages:
        if message.get("id") == request_id:
            require("error" not in message, f"MCP request {request_id} returned a protocol error.")
            require(isinstance(message.get("result"), dict), "MCP result is not an object.")
            return message["result"]
    raise RuntimeError(f"MCP response omitted request {request_id}.")


def discover(endpoint, token=None, call_agenda=False):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def send(method, params, request_id=None):
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if request_id is not None:
            payload["id"] = request_id
        request = Request(
            endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with urlopen(request, timeout=60) as response:
            require(
                response.url == endpoint,
                "MCP endpoint redirected; the exact governed endpoint is required.",
            )
            if response.headers.get("Mcp-Session-Id"):
                headers["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
            if request_id is None:
                return {}
            return rpc_result(
                response.read().decode(), response.headers.get("Content-Type", ""), request_id
            )

    initialized = send(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "geneva-deployment-check", "version": "1.0"},
        },
        1,
    )
    headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
    send("notifications/initialized", {})
    result = send("tools/list", {}, 2)
    require(not result.get("nextCursor"), "Unexpected paginated agenda tool catalog.")
    tools = result.get("tools", [])
    agenda = [tool for tool in tools if tool.get("name", "").endswith("get_event_agenda")]
    require(len(agenda) == 1, "MCP discovery did not return exactly one agenda tool.")
    if call_agenda:
        require(
            [tool["name"] for tool in tools] == ["get_event_agenda"],
            "Public backend exposed unexpected MCP tools.",
        )
        response = send("tools/call", {"name": "get_event_agenda", "arguments": {}}, 3)
        require(not response.get("isError"), "Public agenda tool returned an error.")
        content = response.get("structuredContent")
        if content is None:
            text = [
                item["text"] for item in response.get("content", []) if item.get("type") == "text"
            ]
            require(len(text) == 1, "Agenda tool did not return structured public sources.")
            content = json.loads(text[0])
        require(
            isinstance(content.get("sources"), list) and bool(content["sources"]),
            "Agenda tool returned no public sources.",
        )


def backend_ready(values=None):
    values = environment() if values is None else values
    origin = https_url(needed(values, "BACKEND_ORIGIN"), origin=True)
    for attempt in range(24):
        try:
            with urlopen(origin + "/api/health", timeout=10) as response:
                require(response.status == 200, "Backend health returned a non-200 status.")
            break
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 23:
                raise RuntimeError(
                    "Backend did not become healthy; stop before agent deployment."
                ) from error
            print(f"Waiting for backend health ({attempt + 1}/24).", file=sys.stderr)
            time.sleep(5)
    discover(origin + "/mcp", call_agenda=True)
    print("PASS: real backend health and exact public /mcp initialize/list/call.")


def agent_ready():
    values = environment()
    backend_ready(values)
    endpoint = https_url(needed(values, "TOOLBOX_EVENT_COMPANION_MCP_ENDPOINT"))
    token = az(
        "account",
        "get-access-token",
        "--subscription",
        needed(values, "AZURE_SUBSCRIPTION_ID"),
        "--resource",
        "https://ai.azure.com",
    )["accessToken"]
    discover(endpoint, token=token)
    print("PASS: governed toolbox discovery. Runtime permissions are reconciled after deployment.")


def runtime_principals(agent):
    result = []
    for field in ("instance_identity", "blueprint"):
        identity = agent.get(field)
        require(
            isinstance(identity, dict),
            f"Agent {field} is unavailable; no project/account identity substitution is allowed.",
        )
        value = identity.get("principal_id", "")
        require(
            bool(value),
            f"Agent {field}.principal_id is unavailable; "
            "no project/account identity substitution is allowed.",
        )
        result.append(str(UUID(value)))
    return sorted(set(result))


def runtime_rbac():
    values = environment()
    for attempt in range(12):
        agent = azd("ai", "agent", "show", AGENT)
        require(
            agent.get("status", "").lower() not in {"failed", "error"},
            "Hosted agent deployment failed.",
        )
        if (agent.get("instance_identity") or {}).get("principal_id") and (
            agent.get("blueprint") or {}
        ).get("principal_id"):
            break
        if attempt < 11:
            print("Waiting for actual agent instance/blueprint identities.", file=sys.stderr)
            time.sleep(5)
    principals = runtime_principals(agent)
    project_id = needed(values, "AZURE_AI_PROJECT_ID")
    account_id = project_id.rsplit("/projects/", 1)[0]
    parent_ids = {
        az("resource", "show", "--ids", resource_id, "--api-version", "2025-06-01")["identity"][
            "principalId"
        ].lower()
        for resource_id in (project_id, account_id)
    }
    require(
        not set(principals) & parent_ids,
        "Agent identities unexpectedly match project/account identities; stop.",
    )
    save("AGENT_RUNTIME_PRINCIPAL_IDS", ",".join(principals))
    # Only this role-assignment layer is applied; core resources and publication hooks do not rerun.
    azd("provision", "runtime-rbac", "--no-prompt", as_json=False)
    print(
        "PASS: actual agent instance/blueprint roles reconciled through azd Bicep. "
        "Allow RBAC propagation before smoke."
    )


def frontend_config():
    values = environment()
    origin = https_url(needed(values, "VITE_API_BASE_URL"), origin=True)
    require(
        origin == https_url(needed(values, "BACKEND_ORIGIN"), origin=True),
        "Frontend API URL differs from the backend provisioning output.",
    )
    print(
        "PASS: VITE_API_BASE_URL comes from azd provisioning outputs and is passed by azd to npm."
    )
    return origin


class FrontendScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "module" and attributes.get("src"):
            self.paths.append(attributes["src"])


def verify_frontend_assets(directory, origin):
    directory = directory.resolve()
    index = directory / "index.html"
    require(index.is_file(), "Frontend build did not produce dist/index.html.")
    scripts = FrontendScripts()
    scripts.feed(index.read_text())
    require(bool(scripts.paths), "Frontend index contains no bundled module scripts.")
    bundles = []
    for source in scripts.paths:
        parsed = urlsplit(source)
        require(
            not parsed.scheme and not parsed.netloc and not parsed.query and not parsed.fragment,
            "Frontend entry script must reference a local build artifact.",
        )
        artifact = (directory / parsed.path.lstrip("/")).resolve()
        require(
            artifact.is_relative_to(directory) and artifact.is_file(),
            "Frontend index references a missing or out-of-directory script.",
        )
        bundles.append(artifact.read_text())
    require(
        any(origin in bundle for bundle in bundles),
        "Frontend entry bundle does not contain the current provisioned API URL; refusing upload.",
    )


def frontend_package():
    origin = frontend_config()
    frontend = ROOT / "src" / "frontend"
    require(
        not (frontend / "swa-cli.config.json").exists(),
        "This hook requires azd's declared dist artifact, not an overriding SWA CLI config.",
    )
    # SWA Publish is a no-op; installed azd uploads this live directory after predeploy.
    # Set VITE_API_BASE_URL explicitly, overriding stale shell or initially loaded azd state.
    subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend,
        env={**os.environ, "VITE_API_BASE_URL": origin},
        check=True,
    )
    verify_frontend_assets(frontend / "dist", origin)
    print("PASS: SWA upload artifact rebuilt with the current backend URL and bundle verified.")


def main():
    actions = {
        "preflight": preflight,
        "publish": publish,
        "backend-ready": backend_ready,
        "agent-ready": agent_ready,
        "runtime-rbac": runtime_rbac,
        "frontend-config": frontend_config,
        "frontend-package": frontend_package,
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=actions)
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        actions[args.action]()
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
