# Verification status

2026-10-29. Approved clients: Claude Code at user scope and Codex CLI.

## Completed

- `uv sync`: built the project and installed its dependencies using Python 3.12.12.
  Resolution is recorded in `uv.lock`.
- Started the requested MCP Inspector UI with the stdio launch command.
  Inspector 2.13.0 displayed a connected session.
- Inspector CLI `tools/list`: exactly `get_video`, `get_transcript`, and
  `get_frames`; all declare `readOnlyHint: true` and `destructiveHint: false`.
  The frame schema advertises 1–10 timestamps and image/path output semantics.
- `.venv/bin/python -m unittest discover -s tests -v`: 4 tests passed, covering
  URL/ID parsing, timestamp conversion, invalid input, and duration bounds.

## Live acceptance checks

After the user saved the cookie in Keychain, all three tools succeeded in
Inspector CLI, followed by Claude Code and Codex CLI using their installed
user configurations. The clients were launched from `/private/tmp`, outside
the repository, confirming the absolute-directory entry point works.

Test video: `https://www.loom.com/share/2d424ca8b7b04839ae7e57086030efb0`.

| Check | Inspector | Claude Code | Codex CLI |
| --- | --- | --- | --- |
| Exact name: `Creative-Campaign Association Portal Sync Issue` | Pass | Pass | Pass |
| Transcript starts `Hey, so, this is kind of hard to explain` | Pass | Pass | Pass |
| Frames at 39, 74, and 99 seconds | Pass | Pass | Pass |
| Three PNG image blocks and three absolute paths | Pass | Pass | Pass |
| Returned images match existing PNG files | Pass | Pass | Pass |
| Frame content is readable | Visually inspected | Client described each image | Client described each image |

Metadata returned duration `114.538667` seconds. The transcript contains eight
segments, starting at `0.011` seconds; speakers are unavailable and returned as
null. Each PNG is 1280 by 720 pixels.

The frames show the Creative Requests page at 0:39, the Manage Associations panel
at 1:14, and the Orders page at 1:39. Files exist under
`~/Library/Caches/loom-mcp/2d424ca8b7b04839ae7e57086030efb0/frames/`:

- `39.0s.png`
- `74.0s.png`
- `99.0s.png`

The client event logs were parsed to check actual tool results, exact title,
transcript prefix, image counts, and byte-for-byte equality of each image with
its returned file path. Client final-answer claims were not the sole evidence.
Verification logs and media are kept outside the repository.

## Installed configurations

- Claude Code: `loom` at user scope in `~/.claude.json`; `claude mcp get loom`
  reports Connected when run with normal local filesystem access.
- Codex CLI: global `loom` entry in `~/.codex/config.toml`, enabled with stdio.
- Both launch `/Users/test/.local/bin/uv run --directory
  /Users/test/PersonalProjects/mcp-loom loom-mcp`, without credential variables.

The initial missing-cookie failure returned the documented refresh instructions
without exposing a cookie. A sandboxed connection-status probe also failed
because the sandbox restricts uv's normal cache; the same probe succeeded with
normal local access. Actual client tool calls succeeded.

No code changes were required after the approved draft. The other four documented
clients have not been runtime-tested. No commit has been pushed.

## Standalone installation

The simplified `uv tool install git+https://github.com/sonmai/mcp-loom.git` route
was tested with isolated `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` directories under
`/private/tmp/loom-install-check`. It installed commit `bdd2b81` and exposed a
standalone `loom-mcp` executable. Inspector CLI connected directly to that
executable and discovered exactly the same three read-only tools. Existing
client registrations were unchanged. This check verifies installation and tool
discovery; the live-video checks above used the local-checkout installation.

## Guided public installer

The approved guided installer was implemented on `feat/guided-installation`.
Validation used a fresh tool environment under `/private/tmp/loom-public-install`
and `bash install.sh --source <checkout> --no-setup`; no client configuration or
Keychain item was changed during installation testing.

- Shell syntax and `--help` passed. Installation built the new CLI entry point.
- The installed `loom-mcp setup` displayed all six clients in a real terminal;
  pressing Enter cancelled successfully without changes.
- 17 tests passed, including preserved settings/backups, repeat setup, declined
  replacement, malformed configuration, failed CLI registration, restoration of
  a failed replacement, native hidden cookie entry, cancellation, CLI boundaries,
  and Intel/PATH executable discovery.
- Independent review identified custom CLI config roots as a conflict-detection
  risk. Registration now rejects non-default roots before invoking native commands;
  the focused regression failed for all three affected clients before the fix and
  passes afterward. VS Code's Default-profile registration was separately checked
  by the reviewer using an isolated user-data directory.
- Inspector connected to the installer-built executable with no arguments and
  discovered exactly the three read-only tools. Metadata and transcript matched
  the earlier acceptance checks. Frames at 39, 74, and 99 seconds each returned
  a 1280×720 PNG image block and an existing, byte-identical absolute file path.
- The original user-scoped client registrations remain unchanged.

A clean Mac's Homebrew/prerequisite installation and real Intel hardware were
not exercised. The four additional clients' actual registration commands were
not run; their formats are sourced in the README. Public download URLs require
the installer commit to be pushed to `main` and the repository to be public.

Packaging inspection found that the original wheel omitted the standalone MIT
notice. `project.license-files` now explicitly includes it. Its exact bytes were
verified in both the built wheel and the isolated installed package.

The local uv 0.9.26 failed to extract the generated source archive during a full
`uv build`, although Python tarfile and macOS tar read it successfully. Running
the same archive through isolated uv 0.13.6 succeeded, as did a complete
source-distribution-plus-wheel build with that version. The installer itself
was retested successfully with the existing uv 0.9.26; it builds directly from
the checkout. Use current uv for building release distributions. No system uv
upgrade was performed.
