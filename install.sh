#!/bin/bash
set -euo pipefail

release='v0.1.1'
source_package="git+https://github.com/sonmai/loom-mcp.git@$release"
constraints_url="https://raw.githubusercontent.com/sonmai/loom-mcp/$release/constraints.txt"
custom_source=false
run_setup=true

usage() {
    cat <<'USAGE'
Install Loom MCP on macOS and guide Keychain/client setup.

Usage: bash install.sh [--source PATH_OR_URL] [--no-setup]
  --source     Install a reviewed local checkout or another repository revision
               instead of the pinned release. A local checkout's constraints.txt
               is applied; other sources resolve dependencies without constraints.
  --no-setup   Install only; do not read Keychain or change client configurations.
  --help       Show this help.

Missing prerequisites are installed only after confirmation. Existing uv and
ffmpeg installations are reused. No cookie is passed through this script.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --source)
            if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                echo '--source needs a path or URL.' >&2
                exit 1
            fi
            source_package="$2"
            custom_source=true
            shift 2
            ;;
        --no-setup) run_setup=false; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    esac
done

if [ "$(uname -s)" != Darwin ]; then
    echo 'Loom MCP requires macOS because credentials are stored in Keychain.' >&2
    exit 1
fi

find_program() {
    local program="$1" candidate
    for candidate in "/opt/homebrew/bin/$program" "/usr/local/bin/$program" "$HOME/.local/bin/$program"; do
        if [ -x "$candidate" ] && [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    command -v "$program" 2>/dev/null || true
}

ask() {
    local response
    printf '%s [y/N] ' "$1" >&2
    if ! read -r response </dev/tty; then
        echo 'An interactive Terminal is required to approve prerequisite installation.' >&2
        exit 1
    fi
    case "$response" in
        y|Y|yes|YES) return 0 ;;
        *) echo 'Cancelled. No further installation steps will run.' >&2; exit 1 ;;
    esac
}

uv_program="$(find_program uv)"
ffmpeg_program="$(find_program ffmpeg)"
missing=()
[ -n "$uv_program" ] || missing+=(uv)
[ -n "$ffmpeg_program" ] || missing+=(ffmpeg)

if [ "${#missing[@]}" -gt 0 ]; then
    brew_program="$(find_program brew)"
    if [ -z "$brew_program" ]; then
        ask 'Homebrew is needed to install missing prerequisites. Run its official installer (may request your Mac password)?'
        brew_installer="$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        /bin/bash -c "$brew_installer" </dev/tty
        brew_program="$(find_program brew)"
        if [ -z "$brew_program" ]; then
            echo 'Homebrew was not found after installation. Follow https://brew.sh and rerun this installer.' >&2
            exit 1
        fi
    fi
    ask "Install missing prerequisites with Homebrew: ${missing[*]}?"
    "$brew_program" install "${missing[@]}" </dev/tty
    uv_program="$(find_program uv)"
    ffmpeg_program="$(find_program ffmpeg)"
fi

if [ -z "$uv_program" ] || [ -z "$ffmpeg_program" ]; then
    echo 'uv or ffmpeg is still missing. Fix the prerequisite installation and retry.' >&2
    exit 1
fi

constraint_arguments=()
if [ "$custom_source" = false ]; then
    constraints_file="$(mktemp)"
    trap 'rm -f "$constraints_file"' EXIT
    curl -fsSL "$constraints_url" -o "$constraints_file"
    constraint_arguments=(--constraints "$constraints_file")
elif [ -f "$source_package/constraints.txt" ]; then
    constraint_arguments=(--constraints "$source_package/constraints.txt")
else
    echo 'No constraints.txt for this source; dependencies resolve to their latest compatible versions.' >&2
fi

printf '\nInstalling Loom MCP from %s\n' "$source_package"
"$uv_program" tool install --python 3.12 --reinstall ${constraint_arguments[@]+"${constraint_arguments[@]}"} "$source_package"
# The EXIT trap does not run once setup replaces this process with exec.
[ -z "${constraints_file:-}" ] || rm -f "$constraints_file"
tool_directory="$("$uv_program" tool dir --bin)"
executable="$tool_directory/loom-mcp"
if [ ! -x "$executable" ]; then
    echo 'Installation did not produce the loom-mcp executable.' >&2
    exit 1
fi

printf '\nInstalled: %s\n' "$executable"
printf 'To rerun setup later: %q setup\n' "$executable"
if [ "$run_setup" = true ]; then
    if ! { : </dev/tty; } 2>/dev/null; then
        printf 'Run this command in an interactive Terminal: %q setup\n' "$executable" >&2
        exit 1
    fi
    exec "$executable" setup </dev/tty >/dev/tty
fi
