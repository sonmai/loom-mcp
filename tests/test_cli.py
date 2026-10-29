import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loom_mcp.executables import find_executable


class CliTests(unittest.TestCase):
    def test_help_is_available_without_starting_mcp(self):
        result = subprocess.run([sys.executable, "-m", "loom_mcp.cli", "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("setup", result.stdout)
        self.assertNotIn("jsonrpc", result.stdout)

    def test_setup_refuses_a_noninteractive_mcp_pipe(self):
        result = subprocess.run([sys.executable, "-m", "loom_mcp.cli", "setup"], input="", capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("interactive Terminal", result.stderr)

    def test_executable_lookup_supports_intel_and_path_and_ignores_nonexecutables(self):
        with patch("pathlib.Path.is_file", side_effect=lambda: True), patch(
            "os.access", side_effect=lambda path, mode: str(path) == "/usr/local/bin/ffmpeg"
        ):
            self.assertEqual(find_executable("ffmpeg"), "/usr/local/bin/ffmpeg")
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "ffmpeg"
            candidate.write_text("#!/bin/sh\nexit 0\n")
            candidate.chmod(0o700)
            with patch("pathlib.Path.is_file", return_value=False), patch.dict(os.environ, {"PATH": directory}):
                self.assertEqual(find_executable("ffmpeg"), str(candidate))
                candidate.chmod(0o600)
                self.assertIsNone(find_executable("ffmpeg"))


if __name__ == "__main__":
    unittest.main()
