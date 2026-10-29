import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Loom videos over MCP stdio, or run guided local setup.")
    parser.add_argument("action", nargs="?", choices=["setup"], help="Guide Keychain and client setup in a terminal")
    arguments = parser.parse_args()
    if arguments.action is None:
        from loom_mcp.server import main as serve
        serve()
        return
    from loom_mcp.setup import SetupError, run_setup
    try:
        status = run_setup(Path(os.path.abspath(sys.argv[0])))
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled. Completed steps are kept; rerun setup to continue.", file=sys.stderr)
        status = 130
    except SetupError as error:
        print(str(error), file=sys.stderr)
        status = 1
    except (OSError, subprocess.TimeoutExpired):
        print("Setup could not access a local file or process. Check permissions and retry.", file=sys.stderr)
        status = 1
    raise SystemExit(status)


if __name__ == "__main__":
    main()
