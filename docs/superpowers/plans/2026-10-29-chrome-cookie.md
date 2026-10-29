# Chrome Cookie Import Implementation Plan

**Goal:** Import a Loom cookie from the user's running Chrome into Keychain.
**Architecture:** Explicit setup-only CDP connection; standard-library WebSocket;
native Security.framework write; unchanged MCP tools and runtime authentication.
**Tech Stack:** Python standard library, macOS Security/CoreFoundation, Chrome CDP.

## Global constraints
- Exactly three existing MCP tools and two runtime dependencies.
- Chrome consent required; no remote hosts, browser database reads or page scripts.
- Cookie remains in memory and Keychain; fixed generic credential errors.
- User approved this design; ask before pushing.

## Tasks
- [x] Add focused tests for a loopback CDP peer: matching Loom cookie, unrelated
  cookie exclusion, permission denial, bounded protocol messages, and disconnect.
- [x] Implement `chrome.py`: `read_chrome_cookie() -> str`, validated endpoint,
  matching Loom tab/context, fixed Network.getCookies URL, secret-free errors.
- [x] Implement `keychain.py`: `store_cookie(cookie: str) -> None` with
  SecItemUpdate followed by SecItemAdd only on errSecItemNotFound. Use ctypes
  native bindings and release all owned CF objects. No subprocess with secrets.
- [x] Extend setup tests for Chrome selection, fallback, and cancellation; add
  selection to `setup_cookie`, preserving current manual `save_cookie` behavior.
- [x] Document Chrome 144+, enabling debugging, Allow prompt, signed-in Loom tab,
  broad permission scope, fallback, and cookie refresh.
- [x] Run unittest, compile/build, native Keychain temporary-item round trip,
  and live import if browser consent is available. Record exact verification scope.
- [x] Review final diff and commit small steps; do not push without permission.
