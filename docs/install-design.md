# Public installation design

Status: approved for implementation.

## User experience

The README opens with one macOS install command:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/sonmai/mcp-loom/main/install.sh)"
```

The installer explains each step, checks prerequisites, installs the package,
and launches a terminal setup wizard. A separate download-and-inspect option
remains documented. A manual uv installation remains available.

The wizard asks users to choose their local clients, guides them to the Loom
cookie, saves it through macOS Keychain's own hidden password prompt, registers
the selected clients, and ends with a per-client success/failure summary and
restart instructions. Users do not copy paths, edit JSON/TOML, or clone the repo.
An existing cookie can be kept; refreshing it is an explicit choice.

## Prerequisites and installation

- macOS only. Detect the operating system before making changes.
- Reuse installed uv and ffmpeg. Explain missing prerequisites and ask before
  installing them. Use Homebrew when available; if absent, offer its official
  interactive installer, including any password prompt it requires.
- Let uv manage Python and the application's isolated environment.
- Install a published repository revision, recording the resolved version.
  Do not add a PyPI release, Homebrew tap, or hosted service to this task.
- Resolve the installed executable to an absolute path before registration.
  The setup must work when desktop apps have a different PATH from Terminal.
- Discover ffmpeg at the normal Apple Silicon or Intel Homebrew location, then
  PATH, rather than requiring every Mac to use `/opt/homebrew/bin/ffmpeg`.

## CLI and server boundary

Retain a single console script, `loom-mcp`:

- No arguments: start the existing stdio MCP server.
- `setup`: run the interactive setup wizard in a terminal.
- `--help`: explain both modes.

The setup wizard is isolated from server registration and tool descriptions.
Client-specific code belongs only to installation/setup, as required to automate
client registration. No setup prompt or diagnostic may appear on the MCP stdout
channel. Existing `uv run --directory <repo> loom-mcp` configurations keep working.

Exactly three MCP tools remain: `get_video`, `get_transcript`, and `get_frames`.
No additional runtime dependencies are introduced.

## Credentials

Run `security add-generic-password -U -s loom-mcp -a connect.sid -w` with the
terminal attached. The OS utility reads the hidden value directly. The installer
must never receive the cookie through an argument, environment variable, config
file, or temporary file, and must never print it. Keep the existing runtime
Keychain read. Browser login and copying the cookie remain manual because Loom
has no supported authentication API for this use case.

## Client registration

Support the six clients already documented. Let users select one or more;
only selected configurations can change.

- Claude Code, Codex CLI, Gemini CLI, and VS Code: prefer the documented official
  registration commands with user scope and an absolute executable path.
- Claude Desktop and Cursor: merge only the `loom` entry in their JSON config.
  Preserve unrelated values, back up an existing file, and replace it atomically.
- Existing matching entries are left alone. Show a proposed replacement before
  changing a conflicting `loom` entry. Invalid configurations are left untouched,
  with actionable instructions; never silently replace a malformed file.
- Handle absent clients explicitly and continue with the other selections.
- Do not enable blanket tool approval or weaken client permission settings.

## Verification

Use focused behavioral tests for preserving existing settings, repeat setup,
malformed-file handling, conflicting entries, and cancellation. Test the CLI
boundary to ensure setup is opt-in and the normal invocation still exposes
exactly three tools over stdio. Test prerequisite detection with controlled
executables and temporary directories; do not install system packages in tests.

Run the installer against an isolated installation location, then verify the
installed server with Inspector. Existing live-video results are retained as
historical evidence; rerun the three live tools after changing executable lookup.
Do not overwrite the owner's working client configuration merely to test setup.

The public README uses generic paths and video examples, with the common setup
first and manual configuration/troubleshooting below it. A successful installer
check is distinguished from runtime checks in each client.

## Alternatives considered

1. Guided installer (recommended): fewest manual steps, works without a checkout,
   and does not require publishing infrastructure. Requires maintaining a small
   setup module and script.
2. uv commands only: least code, but users still configure clients and prerequisites
   manually. This is the current fallback.
3. PyPI package or Homebrew tap: shorter package commands, but requires separate
   publishing ownership and still needs the cookie/client setup wizard.

## Source references

- [uv tool installation](https://docs.astral.sh/uv/guides/tools/)
- [Homebrew installation](https://docs.brew.sh/Installation)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Codex MCP registration](https://github.com/openai/codex/blob/main/codex-rs/cli/src/mcp_cmd.rs)
- [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/)
- [Claude Desktop local MCP](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Cursor MCP](https://cursor.com/docs/mcp)
- [VS Code MCP configuration](https://github.com/microsoft/vscode-docs/blob/main/docs/agents/reference/mcp-configuration.md)

No push, package publication, or repository visibility change is included.
