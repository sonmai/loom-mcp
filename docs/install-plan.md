# Guided installation implementation plan

Goal: one macOS install command followed by guided Keychain and client setup.
Approved design: [install-design.md](install-design.md).

Architecture: a shell bootstrap installs prerequisites and the uv tool; an opt-in
Python CLI handles setup. The stdio server remains the default, with no setup
imports or prompts on its normal path. Use Python's standard library only.

## Constraints

- Exactly three read-only MCP tools; no additional runtime dependencies.
- One console script: `loom-mcp`, with optional `setup` and `--help`.
- Cookie input belongs to the macOS security utility, never Python or the shell.
- Preserve unrelated client settings; back up modifications and confirm conflicts.
- No public release, push, or changes to existing working client setups in tests.

## Execution

- [x] Add focused setup tests in `tests/test_setup.py` and run them before implementation.
  Protect JSON preservation, byte-identical backup, repeat setup, rejection of
  malformed configurations, declined replacement, and native hidden cookie input.
- [x] Add `src/loom_mcp/setup.py` for terminal selection and configuration registration.
  Read JSON/TOML to detect conflicts; use native CLI registration where supported.
  Desktop JSON merges use temporary files and atomic replacement, with private backups.
- [x] Add `src/loom_mcp/cli.py`, route the console script there, and preserve no-argument
  dispatch to `server.main`. Test help/setup boundaries separately from server discovery.
- [x] Add `src/loom_mcp/executables.py` for ffmpeg lookup on Apple Silicon, Intel, and PATH;
  extend focused tests for discovery and missing executables, then wire extraction to it.
- [x] Add `install.sh`: macOS check, explicit prerequisite consent, uv installation,
  absolute executable discovery, setup invocation, and local-source/no-setup options.
  Test shell syntax, isolated installation, and unsupported-platform rejection.
  Exercise wizard cancellation without touching client settings. A clean Mac prerequisite install remains untested.
- [x] Rewrite README onboarding, keep six sourced manual configurations, and remove
  personal acceptance-video details from the public setup instructions.
- [x] Run all focused tests, Inspector discovery and three live tools; inspect returned
  frame files. Record actual coverage and limits. Commit small steps; do not push.
