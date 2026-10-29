# Import the Loom cookie from an existing Chrome session

Approved in conversation: use Chrome 144+ with remote debugging enabled through
chrome://inspect/#remote-debugging, accept Chrome's connection prompt, import only
the Loom connect.sid cookie into Keychain, then disconnect. No separate profile,
Chrome restart, browser installation, or additional MCP tools.

Setup offers Chrome import or the existing manual password prompt. It explains
that Chrome grants broad debugging access, although this importer only enumerates
Loom tabs and reads cookies applicable to https://www.loom.com/. An open signed-in
Loom tab is required. Multiple browser contexts with Loom tabs are rejected rather
than guessing which account to import. No page scripts or browser writes occur.

Discover the local endpoint from Chrome Stable's DevToolsActivePort file. Only a
validated browser endpoint on 127.0.0.1 is accepted. Use a bounded, uncompressed
WebSocket connection implemented with the Python standard library to preserve the
existing two-dependency limit. Follow CDP Target.getTargets, attachToTarget, and
Network.getCookies with a fixed Loom URL. Close the connection on all exits.

Write the cookie directly through macOS Security.framework SecItemUpdate/Add;
do not put it in process arguments, environment, files, stdout, or errors. Runtime
MCP authentication continues using security find-generic-password. Failed browser
reads leave Keychain untouched; no deletion before updating an existing item.
Manual entry remains available after a failed import.

References:
- https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/advanced-usage.md
- https://chromedevtools.github.io/devtools-protocol/tot/Target/
- https://chromedevtools.github.io/devtools-protocol/tot/Network/#method-getCookies
- https://www.rfc-editor.org/rfc/rfc6455
- https://developer.apple.com/documentation/security/secitemupdate(_:_:)

Test boundaries: fake loopback Chrome for protocol/filtering/error cleanup;
setup tests for declined/failed imports and manual fallback. Verify native Keychain
writes with a temporary test item, never a real session value in test output.
Live browser import requires the user's Chrome permission; report that separately.
