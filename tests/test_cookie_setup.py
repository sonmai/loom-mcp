import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

from loom_mcp.chrome import ChromeError
from loom_mcp.setup import setup_cookie


class CookieSetupTests(unittest.TestCase):
    def test_chrome_import_saves_without_printing_cookie_or_using_manual_prompt(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('loom_mcp.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 1)), patch(
            'builtins.input', side_effect=['1', 'y']
        ), patch('loom_mcp.setup.read_chrome_cookie', return_value='private-session') as read, patch(
            'loom_mcp.setup.store_cookie'
        ) as store, patch('loom_mcp.setup.save_cookie') as manual:
            self.assertTrue(setup_cookie())
        read.assert_called_once()
        store.assert_called_once_with('private-session')
        manual.assert_not_called()
        self.assertNotIn('private-session', output.getvalue())

    def test_browser_failure_can_fall_back_without_saving_a_browser_cookie(self):
        with contextlib.redirect_stdout(io.StringIO()), patch('loom_mcp.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 1)), patch(
            'builtins.input', side_effect=['1', 'y', 'y', 'y']
        ), patch('loom_mcp.setup.read_chrome_cookie', side_effect=ChromeError('No Loom session')), patch(
            'loom_mcp.setup.store_cookie'
        ) as store, patch('loom_mcp.setup.save_cookie') as manual:
            self.assertTrue(setup_cookie())
        store.assert_not_called()
        manual.assert_called_once()

    def test_declining_browser_connection_does_not_access_session_or_keychain(self):
        with contextlib.redirect_stdout(io.StringIO()), patch('loom_mcp.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 1)), patch(
            'builtins.input', side_effect=['1', 'n']
        ), patch('loom_mcp.setup.read_chrome_cookie') as read, patch('loom_mcp.setup.store_cookie') as store:
            self.assertFalse(setup_cookie())
        read.assert_not_called()
        store.assert_not_called()
