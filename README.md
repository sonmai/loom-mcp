# loom-mcp

A personal, read-only Loom MCP server for local clients on macOS. Python, uv,
the official MCP Python SDK, and HTTPX. Exactly three tools; stdio only.

Verified with MCP Inspector, Claude Code, and Codex CLI: metadata, timestamped
transcript, and three readable frames with existing file paths. Focused parsing
and setup tests pass. See [verification status](docs/verification.md) for evidence
and scope.

## Install

On your Mac, paste this into Terminal:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/sonmai/loom-mcp/v0.1.1/install.sh)"
```

The installer checks prerequisites, asks before installing anything missing,
installs Loom MCP, and opens a setup wizard:

1. Choose the local clients you use.
2. Choose **Import from Chrome** and follow the permission prompt, or paste a cookie manually.
3. Once setup saves the cookie in Keychain, restart your clients.

That is all. No clone, Python setup, path editing, or config-file editing is needed.
The installer pins a tagged release and its locked dependency versions, so every
install of a release gets the same code that was verified.
The wizard supports Claude Code, Claude Desktop, Codex CLI, Gemini CLI, Cursor,
and VS Code's Default profile. Existing settings are preserved; changed files
are backed up. Replacing an existing `loom` entry requires confirmation.

**Import from Chrome (144+):** keep a signed-in [Loom](https://www.loom.com)
tab open in your usual Chrome profile. Open `chrome://inspect/#remote-debugging`
and enable remote debugging. Choose Chrome import in setup, then click **Allow**
in Chrome's connection dialog within 60 seconds. No separate profile or new login
is needed if that profile is already signed in. Setup reads the Loom session,
disconnects, and saves it in Keychain. You can turn remote debugging off afterward.

Chrome grants broad debugging permission. This importer only lists tab metadata,
attaches to a Loom tab, and reads cookies applicable to `https://www.loom.com/`;
it saves only `connect.sid`. It does not execute page scripts, close your tabs,
or read Chrome's cookie database. It supports the standard Chrome Stable user-data
location on macOS. If multiple browser contexts have Loom tabs, it asks you to
keep one context open instead of guessing an account.
[Chrome connection documentation](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/advanced-usage.md#automatically-connecting-to-a-running-chrome-instance).

**Manual fallback:** sign in to Loom, open your browser's DevTools, select
**Application > Cookies > https://www.loom.com**, and copy the **value** of
`connect.sid`. Paste it into setup's hidden password prompt. Older Chrome versions,
managed browsers that disable debugging, and custom user-data directories can use
this route. Failed Chrome imports offer manual entry without replacing Keychain.

The imported cookie is written directly through macOS Keychain APIs; it never
appears in command arguments, environment variables, logs, or temporary files.
The MCP server continues reading only the Keychain item at runtime.

The installer works on Apple Silicon and Intel Macs. Missing prerequisites are
installed through [Homebrew](https://brew.sh), with your consent. Homebrew may
request your Mac password or Command Line Tools installation. Downloads need an
internet connection. Client apps themselves must already be installed.

<details>
<summary>Inspect the installer first, or install manually</summary>

Download and read the script before running it:

```sh
curl -fsSLo install-loom.sh https://raw.githubusercontent.com/sonmai/loom-mcp/v0.1.1/install.sh
less install-loom.sh
bash install-loom.sh
```

Already have uv and ffmpeg? Install the package and open setup directly:

```sh
uv tool install git+https://github.com/sonmai/loom-mcp.git@v0.1.1
"$(uv tool dir --bin)/loom-mcp" setup
```

[Official uv installation guide](https://docs.astral.sh/uv/guides/tools/).
To install without changing Keychain or client settings, use
`bash install-loom.sh --no-setup`. A reviewed local checkout can be installed with
`bash install.sh --source /absolute/path/to/loom-mcp`; its `constraints.txt` is applied.
The manual `uv tool install` above does not apply the locked versions of
indirect dependencies; the installer does.

</details>

## Refresh your cookie or connect another client

Run the setup command printed by the installer. If uv is on your shell's PATH,
you can also use:

```sh
"$(uv tool dir --bin)/loom-mcp" setup
```

Choose **0** to refresh only the cookie. Otherwise choose the clients to configure.
You can keep an existing cookie or import a fresh one from Chrome using the steps
above. Expired cookies can also be replaced directly:

```sh
security add-generic-password -U -s loom-mcp -a connect.sid -w
```

Paste the value at the hidden password prompt, never after the command. No server
restart is needed for a refreshed cookie. Never paste the cookie into an AI chat.

## Troubleshooting

- **No tools after setup:** fully restart the client. Confirm its local MCP server
  named `loom` is enabled. The wizard reports failures separately for each client.
- **A CLI cannot be found:** install that client's command-line launcher and rerun
  setup, or use the manual configurations below. VS Code's bundled launcher is
  also detected under `/Applications` and `~/Applications`.
- **A configuration contains comments or cannot be parsed:** the wizard leaves it
  untouched. Merge the manual snippet below using the client's configuration UI.
  Symlinked configuration files are also left for manual configuration.
- **Different VS Code profile:** use that profile's **MCP: Open User Configuration**
  and the manual snippet. The wizard targets only the Default profile.
- **Custom CLI config directory:** if `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, or
  `GEMINI_CLI_HOME` selects a non-default location, the wizard leaves that client
  untouched. Use its manual registration command in your usual shell instead.
- **Frames need ffmpeg:** rerun the installer, or run `brew install ffmpeg`.
  Both Homebrew locations and executables on PATH are supported.
- **Chrome import cannot connect:** use Chrome 144+, enable remote debugging,
  keep a signed-in Loom tab open, and approve Chrome's connection dialog. Setup
  does not enable debugging itself. Manual entry remains available.
- **Cookie missing or access denied:** rerun setup and choose cookie-only mode.
  Allow the local process to access the Keychain item if macOS asks.

## Manual client configuration

<details>
<summary>Configuration snippets for all six clients</summary>

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

</details>

## Update

Rerun the one-command installer from the [Install](#install) section. It names the
latest release, installs it with locked dependencies, and checks your setup.

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
uv run --directory /absolute/path/to/loom-mcp loom-mcp
```

The project uses Python 3.11+, the official MCP SDK, and HTTPX. `uv_build` is the
build backend. No extra runtime dependency is needed for installation.

To inspect the standalone installation:

```sh
npx @modelcontextprotocol/inspector "$(uv tool dir --bin)/loom-mcp"
```

Connect using stdio and confirm `tools/list` contains exactly `get_video`,
`get_transcript`, and `get_frames`, with read-only annotations. Call each with
`video` set to a share URL you can access:

1. `get_video`: confirm the name and duration match the video.
2. `get_transcript`: compare the first segment with the video's opening words.
3. `get_frames`: choose timestamps before the end of the video; inspect each
   returned image and confirm its absolute PNG path exists.

For development, run the focused standard-library tests from a local checkout:

```sh
uv run --directory /absolute/path/to/loom-mcp python -m unittest discover -s tests
```

To cut a release, set the same version in `pyproject.toml` and `release` in
`install.sh` (a test enforces this), regenerate the constraints, update the
`v…` URLs in this README, and push a matching tag:

```sh
uv export --frozen --no-hashes --no-dev --no-emit-project -o constraints.txt
git tag v0.1.1 && git push origin v0.1.1
```

`uv tool install` ignores `uv.lock`, so `constraints.txt` is how the installer
applies the locked versions. The installer downloads it from the release tag.

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

## License

[MIT](LICENSE). Adapted upstream queries keep their own MIT notice in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
