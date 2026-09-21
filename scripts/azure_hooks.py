#!/usr/bin/env python3
"""Fail-closed azd lifecycle hooks. No credentials or caller grants are persisted."""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
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
    declared = set()
    for template in (ROOT / "infra/main.bicep", ROOT / "infra/backend.bicep"):
        declared.update(re.findall(r"(?m)^output\s+([A-Z][A-Z0-9_]*)\s", template.read_text()))
    updates, obsolete = canonical_output_updates(values, declared)
    if updates:
        for key, value in updates.items():
            save(key, value)
        remove_environment_keys(values, obsolete)
        values = {key: value for key, value in values.items() if key not in obsolete}
        values.update(updates)
        print(f"Normalized {len(updates)} declared deployment output names; values not logged.")
    return values


def canonical_output_updates(values, declared):
    updates = {}
    obsolete = set()
    for key, value in values.items():
        canonical = key.upper()
        if key == canonical or canonical not in declared:
            continue
        require(isinstance(value, str), f"Deployment output {canonical} is not a string.")
        existing = updates.get(canonical, values.get(canonical, value))
        require(existing == value, f"Conflicting output values for {canonical}; do not guess.")
        updates[canonical] = value
        obsolete.add(key)
    return updates, obsolete


def environment_file(values):
    name = needed(values, "AZURE_ENV_NAME")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}", name), "Invalid azd environment name.")
    root = (ROOT / ".azure").resolve()
    path = root / name / ".env"
    require(
        path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
        "Expected a local azd environment file within this workspace.",
    )
    return path


def remove_environment_keys(values, keys):
    path = environment_file(values)
    lines = [
        line
        for line in path.read_text().splitlines(keepends=True)
        if line.partition("=")[0].strip() not in keys
    ]
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
        file.write("".join(lines))
        temporary = Path(file.name)
    temporary.chmod(0o600)
    temporary.replace(path)


def migration_record(values):
    path = environment_file(values).parent / "private-connectivity-migration.json"
    require(
        path.is_file() and not path.is_symlink(), "No approved private migration record exists."
    )
    record = json.loads(path.read_text())
    require(
        record.get("resource_group") == needed(values, "AZURE_RESOURCE_GROUP")
        and record.get("subscription_id") == needed(values, "AZURE_SUBSCRIPTION_ID")
        and record.get("tenant_id") == needed(values, "AZURE_TENANT_ID")
        and record.get("approved") is True,
        "Private migration record does not match this approved environment.",
    )
    return record


def prepare_private_migration():
    values = environment()
    path = environment_file(values).parent / "private-connectivity-migration.json"
    if not path.exists():
        old_name = needed(values, "AZURE_BACKEND_NAME")
        old_environment = needed(values, "AZURE_CONTAINER_ENVIRONMENT_NAME")
        require(
            re.fullmatch(r"api-[a-z0-9]{13}", old_name)
            and old_environment == "cae-" + old_name.removeprefix("api-"),
            "Expected the known original demo backend/environment; do not guess a migration.",
        )
        record = {
            "approved": True,
            "subscription_id": needed(values, "AZURE_SUBSCRIPTION_ID"),
            "tenant_id": needed(values, "AZURE_TENANT_ID"),
            "resource_group": needed(values, "AZURE_RESOURCE_GROUP"),
            "old_backend": old_name,
            "old_environment": old_environment,
            "old_origin": https_url(needed(values, "BACKEND_ORIGIN"), origin=True),
            "new_backend": old_name.replace("api-", "api-private-", 1),
            "new_environment": old_environment.replace("cae-", "cae-private-", 1),
        }
        path.write_text(json.dumps(record, indent=2) + "\n")
        path.chmod(0o600)
    record = migration_record(values)
    if (
        values.get("AZURE_BACKEND_NAME") == record["new_backend"]
        and values.get("BACKEND_ORIGIN")
        and values["BACKEND_ORIGIN"] != record["old_origin"]
    ):
        print("Private replacement outputs already exist; no preparation changes needed.")
        return
    remove_environment_keys(
        values,
        {
            "BACKEND_ORIGIN",
            "VITE_API_BASE_URL",
            "AZURE_CONTAINER_APP_NAME",
            "AZURE_CONTAINER_APP_ID",
        },
    )
    save("AZURE_BACKEND_NAME", record["new_backend"])
    save("AZURE_CONTAINER_ENVIRONMENT_NAME", record["new_environment"])
    save("SERVICE_BACKEND_RESOURCE_EXISTS", "false")
    print("Prepared the approved private replacement; old resources remain untouched.")


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
    environment_name = needed(values, "AZURE_ENV_NAME")
    require(
        re.fullmatch(r"geneva-companion-[a-z0-9-]+-eus2", environment_name),
        "AZURE_ENV_NAME must be a Geneva companion East US 2 environment.",
    )
    expected_group = f"rg-{environment_name}"
    require(
        needed(values, "AZURE_RESOURCE_GROUP") == expected_group
        and needed(values, "AZURE_FOUNDRY_RESOURCE_GROUP") == expected_group,
        "Resource-group selection must match the configured Geneva environment.",
    )
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
    check_network_feature(
        az(
            "feature",
            "show",
            "--namespace",
            "Microsoft.Network",
            "--name",
            "AllowBringYourOwnPublicIpAddress",
            "--subscription",
            subscription,
        )
    )
    print(
        "PASS: caller context, inherited/group roles, live role definitions, and network feature. "
        "No caller grants."
    )


def check_network_feature(feature):
    state = (feature.get("properties") or {}).get("state")
    require(
        state == "Registered",
        "Microsoft.Network/AllowBringYourOwnPublicIpAddress is not Registered. "
        "Stop before provisioning the VNet-integrated environment.",
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
    connection_name = project_id.rsplit("/", 1)[-1] + "-" + CONNECTION
    resource = az(
        "rest",
        "--method",
        "get",
        "--url",
        f"https://management.azure.com{project_id}/connections/{connection_name}"
        "?api-version=2025-04-01-preview",
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
            and tool.get("server_label") == connection_id.rsplit("/", 1)[-1]
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
            not version.get("policies"),
            "No toolbox-specific custom guardrail is configured; model guardrails remain required.",
        )


def model_guardrail_check(values):
    deployment = az(
        "cognitiveservices",
        "account",
        "deployment",
        "show",
        "--name",
        needed(values, "AZURE_AI_ACCOUNT_NAME"),
        "--resource-group",
        needed(values, "AZURE_RESOURCE_GROUP"),
        "--deployment-name",
        needed(values, "AZURE_AI_MODEL_DEPLOYMENT_NAME"),
    )
    require(
        deployment["properties"].get("raiPolicyName") == "Microsoft.DefaultV2",
        "The model must retain its verified built-in Microsoft.DefaultV2 guardrail.",
    )


def inherit_model_guardrails(endpoint, current):
    require(
        current.get("policies") == {"rai_config": {"rai_policy_name": "Microsoft.Default"}},
        "Unexpected toolbox policy; do not overwrite another configured guardrail.",
    )
    # CLI beta.5 cannot update policies. The documented versions API preserves history.
    payload = {
        "description": "Public agenda tools; the agent inherits its model's built-in guardrails.",
        "tools": current["tools"],
        "skills": current["skills"],
    }
    return create_toolbox_version(endpoint, payload)


def create_toolbox_version(endpoint, payload):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as file:
        json.dump(payload, file)
        path = Path(file.name)
    try:
        created = az(
            "rest",
            "--method",
            "post",
            "--url",
            f"{endpoint}/toolboxes/{TOOLBOX}/versions?api-version=v1",
            "--resource",
            "https://ai.azure.com",
            "--headers",
            "Foundry-Features=Toolboxes=V1Preview,Skills=V1Preview",
            "--body",
            f"@{path}",
        )
    finally:
        path.unlink()
    require(
        isinstance(created.get("version"), str) and bool(created["version"]),
        "Toolbox migration returned no immutable version.",
    )
    return created


def repoint_owned_agenda(endpoint, current, connection_id, target, values):
    record = migration_record(values)
    require(
        needed(values, "AZURE_BACKEND_NAME") == record["new_backend"],
        "The replacement backend name does not match the approved private migration.",
    )
    old_target = https_url(record["old_origin"], origin=True) + "/mcp"
    check_toolbox_version(current, connection_id, old_target)
    require(
        target == https_url(needed(values, "BACKEND_ORIGIN"), origin=True) + "/mcp",
        "The new MCP target does not match provisioned replacement outputs.",
    )
    tools = json.loads(json.dumps(current["tools"]))
    tools[0]["server_url"] = target
    return create_toolbox_version(
        endpoint,
        {
            "description": "Approved private backend; public agenda remains read-only.",
            "tools": tools,
            "skills": current["skills"],
        },
    )


def publish():
    values = environment()
    endpoint = https_url(needed(values, "FOUNDRY_PROJECT_ENDPOINT"))
    model_guardrail_check(values)
    publish_skill(endpoint)
    connection_id, target = check_connection(values)
    listed = azd("ai", "toolbox", "list", "--project-endpoint", endpoint)
    require(isinstance(listed.get("toolboxes"), list), "Unexpected toolbox list response.")
    exists = any(item["name"] == TOOLBOX for item in listed["toolboxes"])
    if not exists:
        project_name = needed(values, "AZURE_AI_PROJECT_NAME")
        require(
            re.fullmatch(r"[A-Za-z0-9-]{3,32}", project_name),
            "Invalid Foundry project name for toolbox declaration.",
        )
        declaration = (
            (ROOT / "src/tools.yaml").read_text().replace("${AZURE_AI_PROJECT_NAME}", project_name)
        )
        require("${" not in declaration, "Unresolved toolbox declaration variable.")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as file:
            file.write(declaration)
            declaration_path = Path(file.name)
        try:
            azd(
                "ai",
                "toolbox",
                "create",
                TOOLBOX,
                "--from-file",
                str(declaration_path),
                "--project-endpoint",
                endpoint,
                "--no-prompt",
            )
        finally:
            declaration_path.unlink()
    else:
        shown = azd("ai", "toolbox", "show", TOOLBOX, "--project-endpoint", endpoint)
        current = shown["version"]
        old_target = current["tools"][0].get("server_url") if current.get("tools") else target
        check_toolbox_version(current, connection_id, old_target, complete=False)
        # Branch from the promoted version, not an unrelated unpublished draft.
        branch = current["version"]
        changed = False
        if current.get("policies"):
            current = inherit_model_guardrails(endpoint, current)
            branch = current["version"]
            changed = True
        if old_target != target:
            current = repoint_owned_agenda(endpoint, current, connection_id, target, values)
            branch = current["version"]
            changed = True
        if not current.get("tools"):
            added = azd(
                "ai",
                "toolbox",
                "connection",
                "add",
                TOOLBOX,
                connection_id.rsplit("/", 1)[-1],
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
        headers["Foundry-Features"] = "Toolboxes=V1Preview"
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
        if token is None:
            require(
                [tool["name"] for tool in tools] == ["get_event_agenda"],
                "Public backend exposed unexpected MCP tools.",
            )
        response = send("tools/call", {"name": agenda[0]["name"], "arguments": {}}, 3)
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
    try:
        with urlopen(origin + "/api/event", timeout=10) as response:
            event = json.load(response)
        sessions = event.get("sessions", [])
        require(bool(sessions), "The backend published no sessions.")
        session_id = quote(sessions[0]["id"], safe="")
        with urlopen(origin + f"/api/sessions/{session_id}/questions", timeout=15) as response:
            questions = json.load(response)
        require(
            isinstance(questions.get("items"), list) and "next_cursor" in questions,
            "The live storage read returned an invalid question page.",
        )
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(
            "Backend storage data path is unavailable; stop before frontend/agent rollout."
        ) from error
    print("PASS: real backend health, public MCP, and managed-identity storage read.")


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
    discover(endpoint, token=token, call_agenda=True)
    print("PASS: governed toolbox discovery. Runtime permissions are reconciled after deployment.")


def runtime_principals(agent):
    identity = agent.get("instance_identity")
    require(
        isinstance(identity, dict) and bool(identity.get("principal_id")),
        "Agent instance identity is unavailable; "
        "no project/account identity substitution is allowed.",
    )
    principal = UUID(identity["principal_id"])
    require(principal.int != 0, "The agent instance identity is not a valid principal.")
    require(
        str(principal) != (agent.get("blueprint") or {}).get("principal_id"),
        "A blueprint principal cannot substitute for the acting agent identity.",
    )
    return [str(principal)]


def runtime_rbac():
    values = environment()
    for attempt in range(12):
        agent = azd("ai", "agent", "show", AGENT)
        require(
            agent.get("status", "").lower() not in {"failed", "error"},
            "Hosted agent deployment failed.",
        )
        if (agent.get("instance_identity") or {}).get("principal_id"):
            break
        if attempt < 11:
            print("Waiting for the actual acting agent identity.", file=sys.stderr)
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
        "PASS: actual acting agent identity roles reconciled through azd Bicep; "
        "blueprint principals are not eligible for Azure RBAC. "
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
        "prepare-private-migration": prepare_private_migration,
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
