import subprocess


class KeychainError(Exception):
    pass


def is_valid_session_cookie(value: str) -> bool:
    return bool(value) and not value.startswith('connect.sid=') and not any(
        ord(character) < 33 or ord(character) > 126 or character == ';' for character in value
    )


def store_cookie(cookie: str) -> None:
    """Save the cookie through /usr/bin/security, the program the server reads it with.

    Deliberately not Security.framework from Python: an item created that way lands in a
    Keychain partition that /usr/bin/security cannot read without an access prompt.
    The value is sent on stdin to `security -i`, never as a process argument.
    """
    # `security -i` splits its input like a shell, so quoting characters could alter the command.
    if not is_valid_session_cookie(cookie) or any(character in cookie for character in '"\'\\'):
        raise KeychainError('Cannot save an invalid Loom session cookie.')
    try:
        result = subprocess.run(
            ['/usr/bin/security', '-i'],
            input=f'add-generic-password -U -s loom-mcp -a connect.sid -w "{cookie}"\n',
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is None or result.returncode:
        raise KeychainError('Keychain did not save the cookie. Allow access if prompted, or use manual entry.')
