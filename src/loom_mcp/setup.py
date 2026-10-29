import json
import os
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from loom_mcp.executables import find_executable
from loom_mcp.chrome import REMOTE_DEBUGGING_PAGE, ChromeDebuggingOff, ChromeError, open_in_chrome, read_chrome_cookie
from loom_mcp.keychain import KeychainError, store_cookie


class SetupError(Exception):
    pass


class UnparsableConfiguration(SetupError):
    def __init__(self, message: str, original: bytes):
        super().__init__(message)
        self.original = original


@dataclass(frozen=True)
class Client:
    name: str
    config: str
    key: str = "mcpServers"
    command: str | None = None


CLIENTS = (
    Client("Claude Code", ".claude.json", command="claude"),
    Client("Claude Desktop", "Library/Application Support/Claude/claude_desktop_config.json"),
    Client("Codex CLI", ".codex/config.toml", "mcp_servers", "codex"),
    Client("Gemini CLI", ".gemini/settings.json", command="gemini"),
    Client("Cursor", ".cursor/mcp.json"),
    Client("VS Code", "Library/Application Support/Code/User/mcp.json", "servers", "code"),
)


def confirm(message: str) -> bool:
    return input(f"{message} [y/N] ").strip().lower() in {"y", "yes"}


def read_configuration(path: Path) -> tuple[bytes | None, dict]:
    if path.is_symlink():
        raise SetupError(f"{path} is a symlink. Configure this client manually to preserve your dotfile setup.")
    try:
        original = path.read_bytes() if path.exists() else None
        if original is None:
            return None, {}
        text = original.decode("utf-8")
        document = tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)
        if not isinstance(document, dict):
            raise ValueError
        return original, document
    except (ValueError, UnicodeError):
        raise UnparsableConfiguration(
            f"Cannot parse {path}; it was left untouched. Use the manual instructions "
            "for comments, JSONC, or malformed configuration.",
            original,
        ) from None


def backup_configuration(path: Path, original: bytes | None) -> Path | None:
    if original is None:
        return None
    backup = path.with_name(f"{path.name}.{uuid4().hex}.bak")
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(original)
    return backup


def replace_configuration(path: Path, content: bytes, previous: bytes | None) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
        current = path.read_bytes() if path.exists() else None
        if current != previous:
            raise SetupError(f"{path} changed during setup; retry after closing its editor.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_configuration(path: Path, document: dict, previous: bytes | None) -> None:
    content = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    replace_configuration(path, content, previous)


def restore_server_entry(client: Client, path: Path, entry, backup: Path | None) -> None:
    try:
        current, document = read_configuration(path)
        servers = document.setdefault(client.key, {})
        if not isinstance(servers, dict):
            raise SetupError
        servers["loom"] = entry
        write_configuration(path, document, current)
    except (SetupError, OSError):
        raise SetupError(
            f"{client.name} registration failed, and the previous loom entry could not be restored. "
            f"Restore it from the backup: {backup}"
        ) from None


def registration_command(client: Client, command: str, executable: Path) -> list[str]:
    if client.command == "claude":
        return [command, "mcp", "add", "--transport", "stdio", "--scope", "user", "loom", "--", str(executable)]
    if client.command == "codex":
        return [command, "mcp", "add", "loom", "--", str(executable)]
    if client.command == "gemini":
        return [command, "mcp", "add", "--scope", "user", "--transport", "stdio", "loom", str(executable)]
    return [command, "--profile", "Default", "--add-mcp", json.dumps({
        "name": "loom", "type": "stdio", "command": str(executable),
    })]


def register_client(client: Client, executable: Path, home: Path, approve=confirm) -> str:
    path = home / client.config
    overrides = {
        "claude": ("CLAUDE_CONFIG_DIR", ".claude.json"),
        "codex": ("CODEX_HOME", "config.toml"),
        "gemini": ("GEMINI_CLI_HOME", ".gemini/settings.json"),
    }
    if client.command in overrides:
        variable, relative_path = overrides[client.command]
        custom_directory = os.getenv(variable)
        if custom_directory is not None and (Path(custom_directory).expanduser() / relative_path).absolute() != path.absolute():
            raise SetupError(
                f"{client.name} uses {variable} to select a custom configuration directory. "
                "Use the manual client instructions for that directory; no settings were changed."
            )
    try:
        original, document = read_configuration(path)
    except UnparsableConfiguration as error:
        if not client.command:
            raise
        if not approve(
            f"{path} cannot be parsed, so an existing loom entry cannot be checked. "
            f"Register through the {client.name} CLI anyway?"
        ):
            return "Skipped; configuration left untouched"
        original, document = error.original, {}
    servers = document.get(client.key, {})
    if not isinstance(servers, dict):
        raise SetupError(f"Invalid server settings in {path}; nothing was changed.")
    expected = {"command": str(executable)}
    if client.command == "code":
        expected["type"] = "stdio"
    existing = servers.get("loom")
    normalized = dict(existing) if isinstance(existing, dict) else existing
    if isinstance(normalized, dict) and normalized.get("args") == []:
        normalized.pop("args")
    if isinstance(normalized, dict):
        if normalized.get("env") == {}:
            normalized.pop("env")
        if normalized.get("enabled") is True:
            normalized.pop("enabled")
        if client.command != "code" and normalized.get("type") == "stdio":
            normalized.pop("type")
    if normalized == expected:
        return "Already configured"
    if "loom" in servers and not approve(
        f"{client.name} already has a loom entry. Replace it with {executable}?"
    ):
        return "Skipped; existing entry kept"
    command = find_executable(client.command) if client.command else None
    if client.command and not command:
        raise SetupError(f"{client.name} command is unavailable. Install its CLI or use manual configuration.")
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = backup_configuration(path, original)
    if command:
        removed_existing = False
        if client.command == "claude" and "loom" in servers:
            result = subprocess.run(
                [command, "mcp", "remove", "loom", "--scope", "user"],
                capture_output=True, timeout=60, check=False,
            )
            if result.returncode:
                raise SetupError(f"{client.name} could not replace its entry. Backup: {backup}")
            removed_existing = True
        try:
            result = subprocess.run(
                registration_command(client, command, executable),
                capture_output=True, timeout=60, check=False,
            )
            if result.returncode:
                raise SetupError(f"{client.name} registration failed. Check the client CLI. Backup: {backup or 'not needed'}")
        except (SetupError, OSError, subprocess.TimeoutExpired, KeyboardInterrupt):
            if removed_existing:
                restore_server_entry(client, path, existing, backup)
            raise
    else:
        servers["loom"] = expected
        document[client.key] = servers
        write_configuration(path, document, original)
    return f"Configured (backup: {backup})" if backup else "Configured"


def save_cookie() -> None:
    result = subprocess.run(
        ["/usr/bin/security", "add-generic-password", "-U", "-s", "loom-mcp",
         "-a", "connect.sid", "-w"],
        check=False,
    )
    if result.returncode:
        raise SetupError("Keychain did not save the cookie. Run loom-mcp setup to retry.")


def setup_cookie() -> bool:
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", "loom-mcp", "-a", "connect.sid"],
        capture_output=True, check=False, timeout=30,
    )
    if result.returncode == 0:
        print("A Loom cookie is already stored in Keychain.")
        if not confirm("Replace it with a fresh cookie?"):
            return True
    print("\n  1. Import from your signed-in Chrome session (Chrome 144+)")
    print("  2. Paste a cookie manually")
    while True:
        method = input("Choose cookie source (1 or 2; Enter to skip): ").strip()
        if not method:
            return False
        if method in {"1", "2"}:
            break
        print("Choose 1 or 2, or press Enter to skip.")
    if method == "1":
        print("Open a signed-in https://www.loom.com tab in your usual Chrome profile.")
        print("Enable chrome://inspect/#remote-debugging in Chrome 144+.")
        print("Chrome will ask you to Allow a debugging connection (up to 60 seconds).")
        print("This permission grants broad browser access; setup only reads the Loom session cookie.")
        if not confirm("Connect to Chrome and save the Loom cookie in Keychain?"):
            return False
        while True:
            try:
                open_in_chrome()
                cookie = read_chrome_cookie()
                try:
                    store_cookie(cookie)
                finally:
                    del cookie
                print("Loom cookie saved in Keychain. The Chrome connection is closed.")
                print("You can turn remote debugging off again in Chrome.")
                return True
            except ChromeDebuggingOff as error:
                print(str(error))
                if not confirm("Open Chrome's remote debugging page now?"):
                    break
                open_in_chrome(REMOTE_DEBUGGING_PAGE)
                print(f"If the page did not open, paste {REMOTE_DEBUGGING_PAGE} into Chrome's address bar.")
                input("Turn on remote debugging there, then press Enter to connect again. ")
            except ChromeError as error:
                print(str(error))
                if not confirm("Try connecting to Chrome again?"):
                    break
            except KeychainError as error:
                print(str(error))
                break
        if not confirm("Use manual cookie entry instead?"):
            return False
    print("\nSign in to loom.com in your browser.")
    print("Open DevTools > Application > Cookies > connect.sid and copy only its value.")
    print("The macOS password prompt below hides your input; paste the value there.")
    if not confirm("Ready to save the cookie in Keychain?"):
        print("Cookie setup skipped. Run loom-mcp setup when ready.")
        return False
    save_cookie()
    return True


def run_setup(executable: Path) -> int:
    if sys.platform != "darwin":
        raise SetupError("Setup requires macOS Keychain.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SetupError("Run loom-mcp setup in an interactive Terminal.")
    print("Loom MCP setup — metadata, transcripts, and frames; read-only access to Loom.")
    print(f"Server: {executable}\n")
    for index, client in enumerate(CLIENTS, 1):
        suffix = " (Default profile)" if client.command == "code" else ""
        print(f"  {index}. {client.name}{suffix}")
    print("  0. Cookie only / no client changes")
    while True:
        answer = input("Choose client numbers separated by spaces (Enter to cancel): ").strip()
        if not answer:
            print("Cancelled. No changes made.")
            return 0
        try:
            numbers = list(dict.fromkeys(int(value) for value in answer.replace(",", " ").split()))
            if numbers == [0] or all(1 <= number <= len(CLIENTS) for number in numbers):
                break
        except ValueError:
            pass
        print("Enter numbers from the list, for example 1 3, or 0 for cookie only.")
    selected = [] if numbers == [0] else [CLIENTS[number - 1] for number in numbers]
    if selected and not confirm("Configure " + ", ".join(client.name for client in selected) + "?"):
        print("Cancelled. No changes made.")
        return 0
    ffmpeg = find_executable("ffmpeg")
    print(f"\nffmpeg: {ffmpeg or 'missing — install with brew install ffmpeg for frames'}")
    ready = setup_cookie()
    failures = []
    for client in selected:
        try:
            status = register_client(client, executable, Path.home())
            print(f"{client.name}: {status}")
            if status.startswith("Skipped"):
                failures.append(client.name)
        except (SetupError, OSError, subprocess.TimeoutExpired) as error:
            message = str(error) if isinstance(error, SetupError) else "Local access failed or timed out; retry setup."
            print(f"{client.name}: {message}")
            failures.append(client.name)
    print("\nRestart configured clients, then ask them to read a Loom share URL.")
    if not ready:
        print("A Loom cookie is still required before the tools can read videos.")
    if failures:
        print("Not configured: " + ", ".join(failures))
    return 1 if failures or not ready else 0
