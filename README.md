# loom-mcp

A personal, read-only Loom MCP server for local clients on macOS. Python, uv,
the official MCP Python SDK, and HTTPX. Exactly three tools; stdio only.

Verified with MCP Inspector, Claude Code, and Codex CLI: metadata, timestamped
transcript, and three readable frames with existing file paths. Four parsing
tests pass. See [verification status](docs/verification.md) for evidence and scope.

## Quick install

Requires macOS, [uv](https://docs.astral.sh/uv/getting-started/installation/),
and ffmpeg at `/opt/homebrew/bin/ffmpeg`.

**1. Install directly from GitHub.** No clone or repository path needed.

```sh
uv tool install git+https://github.com/sonmai/mcp-loom.git
```

uv manages the Python environment and installs the `loom-mcp` executable.
[Official uv tool installation guide](https://docs.astral.sh/uv/guides/tools/).

**2. Save your Loom cookie once.** In your signed-in browser, open
**DevTools > Application > Cookies > connect.sid** and copy its value. Run:

```sh
security add-generic-password -U -s loom-mcp -a connect.sid -w
```

Paste the value at the password prompt, not into the command or a config file.
Use the same command whenever the cookie expires. No server restart is needed.

**3. Connect your client** using one of the commands or configurations below,
then start a new client session.

## Connect a client

For command-line clients, these commands automatically find the installed executable.
For JSON configurations, replace `/absolute/path/to/loom-mcp` with the path printed by:

```sh
printf '%s/loom-mcp\n' "$(uv tool dir --bin)"
```

Merge entries into existing configurations rather than replacing other servers.
Credentials stay in Keychain.

### Claude Code

[Official MCP documentation](https://code.claude.com/docs/en/mcp).

```sh
claude mcp add --transport stdio --scope user loom -- "$(uv tool dir --bin)/loom-mcp"
```

### Codex CLI

[Official MCP registration source](https://github.com/openai/codex/blob/main/codex-rs/cli/src/mcp_cmd.rs).

```sh
codex mcp add loom -- "$(uv tool dir --bin)/loom-mcp"
```

### Claude Desktop

Merge into `~/Library/Application Support/Claude/claude_desktop_config.json`
(Settings > Developer > Edit Config).
[Official local-server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

```json
{
  "mcpServers": {
    "loom": { "command": "/absolute/path/to/loom-mcp" }
  }
}
```

### Gemini CLI

Merge into `~/.gemini/settings.json`.
[Official MCP documentation](https://geminicli.com/docs/tools/mcp-server/)
and [configuration locations](https://geminicli.com/docs/reference/configuration/).

```json
{
  "mcpServers": {
    "loom": { "command": "/absolute/path/to/loom-mcp" }
  }
}
```

### Cursor

Merge into `~/.cursor/mcp.json`.
[Official MCP documentation](https://cursor.com/docs/mcp).

```json
{
  "mcpServers": {
    "loom": { "command": "/absolute/path/to/loom-mcp" }
  }
}
```

### VS Code

Run **MCP: Open User Configuration** and merge into that `mcp.json`.
[Official configuration reference](https://github.com/microsoft/vscode-docs/blob/main/docs/agents/reference/mcp-configuration.md).

```json
{
  "servers": {
    "loom": { "type": "stdio", "command": "/absolute/path/to/loom-mcp" }
  }
}
```

Formats were checked against the linked documentation on 2026-10-29.
Existing installations using `uv run --directory ... loom-mcp` continue to work;
there is no need to change them. Only Claude Code and Codex CLI have been
runtime-tested, using that local-checkout launch command.

## Update

Reinstall from the current GitHub revision:

```sh
uv tool install --reinstall git+https://github.com/sonmai/mcp-loom.git
```

Restart the client to use the updated server. The Keychain cookie and media cache
are retained.

## Tools

| Tool | Arguments | Result |
| --- | --- | --- |
| `get_video` | `video`: HTTPS Loom share URL or 32-character hexadecimal ID | JSON text with `id`, `name`, `owner`, `duration_seconds`, `created_at`, `description`; unavailable optional values are null |
| `get_transcript` | `video` | JSON text with `video_id` and `segments`, each containing `timestamp_seconds`, `text`, and `speaker` (null if unavailable) |
| `get_frames` | `video`, `timestamps`: 1–10 numbers or strings | For each input position, a text block containing `timestamp_seconds` and absolute `path`, followed by PNG MCP image content |

For example, `timestamps: ["0:39", "1:14", "1:39"]` is equivalent to
`[39, 74, 99]`. Decimal seconds are accepted. Strings use seconds or `M:SS`;
hours can be expressed as total minutes. Negative values, non-finite values,
and positions at or beyond the duration are rejected. The exact endpoint has
no frame. Input order and duplicates are preserved.

Frames are scaled to 1280 pixels wide with the aspect ratio preserved and saved
under `~/Library/Caches/loom-mcp/<video_id>/frames/`. Both image content and an
absolute path are returned so a client that drops image content can still read
the PNG locally. The MP4 is cached at `~/Library/Caches/loom-mcp/<video_id>.mp4`.
Separate processes share a per-video file lock; downloads are installed atomically.
Frame calls re-check video metadata and duration, even when the MP4 is cached.

The cache is not automatically refreshed when a video is edited. Delete the
affected MP4 manually to force a fresh download. Cache files remain locally
until removed, including after a cookie expires. There is no cache-management tool.

## Development and verification

For a local checkout, the original entry point remains available:

```sh
uv run --directory /absolute/path/to/mcp-loom loom-mcp
```

The project uses Python 3.11+, the official MCP SDK, and HTTPX. `uv_build` is the
build backend. No extra runtime dependency is needed for installation.

To inspect the standalone installation:

```sh
npx @modelcontextprotocol/inspector "$(uv tool dir --bin)/loom-mcp"
```

Connect using stdio and confirm `tools/list` contains exactly `get_video`,
`get_transcript`, and `get_frames`, with read-only annotations. Call each with
`video` set to `https://www.loom.com/share/2d424ca8b7b04839ae7e57086030efb0`:

1. `get_video`: name is `Creative-Campaign Association Portal Sync Issue`.
2. `get_transcript`: first text starts near `Hey, so, this is kind of hard to explain`.
3. `get_frames`: use `["0:39", "1:14", "1:39"]`; inspect three readable images
   and confirm all three returned absolute PNG paths exist.

For development, run the focused standard-library tests from a local checkout:

```sh
uv run --directory /absolute/path/to/mcp-loom python -m unittest discover -s tests
```

## Limits and attribution

Authentication reads only the `loom-mcp` / `connect.sid` Keychain item at runtime.
Errors never include cookie values or raw HTTP/subprocess diagnostics. Logs go to
stderr; stdout is the MCP channel.

macOS only, because authentication uses Keychain. Stdio only. Remote HTTP clients
are out of scope: a remotely hosted server would need to hold the browser cookie.
The server has no HTTP transport and no client-specific runtime behavior.

This uses an undocumented internal API that can break. A cookie grants whatever
access the browser session has; this server exposes only fixed read queries.
It cannot bypass sharing restrictions, supply video passwords, generate
transcripts, or regenerate MP4 exports. Missing MP4 exports cause a clear error;
there is no DASH fallback in this small implementation. Only local cache files
are written. No Loom data is modified.

The GraphQL queries are adapted from
[karbassi/mcp-loom@9d5f0ce5bfad960541ae11a3e525640d5acc8081](https://github.com/karbassi/mcp-loom/blob/9d5f0ce5bfad960541ae11a3e525640d5acc8081/src/loom_mcp/client.py)
(MIT). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the full notice,
and [docs/upstream.md](docs/upstream.md) for exact source queries and adaptations.
The upstream package is not installed or executed.
