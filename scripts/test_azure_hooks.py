"""Offline regression tests for deployment hooks; no Azure calls."""

import base64
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import azure_hooks as hooks


def assignments(*roles):
    return [
        {"roleDefinitionId": f"/providers/Microsoft.Authorization/roleDefinitions/{role}"}
        for role in roles
    ]


def toolbox_version():
    return {
        "version": "3",
        "tools": [
            {
                "type": "mcp",
                "server_label": hooks.CONNECTION,
                "project_connection_id": "/project/connections/event-agenda",
                "server_url": "https://backend.example/mcp",
            }
        ],
        "skills": [{"type": "skill_reference", "name": hooks.AGENT}],
        "policies": None,
    }


class CallerGateTests(unittest.TestCase):
    def test_network_capability_must_be_registered(self):
        hooks.check_network_feature({"properties": {"state": "Registered"}})
        for state in ("NotRegistered", "Pending", "Registering", None):
            with self.assertRaisesRegex(RuntimeError, "Stop before provisioning"):
                hooks.check_network_feature({"properties": {"state": state}})

    def test_provider_output_casing_is_normalized_at_the_boundary(self):
        updates, obsolete = hooks.canonical_output_updates(
            {"backenD_ORIGIN": "https://backend.example", "unrelatedCase": "unchanged"},
            {"BACKEND_ORIGIN"},
        )
        self.assertEqual(updates, {"BACKEND_ORIGIN": "https://backend.example"})
        self.assertEqual(obsolete, {"backenD_ORIGIN"})

    def test_conflicting_output_aliases_are_not_silently_selected(self):
        with self.assertRaisesRegex(RuntimeError, "Conflicting"):
            hooks.canonical_output_updates(
                {"BACKEND_ORIGIN": "https://old.example", "backenD_ORIGIN": "https://new.example"},
                {"BACKEND_ORIGIN"},
            )

    def test_azd_principal_mismatch_blocks_before_provision(self):
        claims = (
            base64.urlsafe_b64encode(
                json.dumps({"oid": "another-user", "tid": "approved-tenant"}).encode()
            )
            .decode()
            .rstrip("=")
        )
        with patch.object(hooks, "azd", return_value={"token": f"header.{claims}.signature"}):
            with self.assertRaisesRegex(RuntimeError, "different principals"):
                hooks.check_azd_identity("approved-user", "approved-tenant")

    def test_authorized_stable_ids(self):
        hooks.check_role_contract(
            assignments(hooks.OWNER, hooks.ACCOUNT_OWNER, hooks.PROJECT_MANAGER)
        )

    def test_owner_does_not_replace_foundry_roles(self):
        with self.assertRaisesRegex(RuntimeError, "Foundry"):
            hooks.check_role_contract(assignments(hooks.OWNER))

    def test_conditional_role_not_counted(self):
        roles = assignments(hooks.OWNER, hooks.ACCOUNT_OWNER, hooks.PROJECT_MANAGER)
        roles[0]["condition"] = "restricted"
        with self.assertRaisesRegex(RuntimeError, "No roles were granted"):
            hooks.check_role_contract(roles)

    def test_alternative_provisioning_contract(self):
        hooks.check_role_contract(
            assignments(hooks.CONTRIBUTOR, hooks.RBAC_ADMIN, hooks.FOUNDRY_OWNER)
        )

    def test_preflight_includes_groups_and_inheritance_without_writes(self):
        values = {
            "AZURE_SUBSCRIPTION_ID": "test-subscription",
            "AZURE_TENANT_ID": "test-tenant",
            "AZURE_LOCATION": "eastus2",
            "AZURE_RESOURCE_GROUP": "rg-geneva-companion-dev-eus2",
        }

        def azure(*args):
            if args[:2] == ("account", "show"):
                return {"tenantId": "test-tenant", "user": {"type": "user"}}
            if args[:2] == ("ad", "signed-in-user"):
                return {"id": "test-principal"}
            if args[:3] == ("role", "assignment", "list"):
                self.assertIn("--include-groups", args)
                self.assertIn("--include-inherited", args)
                return assignments(hooks.OWNER, hooks.ACCOUNT_OWNER, hooks.PROJECT_MANAGER)
            if args[:3] == ("role", "definition", "list"):
                role = args[-1]
                return [{"name": role, "roleName": hooks.ROLE_NAMES[role]}]
            if args[:2] == ("feature", "show"):
                self.assertIn("AllowBringYourOwnPublicIpAddress", args)
                return {"properties": {"state": "Registered"}}
            self.fail(f"Unexpected or mutating Azure command: {args}")

        with (
            patch.object(hooks, "environment", return_value=values),
            patch.object(hooks, "check_azd_identity"),
            patch.object(hooks, "az", side_effect=azure),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            hooks.preflight()

    def test_azd_always_uses_inline_user_agent(self):
        with patch.object(hooks, "run", return_value="{}") as run:
            hooks.azd("env", "get-values")
        self.assertEqual(
            run.call_args.args[:3],
            ("env", "AZURE_DEV_USER_AGENT=microsoft_foundry_skill", "azd"),
        )


class PublicationTests(unittest.TestCase):
    def test_backend_readiness_requires_real_storage_access(self):
        class Response(io.BytesIO):
            status = 200

        with (
            patch.object(
                hooks,
                "urlopen",
                side_effect=[
                    Response(b"{}"),
                    Response(b'{"sessions":[{"id":"session"}]}'),
                    HTTPError("https://backend.example/api/questions", 503, "blocked", {}, None),
                ],
            ),
            patch.object(hooks, "discover"),
        ):
            with self.assertRaisesRegex(RuntimeError, "storage data path"):
                hooks.backend_ready({"BACKEND_ORIGIN": "https://backend.example"})

    def test_backend_readiness_accepts_valid_storage_page(self):
        class Response(io.BytesIO):
            status = 200

        with (
            patch.object(
                hooks,
                "urlopen",
                side_effect=[
                    Response(b"{}"),
                    Response(b'{"sessions":[{"id":"session"}]}'),
                    Response(b'{"items":[],"next_cursor":null}'),
                ],
            ),
            patch.object(hooks, "discover") as discover,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            hooks.backend_ready({"BACKEND_ORIGIN": "https://backend.example"})
        discover.assert_called_once_with("https://backend.example/mcp", call_agenda=True)

    def test_owned_endpoint_migration_preserves_tools_and_skill_history(self):
        current = toolbox_version()
        record = {"old_origin": "https://backend.example", "new_backend": "api-private-demo"}
        values = {
            "AZURE_BACKEND_NAME": "api-private-demo",
            "BACKEND_ORIGIN": "https://private-backend.example",
        }
        with (
            patch.object(hooks, "migration_record", return_value=record),
            patch.object(hooks, "create_toolbox_version", return_value={"version": "4"}) as create,
        ):
            migrated = hooks.repoint_owned_agenda(
                "https://project.example",
                current,
                "/project/connections/event-agenda",
                "https://private-backend.example/mcp",
                values,
            )
        self.assertEqual(migrated["version"], "4")
        body = create.call_args.args[1]
        self.assertEqual(body["tools"][0]["server_url"], "https://private-backend.example/mcp")
        self.assertEqual(body["skills"], current["skills"])
        self.assertEqual(current["tools"][0]["server_url"], "https://backend.example/mcp")

    def test_private_migration_clears_only_changed_outputs_and_retains_old_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = root / ".azure" / "demo"
            env.mkdir(parents=True)
            env_file = env / ".env"
            env_file.write_text("BACKEND_ORIGIN=https://backend.example\nPRESERVE=unchanged\n")
            values = {
                "AZURE_ENV_NAME": "demo",
                "AZURE_SUBSCRIPTION_ID": "subscription",
                "AZURE_TENANT_ID": "tenant",
                "AZURE_RESOURCE_GROUP": "group",
                "AZURE_BACKEND_NAME": "api-aaaaaaaaaaaaa",
                "AZURE_CONTAINER_ENVIRONMENT_NAME": "cae-aaaaaaaaaaaaa",
                "BACKEND_ORIGIN": "https://backend.example",
            }
            with (
                patch.object(hooks, "ROOT", root),
                patch.object(hooks, "environment", return_value=values),
                patch.object(hooks, "save") as save,
                patch("sys.stdout", new_callable=io.StringIO),
            ):
                hooks.prepare_private_migration()
            record = json.loads((env / "private-connectivity-migration.json").read_text())
            self.assertEqual(record["old_backend"], "api-aaaaaaaaaaaaa")
            self.assertEqual(record["new_backend"], "api-private-aaaaaaaaaaaaa")
            self.assertEqual(env_file.read_text(), "PRESERVE=unchanged\n")
            self.assertIn(
                ("AZURE_BACKEND_NAME", "api-private-aaaaaaaaaaaaa"),
                [call.args for call in save.call_args_list],
            )

    def test_model_guardrail_is_required_even_without_toolbox_override(self):
        values = {
            "AZURE_AI_ACCOUNT_NAME": "account",
            "AZURE_RESOURCE_GROUP": "group",
            "AZURE_AI_MODEL_DEPLOYMENT_NAME": "model",
        }
        with patch.object(
            hooks, "az", return_value={"properties": {"raiPolicyName": "Microsoft.DefaultV2"}}
        ):
            hooks.model_guardrail_check(values)
        with patch.object(hooks, "az", return_value={"properties": {}}):
            with self.assertRaisesRegex(RuntimeError, "built-in"):
                hooks.model_guardrail_check(values)

    def test_legacy_toolbox_override_migrates_without_deleting_history(self):
        current = toolbox_version()
        current["policies"] = {"rai_config": {"rai_policy_name": "Microsoft.Default"}}

        def create(*args):
            self.assertEqual(args[:3], ("rest", "--method", "post"))
            self.assertNotIn("delete", args)
            body = json.loads(Path(args[args.index("--body") + 1][1:]).read_text())
            self.assertEqual(body["tools"], current["tools"])
            self.assertEqual(body["skills"], current["skills"])
            self.assertNotIn("policies", body)
            return {"version": "2", **body}

        with patch.object(hooks, "az", side_effect=create):
            self.assertEqual(
                hooks.inherit_model_guardrails("https://project.example", current)["version"], "2"
            )
        current["policies"] = {"rai_config": {"rai_policy_name": "someone-elses-policy"}}
        with self.assertRaisesRegex(RuntimeError, "Unexpected"):
            hooks.inherit_model_guardrails("https://project.example", current)

    def test_bundle_hash_includes_asset_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text("skill")
            first = hooks.tree_digest(root)
            (root / "agenda.txt").write_text("public")
            self.assertNotEqual(first, hooks.tree_digest(root))

    def test_skill_update_preserves_history_and_identical_content_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "skills" / hooks.AGENT
            local.mkdir(parents=True)
            (local / "SKILL.md").write_text("new skill")
            calls = []

            def cli(*args, **kwargs):
                calls.append(args)
                if args[:3] == ("ai", "skill", "list"):
                    return [{"name": hooks.AGENT}]
                if args[:3] == ("ai", "skill", "download"):
                    destination = Path(args[args.index("--output-dir") + 1])
                    (destination / "SKILL.md").write_text("old skill")
                return {}

            with patch.object(hooks, "ROOT", root), patch.object(hooks, "azd", side_effect=cli):
                hooks.publish_skill("https://foundry.example")
            self.assertTrue(any(command[:3] == ("ai", "skill", "update") for command in calls))
            self.assertFalse(any("--force" in command or "delete" in command for command in calls))

            (local / "SKILL.md").write_text("old skill")
            calls.clear()
            with patch.object(hooks, "ROOT", root), patch.object(hooks, "azd", side_effect=cli):
                hooks.publish_skill("https://foundry.example")
            self.assertFalse(any(command[:3] == ("ai", "skill", "update") for command in calls))

    def test_valid_toolbox_and_no_unrelated_tools(self):
        version = toolbox_version()
        hooks.check_toolbox_version(
            version, "/project/connections/event-agenda", "https://backend.example/mcp"
        )
        version["tools"].append({"type": "web_search"})
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            hooks.check_toolbox_version(
                version, "/project/connections/event-agenda", "https://backend.example/mcp"
            )

    def test_target_drift_and_pinned_skill_fail_closed(self):
        for mutate in (
            lambda version: version["tools"][0].update(server_url="https://other.example/mcp"),
            lambda version: version["skills"][0].update(version="1"),
            lambda version: version.update(
                policies={"rai_config": {"rai_policy_name": "unapproved-custom-policy"}}
            ),
        ):
            version = toolbox_version()
            mutate(version)
            with self.assertRaises(RuntimeError):
                hooks.check_toolbox_version(
                    version, "/project/connections/event-agenda", "https://backend.example/mcp"
                )

    def test_repeat_publication_avoids_immutable_version_churn(self):
        endpoint = "https://foundry.example/api/projects/geneva"
        shown = {
            "version": toolbox_version(),
            "endpoint": endpoint + "/toolboxes/event-companion/versions/3/mcp?api-version=v1",
        }
        calls = []

        def cli(*args, **kwargs):
            calls.append(args)
            if args[:3] == ("ai", "toolbox", "list"):
                return {"toolboxes": [{"name": hooks.TOOLBOX}]}
            if args[:3] == ("ai", "toolbox", "show"):
                return shown
            self.fail(f"Unexpected mutation: {args}")

        with (
            patch.object(hooks, "environment", return_value={"FOUNDRY_PROJECT_ENDPOINT": endpoint}),
            patch.object(hooks, "publish_skill"),
            patch.object(
                hooks,
                "check_connection",
                return_value=("/project/connections/event-agenda", "https://backend.example/mcp"),
            ),
            patch.object(hooks, "azd", side_effect=cli),
            patch.object(hooks, "save") as save,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            with patch.object(hooks, "model_guardrail_check"):
                hooks.publish()
        save.assert_called_once_with("TOOLBOX_EVENT_COMPANION_MCP_ENDPOINT", shown["endpoint"])
        self.assertFalse(any("create" in call or "publish" in call for call in calls))

    def test_publication_order_does_not_probe_unstarted_backend(self):
        endpoint = "https://foundry.example/api/projects/geneva"
        operations = []

        def cli(*args, **kwargs):
            if args[:3] == ("ai", "toolbox", "list"):
                return {"toolboxes": []}
            if args[:3] == ("ai", "toolbox", "create"):
                declaration = Path(args[args.index("--from-file") + 1]).read_text()
                self.assertIn("geneva-event-agenda", declaration)
                self.assertNotIn("${", declaration)
                operations.append("toolbox")
                return {}
            if args[:3] == ("ai", "toolbox", "show"):
                return {
                    "version": toolbox_version(),
                    "endpoint": endpoint
                    + "/toolboxes/event-companion/versions/1/mcp?api-version=v1",
                }
            self.fail(f"Unexpected command: {args}")

        def connection(_):
            operations.append("connection")
            return "/project/connections/event-agenda", "https://backend.example/mcp"

        with (
            patch.object(
                hooks,
                "environment",
                return_value={
                    "FOUNDRY_PROJECT_ENDPOINT": endpoint,
                    "AZURE_AI_PROJECT_NAME": "geneva",
                },
            ),
            patch.object(hooks, "publish_skill", side_effect=lambda _: operations.append("skill")),
            patch.object(hooks, "check_connection", side_effect=connection),
            patch.object(hooks, "azd", side_effect=cli),
            patch.object(hooks, "save"),
            patch.object(hooks, "discover") as discover,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            with patch.object(hooks, "model_guardrail_check"):
                hooks.publish()
        self.assertEqual(operations, ["skill", "connection", "toolbox"])
        discover.assert_not_called()


class ReadinessTests(unittest.TestCase):
    def test_frontend_predeploy_rebuild_overrides_stale_environment(self):
        origin = "https://current-backend.example"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontend = root / "src" / "frontend"
            assets = frontend / "dist" / "assets"
            assets.mkdir(parents=True)
            (frontend / "dist" / "index.html").write_text(
                '<script type="module" src="/assets/index.js"></script>'
            )
            bundle = assets / "index.js"
            bundle.write_text('const base = "https://stale-backend.example";')

            def build(command, **kwargs):
                self.assertEqual(command, ["npm", "run", "build"])
                self.assertEqual(kwargs["cwd"], frontend)
                self.assertEqual(kwargs["env"]["VITE_API_BASE_URL"], origin)
                self.assertTrue(kwargs["check"])
                bundle.write_text(f'const base = "{origin}";')

            with (
                patch.object(hooks, "ROOT", root),
                patch.object(
                    hooks,
                    "environment",
                    return_value={"VITE_API_BASE_URL": origin, "BACKEND_ORIGIN": origin},
                ),
                patch.dict(hooks.os.environ, {"VITE_API_BASE_URL": "https://stale-shell.example"}),
                patch.object(hooks.subprocess, "run", side_effect=build) as run,
                patch("sys.stdout", new_callable=io.StringIO),
            ):
                hooks.frontend_package()
            run.assert_called_once()
            self.assertIn(origin, bundle.read_text())

    def test_frontend_gate_rejects_stale_entry_even_with_unused_correct_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text('<script type="module" src="/entry.js"></script>')
            (root / "entry.js").write_text('const base = "https://stale.example";')
            (root / "unused.js").write_text('const base = "https://current.example";')
            with self.assertRaisesRegex(RuntimeError, "refusing upload"):
                hooks.verify_frontend_assets(root, "https://current.example")

    def test_frontend_gate_rejects_missing_provisioning_outputs_before_build(self):
        with (
            patch.object(hooks, "environment", return_value={}),
            patch.object(hooks.subprocess, "run") as build,
        ):
            with self.assertRaisesRegex(RuntimeError, "Missing VITE_API_BASE_URL"):
                hooks.frontend_package()
        build.assert_not_called()

    def test_runtime_reconciliation_provisions_only_role_layer(self):
        principals = [
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ]
        agent = {
            "status": "active",
            "instance_identity": {"principal_id": principals[0]},
            "blueprint": {"principal_id": principals[1]},
        }
        calls = []

        def cli(*args, **kwargs):
            calls.append(args)
            if args[:3] == ("ai", "agent", "show"):
                return agent
            self.assertEqual(args, ("provision", "runtime-rbac", "--no-prompt"))
            return ""

        with (
            patch.object(
                hooks,
                "environment",
                return_value={"AZURE_AI_PROJECT_ID": "/account/projects/geneva"},
            ),
            patch.object(hooks, "azd", side_effect=cli),
            patch.object(
                hooks,
                "az",
                return_value={"identity": {"principalId": "33333333-3333-4333-8333-333333333333"}},
            ) as azure,
            patch.object(hooks, "save") as save,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            hooks.runtime_rbac()
        save.assert_called_once_with("AGENT_RUNTIME_PRINCIPAL_IDS", principals[0])
        self.assertEqual(calls[-1], ("provision", "runtime-rbac", "--no-prompt"))
        self.assertTrue(all(call.args[:2] == ("resource", "show") for call in azure.call_args_list))

    def test_json_and_sse_mcp_responses(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26"}})
        for value, kind in (
            (body, "application/json"),
            ("event: message\ndata: " + body + "\n\n", "text/event-stream"),
        ):
            self.assertEqual(hooks.rpc_result(value, kind, 1)["protocolVersion"], "2025-03-26")

    def test_mcp_protocol_errors_are_not_success(self):
        with self.assertRaisesRegex(RuntimeError, "protocol error"):
            hooks.rpc_result('{"id":2,"error":{"code":-32603}}', "application/json", 2)

    def test_only_actual_runtime_identity_fields_accepted(self):
        instance = "11111111-1111-4111-8111-111111111111"
        blueprint = "22222222-2222-4222-8222-222222222222"
        self.assertEqual(
            hooks.runtime_principals(
                {
                    "instance_identity": {"principal_id": instance},
                    "blueprint": {"principal_id": blueprint},
                }
            ),
            [instance],
        )
        self.assertEqual(
            hooks.runtime_principals({"instance_identity": {"principal_id": instance}}),
            [instance],
        )
        for invalid in (
            {"identity": {"principalId": instance}},
            {"instance_identity": None, "blueprint": {"principal_id": blueprint}},
        ):
            with self.assertRaisesRegex(RuntimeError, "substitution"):
                hooks.runtime_principals(invalid)
        with self.assertRaisesRegex(RuntimeError, "blueprint"):
            hooks.runtime_principals(
                {
                    "instance_identity": {"principal_id": blueprint},
                    "blueprint": {"principal_id": blueprint},
                }
            )

    def test_frontend_origin_rejects_paths_and_credentials(self):
        for invalid in (
            "http://backend.example",
            "https://user:secret@backend.example",
            "https://backend.example/api",
        ):
            with self.assertRaises(RuntimeError):
                hooks.https_url(invalid, origin=True)

    def test_backend_gate_precedes_toolbox_discovery(self):
        with (
            patch.object(hooks, "environment", return_value={}),
            patch.object(hooks, "backend_ready", side_effect=RuntimeError("not ready")),
            patch.object(hooks, "discover") as discover,
        ):
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                hooks.agent_ready()
        discover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
