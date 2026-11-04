"""
Runs a command safely and returns what it printed.

The command is a fixed list of words (never a shell line), it must finish within a time limit,
and its output is capped so one runaway command cannot fill memory.
"""

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import List

from constants import COMMAND_TIMEOUT_SECONDS, MAX_COMMAND_OUTPUT_CHARS
from errors import CommandError

log = logging.getLogger(__name__)

TRUNCATION_MARKER = "\n...[truncated]"


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


def run_command(argv: List[str], timeout_seconds: int = COMMAND_TIMEOUT_SECONDS) -> CommandResult:
    if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
        raise CommandError(f"argv must be a non-empty list of non-empty strings, got {argv!r}")
    if shutil.which(argv[0]) is None:
        raise CommandError(f"'{argv[0]}' is not installed or not on PATH")

    # Only the command and its first words are logged; later words can hold user search text.
    summary = " ".join(argv[:3])
    log.info("Running command: %s", summary)
    started = time.monotonic()
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        log.warning("Command timed out after %ss: %s", timeout_seconds, summary)
        raise CommandError(f"'{summary}' did not finish within {timeout_seconds}s. Retry with a lower limit.") from exc
    log.info("Command finished in %.1fs with exit code %s: %s", time.monotonic() - started, completed.returncode, summary)
    return CommandResult(
        exit_code=completed.returncode,
        stdout=_cap_output(completed.stdout or ""),
        stderr=_cap_output(completed.stderr or ""),
    )


def _cap_output(text: str) -> str:
    if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
        return text
    return text[:MAX_COMMAND_OUTPUT_CHARS] + TRUNCATION_MARKER
