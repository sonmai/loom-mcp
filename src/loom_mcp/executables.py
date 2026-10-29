import os
import shutil
from pathlib import Path


def find_executable(name: str) -> str | None:
    directories = [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path.home() / ".local/bin"]
    if name == "code":
        directories.extend([
            Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin"),
            Path.home() / "Applications/Visual Studio Code.app/Contents/Resources/app/bin",
        ])
    for directory in directories:
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)
