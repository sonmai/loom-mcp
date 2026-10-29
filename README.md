# loom-mcp

A personal, read-only Loom MCP server for local clients on macOS. Python, uv,
the official MCP Python SDK, and HTTPX. Exactly three tools; stdio only.

Verified with MCP Inspector, Claude Code, and Codex CLI: metadata, timestamped
transcript, and three readable frames with existing file paths. Four parsing
tests pass. See [verification status](docs/verification.md) for evidence and scope.

## Setup

Requires Python 3.11+, uv, macOS Keychain, and `/opt/homebrew/bin/ffmpeg`.
The only runtime dependencies declared by this project are `mcp` and `httpx`;
their transitive dependencies are installed by uv. `uv_build` is the build backend.

In your signed-in Loom browser, open **DevTools > Application > Cookies >
connect.sid**. Copy only the cookie value. In Terminal run:

```sh
security add-generic-password -U -s loom-mcp -a connect.sid -w
```

Enter the value at the password prompt. Do not append it to the command, paste it
into chat, or put it in a configuration file. Refresh an expired cookie using the
same steps and command. A later tool call reads the updated item automatically.
If Keychain prompts for access, allow the local process to read this item.

At runtime the server captures the output of this command internally:

```sh
security find-generic-password -s loom-mcp -a connect.sid -w
```

Do not run that read command in a shared terminal or paste its output anywhere.
The server reads credentials only from Keychain. Authentication errors contain
refresh instructions; raw HTTP bodies, cookie values, and subprocess diagnostics
are not included in errors. Logging goes to stderr; stdout carries MCP only.

After approval, launch from any working directory:

```sh
uv run --directory /Users/test/PersonalProjects/mcp-loom loom-mcp
```

The first launch installs the project and its dependencies. All media paths are
derived from the user's home directory, never the caller's working directory.

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

## Install in a local client

These examples use the repository's current absolute path and the locally detected
uv executable, `/Users/test/.local/bin/uv`. Adjust both paths if the repo or uv moves.
Merge entries into existing configurations rather than replacing other servers.
No example stores a cookie or supplies credentials through environment variables.

### Claude Code

Register at user scope. [Official MCP configuration documentation](https://code.claude.com/docs/en/mcp).

```sh
claude mcp add --transport stdio --scope user loom -- \
  /Users/test/.local/bin/uv run --directory /Users/test/PersonalProjects/mcp-loom loom-mcp
```

### Claude Desktop

Merge into `~/Library/Application Support/Claude/claude_desktop_config.json`,
available through Settings > Developer > Edit Config.
[Official local-server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

```json
{
  "mcpServers": {
    "loom": {
      "command": "/Users/test/.local/bin/uv",
      "args": ["run", "--directory", "/Users/test/PersonalProjects/mcp-loom", "loom-mcp"]
    }
  }
}
```

### Codex CLI

Add to `~/.codex/config.toml`.
[Official configuration source](https://github.com/openai/codex/blob/main/codex-rs/config/src/mcp_types.rs).

```toml
[mcp_servers.loom]
command = "/Users/test/.local/bin/uv"
args = ["run", "--directory", "/Users/test/PersonalProjects/mcp-loom", "loom-mcp"]
```

### Gemini CLI

Merge into `~/.gemini/settings.json`.
[Official MCP configuration documentation](https://geminicli.com/docs/tools/mcp-server/)
and [configuration locations](https://geminicli.com/docs/reference/configuration/).

```json
{
  "mcpServers": {
    "loom": {
      "command": "/Users/test/.local/bin/uv",
      "args": ["run", "--directory", "/Users/test/PersonalProjects/mcp-loom", "loom-mcp"]
    }
  }
}
```

### Cursor

Merge into `~/.cursor/mcp.json`.
[Official MCP configuration documentation](https://cursor.com/docs/mcp).

```json
{
  "mcpServers": {
    "loom": {
      "command": "/Users/test/.local/bin/uv",
      "args": ["run", "--directory", "/Users/test/PersonalProjects/mcp-loom", "loom-mcp"]
    }
  }
}
```

### VS Code

Use **MCP: Open User Configuration** and merge into that `mcp.json`.
This is the VS Code format, with `servers` and `type: stdio`.
[Official configuration reference](https://github.com/microsoft/vscode-docs/blob/main/docs/agents/reference/mcp-configuration.md).

```json
{
  "servers": {
    "loom": {
      "type": "stdio",
      "command": "/Users/test/.local/bin/uv",
      "args": ["run", "--directory", "/Users/test/PersonalProjects/mcp-loom", "loom-mcp"]
    }
  }
}
```

Formats were checked against the linked documentation on 2026-10-29.
Configuration documentation is not evidence that a client has been tested.

## Verification after approval

Start with MCP Inspector before installing the server in any client:

```sh
npx @modelcontextprotocol/inspector uv run --directory /Users/test/PersonalProjects/mcp-loom loom-mcp
```

Connect using stdio and confirm `tools/list` contains exactly `get_video`,
`get_transcript`, and `get_frames`, with read-only annotations. Call each with
`video` set to `https://www.loom.com/share/2d424ca8b7b04839ae7e57086030efb0`:

1. `get_video`: name is `Creative-Campaign Association Portal Sync Issue`.
2. `get_transcript`: first text starts near `Hey, so, this is kind of hard to explain`.
3. `get_frames`: use `["0:39", "1:14", "1:39"]`; inspect three readable images
   and confirm all three returned absolute PNG paths exist.

Repeat the same checks in the two selected local clients after Inspector passes.
The focused standard-library parsing tests can then be run without a test dependency:

```sh
uv run --directory /Users/test/PersonalProjects/mcp-loom python -m unittest discover -s tests
```

## Limits and attribution

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
