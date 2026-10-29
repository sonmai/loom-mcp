import base64
import hashlib
import json
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from loom_mcp.chrome import ChromeDebuggingOff, ChromeError, read_chrome_cookie


class ChromeTests(unittest.TestCase):
    def test_import_reads_only_loom_and_disconnects_on_success_or_error(self):
        for scenario in ('success', 'denied', 'ambiguous', 'missing', 'oversized'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                endpoint = Path(directory) / 'DevToolsActivePort'
                endpoint.write_text('12345\n/devtools/browser/test-id\n')
                connection, peer = socket.socketpair()
                self.addCleanup(connection.close)
                self.addCleanup(peer.close)
                peer.settimeout(2)
                requests, errors = [], []

                def serve():
                    try:
                        with peer.makefile('rb', buffering=0) as stream:
                            headers = b''
                            while not headers.endswith(b'\r\n\r\n'):
                                headers += stream.read(1)
                            key = next(line.split(b': ', 1)[1] for line in headers.split(b'\r\n') if line.startswith(b'Sec-WebSocket-Key:'))
                            accept = base64.b64encode(hashlib.sha1(key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                            peer.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
                            while True:
                                header = stream.read(2)
                                if not header or header[0] & 15 == 8:
                                    break
                                self.assertTrue(header[1] & 128)
                                length = header[1] & 127
                                if length == 126:
                                    length = struct.unpack('!H', stream.read(2))[0]
                                mask = stream.read(4)
                                payload = bytearray()
                                while len(payload) < length:
                                    payload.extend(stream.read(length - len(payload)))
                                request = json.loads(bytes(value ^ mask[index % 4] for index, value in enumerate(payload)))
                                requests.append(request)
                                if scenario == 'oversized':
                                    peer.sendall(bytes([129, 127]) + struct.pack('!Q', 4 * 1024 * 1024 + 1))
                                    continue
                                method = request['method']
                                if scenario == 'denied':
                                    response = {'id': request['id'], 'error': {'message': 'secret-must-not-leak'}}
                                else:
                                    if method == 'Target.getTargets':
                                        targets = [{'targetId': 'loom', 'type': 'page', 'url': 'https://www.loom.com/home', 'browserContextId': 'a'},
                                                   {'targetId': 'other', 'type': 'page', 'url': 'https://example.com'}]
                                        if scenario == 'ambiguous':
                                            targets.append(dict(targets[0], targetId='second', browserContextId='b'))
                                        result = {'targetInfos': targets}
                                    elif method == 'Target.attachToTarget':
                                        self.assertEqual(request['params'], {'targetId': 'loom', 'flatten': True})
                                        result = {'sessionId': 'session'}
                                    else:
                                        self.assertEqual(method, 'Network.getCookies')
                                        self.assertEqual(request['sessionId'], 'session')
                                        self.assertEqual(request['params'], {'urls': ['https://www.loom.com/']})
                                        cookies = [{'name': 'connect.sid', 'domain': 'evil-loom.com', 'value': 'wrong'},
                                                   {'name': 'unrelated', 'domain': '.loom.com', 'value': 'wrong'}]
                                        if scenario == 'success':
                                            cookies.append({'name': 'connect.sid', 'domain': '.loom.com', 'path': '/', 'value': 'test-session'})
                                        result = {'cookies': cookies}
                                    response = {'id': request['id'], 'result': result}
                                payload = json.dumps(response).encode()
                                split = len(payload) // 2
                                for opcode, part in ((1, payload[:split]), (128, payload[split:])):
                                    prefix = bytes([opcode, len(part)]) if len(part) < 126 else bytes([opcode, 126]) + struct.pack('!H', len(part))
                                    peer.sendall(prefix + part)
                    except Exception as error:
                        errors.append(error)

                worker = threading.Thread(target=serve, daemon=True)
                worker.start()
                with patch('loom_mcp.chrome.chrome_endpoint', return_value=endpoint), patch('socket.create_connection', return_value=connection):
                    if scenario == 'success':
                        self.assertEqual(read_chrome_cookie(), 'test-session')
                    else:
                        with self.assertRaises(ChromeError) as raised:
                            read_chrome_cookie()
                        self.assertNotIn('secret-must-not-leak', str(raised.exception))
                worker.join(3)
                self.assertFalse(worker.is_alive(), 'Importer did not disconnect')
                self.assertEqual(errors, [])
                self.assertTrue(requests)

    def test_refused_or_missing_endpoint_reports_debugging_off(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / 'DevToolsActivePort'
            with patch('loom_mcp.chrome.chrome_endpoint', return_value=endpoint), self.assertRaises(ChromeDebuggingOff):
                read_chrome_cookie()
            endpoint.write_text('9222\n/devtools/browser/stale-id\n')
            with patch('loom_mcp.chrome.chrome_endpoint', return_value=endpoint), patch(
                'socket.create_connection', side_effect=ConnectionRefusedError
            ), self.assertRaises(ChromeDebuggingOff) as raised:
                read_chrome_cookie()
            self.assertNotIn('Allow', str(raised.exception))

    def test_invalid_endpoint_is_rejected_before_connecting(self):
        for value in ('443\nhttps://example.com\n', '0\n/devtools/browser/test\n', '123\n/devtools/browser/test\r\nInjected: yes\n'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                endpoint = Path(directory) / 'endpoint'
                endpoint.write_text(value)
                with patch('loom_mcp.chrome.chrome_endpoint', return_value=endpoint), patch('socket.create_connection') as connect:
                    with self.assertRaises(ChromeError):
                        read_chrome_cookie()
                    connect.assert_not_called()
