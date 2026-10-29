import base64
import hashlib
import json
import os
import re
import socket
import struct
import time
from pathlib import Path
from urllib.parse import urlsplit

from loom_mcp.keychain import is_valid_session_cookie


class ChromeError(Exception):
    pass


def chrome_endpoint() -> Path:
    return Path.home() / 'Library/Application Support/Google/Chrome/DevToolsActivePort'


class ChromeConnection:
    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.deadline = time.monotonic() + 60
        self.sequence = 0

    def read(self, length: int) -> bytes:
        content = bytearray()
        while len(content) < length:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            self.connection.settimeout(remaining)
            chunk = self.connection.recv(length - len(content))
            if not chunk:
                raise ChromeError('Chrome disconnected. Allow the connection in Chrome and retry.')
            content.extend(chunk)
        return bytes(content)

    def handshake(self, port: int, path: str) -> None:
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        self.connection.sendall((
            f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
            'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
        ).encode('ascii'))
        response = bytearray()
        while not response.endswith(b'\r\n\r\n'):
            if len(response) >= 16384:
                raise ChromeError('Chrome returned an invalid connection response.')
            response.extend(self.read(1))
        lines = response.decode('ascii').split('\r\n')
        headers = dict(line.lower().split(':', 1) for line in lines[1:] if ':' in line)
        expected = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')
        ).digest()).decode('ascii')
        accept = next((line.split(':', 1)[1].strip() for line in lines[1:] if line.lower().startswith('sec-websocket-accept:')), '')
        if (lines[0].split()[:2] != ['HTTP/1.1', '101'] or accept != expected
                or headers.get('upgrade', '').strip() != 'websocket'
                or 'upgrade' not in headers.get('connection', '').strip().split(', ')
                or 'sec-websocket-extensions' in headers):
            raise ChromeError('Chrome refused the debugging connection. Click Allow in Chrome and retry.')

    def send(self, payload: bytes, opcode: int = 1) -> None:
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            prefix = bytes([128 | opcode, 128 | length])
        elif length < 65536:
            prefix = bytes([128 | opcode, 254]) + struct.pack('!H', length)
        else:
            prefix = bytes([128 | opcode, 255]) + struct.pack('!Q', length)
        self.connection.sendall(prefix + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload)))

    def receive(self) -> dict:
        content = bytearray()
        started = False
        while True:
            first, second = self.read(2)
            opcode, final = first & 15, bool(first & 128)
            length = second & 127
            if first & 112 or second & 128:
                raise ChromeError('Chrome returned an unsupported WebSocket frame.')
            if length == 126:
                length = struct.unpack('!H', self.read(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self.read(8))[0]
            if length + len(content) > 4 * 1024 * 1024:
                raise ChromeError('Chrome response exceeded the import size limit.')
            if opcode >= 8 and (not final or length > 125):
                raise ChromeError('Chrome returned an invalid control frame.')
            payload = self.read(length)
            if opcode == 8:
                raise ChromeError('Chrome closed the connection. Allow debugging and retry.')
            if opcode == 9:
                self.send(payload, 10)
                continue
            if opcode == 10:
                continue
            if opcode not in (0, 1) or (opcode == 0) != started:
                raise ChromeError('Chrome returned an unexpected WebSocket message.')
            started = True
            content.extend(payload)
            if final:
                result = json.loads(content)
                if not isinstance(result, dict):
                    raise ChromeError('Chrome returned an unexpected protocol response.')
                return result

    def call(self, method: str, parameters: dict | None = None, session: str | None = None) -> dict:
        self.sequence += 1
        message = {'id': self.sequence, 'method': method, 'params': parameters or {}}
        if session:
            message['sessionId'] = session
        self.send(json.dumps(message).encode())
        while True:
            response = self.receive()
            if response.get('id') != self.sequence:
                continue
            if 'error' in response or not isinstance(response.get('result'), dict):
                raise ChromeError('Chrome could not read the Loom session. Check permission and retry.')
            return response['result']


def read_chrome_cookie() -> str:
    try:
        endpoint = chrome_endpoint().read_text().splitlines()
        if len(endpoint) != 2 or not endpoint[0].isascii() or not endpoint[0].isdigit():
            raise ValueError
        port = int(endpoint[0])
        if not 1 <= port <= 65535 or not re.fullmatch(r'/devtools/browser/[A-Za-z0-9-]+', endpoint[1]):
            raise ValueError
        with socket.create_connection(('127.0.0.1', port), timeout=60) as connection:
            chrome = ChromeConnection(connection)
            chrome.handshake(port, endpoint[1])
            try:
                targets = chrome.call('Target.getTargets')['targetInfos']
                tabs = [target for target in targets if target.get('type') == 'page'
                        and urlsplit(target.get('url', '')).scheme == 'https'
                        and urlsplit(target.get('url', '')).hostname in {'loom.com', 'www.loom.com'}]
                if not tabs:
                    raise ChromeError('Open a signed-in https://www.loom.com tab in Chrome, then retry.')
                if len({tab.get('browserContextId', '') for tab in tabs}) != 1:
                    raise ChromeError('Loom is open in multiple browser contexts. Keep one Loom context open and retry.')
                session = chrome.call('Target.attachToTarget', {'targetId': tabs[0]['targetId'], 'flatten': True})['sessionId']
                cookies = chrome.call('Network.getCookies', {'urls': ['https://www.loom.com/']}, session)['cookies']
                values = {cookie['value'] for cookie in cookies
                          if cookie.get('name') == 'connect.sid'
                          and cookie.get('domain') in {'loom.com', '.loom.com', 'www.loom.com', '.www.loom.com'}
                          and cookie.get('path') == '/'}
                if len(values) != 1:
                    raise ChromeError('No unique Loom session was found. Sign in to Loom in Chrome and retry.')
                value = values.pop()
                if not is_valid_session_cookie(value):
                    raise ChromeError('Chrome returned an invalid Loom session cookie.')
                return value
            finally:
                try:
                    chrome.send(struct.pack('!H', 1000), 8)
                except OSError:
                    pass
    except ChromeError:
        raise
    except FileNotFoundError:
        raise ChromeError('Open Chrome 144+ and enable chrome://inspect/#remote-debugging, then retry.') from None
    except (TimeoutError, ConnectionError):
        raise ChromeError('Chrome connection timed out or was denied. Click Allow in Chrome and retry.') from None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise ChromeError('Cannot read the Chrome session. Check remote debugging or use manual cookie entry.') from None
