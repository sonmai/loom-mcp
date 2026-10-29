import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

from loom_mcp.chrome import REMOTE_DEBUGGING_PAGE, ChromeDebuggingOff, ChromeError
from loom_mcp.keychain import KeychainError, store_cookie
from loom_mcp.setup import setup_cookie


class CookieSetupTests(unittest.TestCase):
    def test_chrome_import_saves_without_printing_cookie_or_using_manual_prompt(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('loom_mcp.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 1)), patch(
            'builtins.input', side_effect=['1', 'y']
        ), patch('loom_mcp.setup.open_in_chrome'), patch('loom_mcp.setup.read_chrome_cookie', return_value='private-session') as read, patch(
            'loom_mcp.setup.store_cookie'
        ) as store, patch('loom_mcp.setup.save_cookie') as manual:
            self.assertTrue(setup_cookie())
        read.assert_called_once()
        store.assert_called_once_with('private-session')
        manual.assert_not_called()
        self.assertNotIn('private-session', output.getvalue())

    def test_debugging_off_opens_chrome_settings_and_retries_the_import(self):
        with contextlib.redirect_stdout(io.StringIO()), patch('loom_mcp.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 1)), patch(
            'builtins.input', side_effect=['1', 'y', 'y', '']
        ), patch('loom_mcp.setup.read_chrome_cookie', side_effect=[ChromeDebuggingOff('off'), 'private-session']), patch(
            'loom_mcp.setup.open_in_chrome'
        ) as open_in_chrome, patch('loom_mcp.setup.store_cookie') as store, patch('loom_mcp.setup.save_cookie') as manual:
            self.assertTrue(setup_cookie())
        open_in_chrome.assert_any_call(REMOTE_DEBUGGING_PAGE)
        store.assert_called_once_with('private-session')
        manual.assert_not_called()

    def test_browser_failure_can_fall_back_without_saving_a_browser_cookie(self):
        with contextlib.redirect_stdout(io.StringIO()), patch('loom_mcp.setup.subprocess.run', return_value=subprocess.CompletedProcess([], 1)), patch(
            'builtins.input', side_effect=['1', 'y', 'n', 'y', 'y']
        ), patch('loom_mcp.setup.open_in_chrome'), patch('loom_mcp.setup.read_chrome_cookie', side_effect=ChromeError('No Loom session')), patch(
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

    def test_imported_cookie_reaches_security_only_on_stdin(self):
        with patch('loom_mcp.keychain.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            store_cookie('s%3Aprivate.session')
        arguments, options = run.call_args
        self.assertEqual(arguments[0], ['/usr/bin/security', '-i'])
        self.assertIn('-w "s%3Aprivate.session"', options['input'])
        self.assertNotIn('env', options)
        with patch('loom_mcp.keychain.subprocess.run') as run:
            for value in ('a"b', "a'b", 'a\\b', 'connect.sid=abc', 'a;b'):
                with self.subTest(value=value), self.assertRaises(KeychainError):
                    store_cookie(value)
        run.assert_not_called()
