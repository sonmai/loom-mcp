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
