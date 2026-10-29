import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loom_mcp.setup import CLIENTS, SetupError, register_client, save_cookie, run_setup


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.executable = self.home / "bin with spaces" / "loom-mcp"
        self.client = next(client for client in CLIENTS if client.name == "Cursor")
        self.config = self.home / self.client.config
        self.config.parent.mkdir(parents=True)

    def test_registration_preserves_settings_and_repeat_setup_does_not_rewrite(self):
        original = '{"theme":"dark", "mcpServers":{"other":{"command":"existing"}}}\n'
        self.config.write_text(original)
        register_client(self.client, self.executable, self.home, lambda _: False)
        value = json.loads(self.config.read_text())
        self.assertEqual(value, {
            "theme": "dark", "mcpServers": {
                "other": {"command": "existing"},
                "loom": {"command": str(self.executable)},
            },
        })
        backups = list(self.config.parent.glob("mcp.json.*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        before = self.config.stat().st_mtime_ns
        register_client(self.client, self.executable, self.home, lambda _: self.fail("Unexpected prompt"))
        self.assertEqual(self.config.stat().st_mtime_ns, before)
        self.assertEqual(list(self.config.parent.glob("mcp.json.*.bak")), backups)

    def test_declined_conflict_preserves_the_original_bytes(self):
        original = '{"mcpServers": {"loom": {"command": "different-server"}}}'
        self.config.write_text(original)
        register_client(self.client, self.executable, self.home, lambda _: False)
        self.assertEqual(self.config.read_text(), original)
        self.assertEqual(list(self.config.parent.glob("*.bak")), [])

    def test_malformed_configs_are_never_replaced(self):
        for original in ('{ // comments\n}', '[]', '{"mcpServers": []}'):
            with self.subTest(original=original):
                self.config.write_text(original)
                with self.assertRaises(SetupError):
                    register_client(self.client, self.executable, self.home, lambda _: True)
                self.assertEqual(self.config.read_text(), original)

    def test_approved_replacement_preserves_other_servers_and_backups(self):
        original = {"mcpServers": {"loom": {"command": "old"}, "other": {"command": "keep"}}}
        self.config.write_text(json.dumps(original))
        register_client(self.client, self.executable, self.home, lambda _: True)
        result = json.loads(self.config.read_text())
        self.assertEqual(result["mcpServers"]["loom"], {"command": str(self.executable)})
        self.assertEqual(result["mcpServers"]["other"], {"command": "keep"})
        self.assertEqual(json.loads(next(self.config.parent.glob("*.bak")).read_text()), original)

    def test_cli_failure_does_not_leak_configuration_or_report_success(self):
        client = next(client for client in CLIENTS if client.name == "Codex CLI")
        config = self.home / client.config
        config.parent.mkdir(parents=True)
        original = 'model = "keep"\n[mcp_servers.other]\ncommand = "keep"\n'
        config.write_text(original)
        with patch("loom_mcp.setup.find_executable", return_value="/bin/fake"), patch(
            "loom_mcp.setup.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, stdout="private", stderr="private"),
        ):
            with self.assertRaises(SetupError) as raised:
                register_client(client, self.executable, self.home, lambda _: True)
        self.assertNotIn("private", str(raised.exception))
        self.assertEqual(config.read_text(), original)
        self.assertEqual(next(config.parent.glob("*.bak")).read_text(), original)

    def test_cookie_is_entered_by_security_without_capture_or_password_argument(self):
        with patch("loom_mcp.setup.subprocess.run") as run:
            run.return_value.returncode = 0
            save_cookie()
        arguments, options = run.call_args
        self.assertEqual(arguments[0], [
            "/usr/bin/security", "add-generic-password", "-U", "-s", "loom-mcp",
            "-a", "connect.sid", "-w",
        ])
        self.assertNotIn("capture_output", options)
        self.assertNotIn("input", options)
        self.assertNotIn("env", options)

    def test_cancelled_wizard_does_not_read_keychain_or_touch_configs(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), patch(
            "builtins.input", return_value=""
        ), patch("loom_mcp.setup.subprocess.run") as run:
            self.assertEqual(run_setup(self.executable), 0)
        run.assert_not_called()
        self.assertFalse(self.config.exists())

    def test_existing_native_stdio_entry_is_already_configured(self):
        client = next(client for client in CLIENTS if client.name == "Claude Code")
        config = self.home / client.config
        original = json.dumps({"mcpServers": {"loom": {
            "type": "stdio", "command": str(self.executable), "args": [], "env": {},
        }}})
        config.write_text(original)
        with patch("loom_mcp.setup.subprocess.run") as run:
            register_client(client, self.executable, self.home, lambda _: self.fail("Unexpected replacement"))
        run.assert_not_called()
        self.assertEqual(config.read_text(), original)

    def test_failed_claude_replacement_restores_entry_and_keeps_concurrent_changes(self):
        client = next(client for client in CLIENTS if client.name == "Claude Code")
        config = self.home / client.config
        config.write_text('{"other": 1, "mcpServers": {"loom": {"command": "old"}}}')
        def run(arguments, **options):
            if "remove" in arguments:
                config.write_text('{"other": 1, "mcpServers": {}}')
                return subprocess.CompletedProcess(arguments, 0)
            config.write_text('{"other": 2, "mcpServers": {}}')
            return subprocess.CompletedProcess(arguments, 1)
        with patch("loom_mcp.setup.find_executable", return_value="/bin/fake"), patch(
            "loom_mcp.setup.subprocess.run", side_effect=run
        ):
            with self.assertRaisesRegex(SetupError, "registration failed"):
                register_client(client, self.executable, self.home, lambda _: True)
        self.assertEqual(json.loads(config.read_text()), {"other": 2, "mcpServers": {"loom": {"command": "old"}}})

    def test_unparsable_config_still_registers_through_client_cli_after_approval(self):
        client = next(client for client in CLIENTS if client.name == "VS Code")
        config = self.home / client.config
        config.parent.mkdir(parents=True)
        original = '{ // JSONC comment\n  "servers": {}\n}\n'
        config.write_text(original)
        with patch("loom_mcp.setup.find_executable", return_value="/bin/fake"), patch(
            "loom_mcp.setup.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            self.assertTrue(register_client(client, self.executable, self.home, lambda _: True).startswith("Configured"))
        self.assertIn("--add-mcp", run.call_args.args[0])
        self.assertEqual(config.read_text(), original)

    def test_custom_cli_config_roots_are_rejected_before_registration(self):
        overrides = {"claude": "CLAUDE_CONFIG_DIR", "codex": "CODEX_HOME", "gemini": "GEMINI_CLI_HOME"}
        cases = [(client, str(self.home / "custom")) for client in CLIENTS if client.command in overrides]
        cases.append((next(client for client in CLIENTS if client.command == "claude"), ""))
        for client, directory in cases:
            with self.subTest(client=client.name, directory=directory), patch(
                "loom_mcp.setup.os.getenv", side_effect=lambda key: directory if key == overrides[client.command] else None
            ), patch("loom_mcp.setup.find_executable", return_value="/bin/fake"), patch(
                "loom_mcp.setup.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
            ) as run:
                with self.assertRaises(SetupError):
                    register_client(client, self.executable, self.home, lambda _: True)
                run.assert_not_called()
                self.assertFalse((self.home / client.config).exists())


if __name__ == "__main__":
    unittest.main()
