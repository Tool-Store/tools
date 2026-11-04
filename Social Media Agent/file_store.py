"""
Writes files so that a crash or a parallel reader never sees half a file.

The new content goes to a temporary file next to the target, which then replaces the target in one step.
Files are readable by the server user only, because they hold usage counts and saved logins.
"""

from pathlib import Path


def write_atomically(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.chmod(0o600)
    temporary.replace(path)
