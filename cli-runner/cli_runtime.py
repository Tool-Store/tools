"""CLI runtime: install tracking, binary checks, and safe command execution."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 600
MAX_OUTPUT_CHARS = 200_000
STATE_PATH = Path(os.getenv("CLI_RUNNER_STATE_PATH", "/app/data/installed.json"))

_DENIED_INSTALL_PATTERNS = (
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+if="),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;"),
    re.compile(r"\bcurl\b.+\|\s*(ba)?sh"),
    re.compile(r"\bwget\b.+\|\s*(ba)?sh"),
)


class CliRuntimeError(ValueError):
    """Raised when a CLI runtime operation is invalid or unsafe."""


def _ensure_state_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict[str, Any]:
    _ensure_state_dir()
    if not STATE_PATH.is_file():
        return {"skills": {}}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliRuntimeError(f"Corrupt install state at {STATE_PATH}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CliRuntimeError(f"Install state must be a JSON object: {STATE_PATH}")
    skills = payload.get("skills")
    if skills is None:
        payload["skills"] = {}
    elif not isinstance(skills, dict):
        raise CliRuntimeError("Install state 'skills' must be an object")
    return payload


def _save_state(payload: dict[str, Any]) -> None:
    _ensure_state_dir()
    STATE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require_slug(skill_slug: str) -> str:
    slug = (skill_slug or "").strip().lower()
    if not slug:
        raise CliRuntimeError("skill_slug is required")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise CliRuntimeError("skill_slug must be lowercase kebab-case")
    return slug


def get_install_status(skill_slug: str) -> dict[str, Any]:
    slug = _require_slug(skill_slug)
    record = _load_state()["skills"].get(slug)
    if not isinstance(record, dict):
        return {"skill_slug": slug, "installed": False}
    return {
        "skill_slug": slug,
        "installed": True,
        "bins": list(record.get("bins") or []),
        "installed_at": record.get("installed_at"),
    }


def check_binary(binary: str) -> dict[str, Any]:
    name = (binary or "").strip()
    if not name:
        raise CliRuntimeError("binary is required")
    if "/" in name or name.startswith("."):
        raise CliRuntimeError("binary must be a bare command name on PATH")
    path = shutil.which(name)
    return {"binary": name, "available": path is not None, "path": path}


def _validate_install_step(step: str) -> str:
    command = (step or "").strip()
    if not command:
        raise CliRuntimeError("install step must be a non-empty command")
    if "\n" in command or "\r" in command:
        raise CliRuntimeError("install step must be a single line")
    for pattern in _DENIED_INSTALL_PATTERNS:
        if pattern.search(command):
            raise CliRuntimeError(f"install step rejected by safety policy: {command}")
    return command


def _clamp_timeout(timeout_seconds: int | None) -> int:
    if timeout_seconds is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = int(timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise CliRuntimeError("timeout_seconds must be an integer") from exc
    if value < 1:
        raise CliRuntimeError("timeout_seconds must be >= 1")
    return min(value, MAX_TIMEOUT_SECONDS)


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n...[truncated]..."


def _run_subprocess(
    argv: list[str],
    *,
    timeout_seconds: int,
    shell: bool = False,
) -> dict[str, Any]:
    if not argv:
        raise CliRuntimeError("command argv must not be empty")
    log.info("cli_runner_exec shell=%s argv=%s", shell, argv if not shell else argv[0])
    try:
        completed = subprocess.run(
            argv if not shell else argv[0],
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CliRuntimeError(f"command timed out after {timeout_seconds}s: {argv}") from exc
    except FileNotFoundError as exc:
        raise CliRuntimeError(f"executable not found: {argv[0]}") from exc
    return {
        "argv": argv if not shell else [argv[0]],
        "exit_code": completed.returncode,
        "stdout": _truncate(completed.stdout or ""),
        "stderr": _truncate(completed.stderr or ""),
        "ok": completed.returncode == 0,
    }


def install_skill_runtime(
    skill_slug: str,
    *,
    bins: list[str] | None = None,
    install_steps: list[str] | None = None,
    timeout_seconds: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Install skill binaries once. Skips when already marked installed unless force=True."""
    slug = _require_slug(skill_slug)
    timeout = _clamp_timeout(timeout_seconds)
    requested_bins = [str(item).strip() for item in (bins or []) if str(item).strip()]
    steps = [_validate_install_step(str(step)) for step in (install_steps or [])]

    status = get_install_status(slug)
    if status.get("installed") and not force:
        missing = [name for name in requested_bins if not check_binary(name)["available"]]
        return {
            "skill_slug": slug,
            "skipped": True,
            "reason": "already_installed",
            "bins": status.get("bins") or requested_bins,
            "missing_bins": missing,
            "steps_run": [],
        }

    step_results: list[dict[str, Any]] = []
    for step in steps:
        result = _run_subprocess([step], timeout_seconds=timeout, shell=True)
        step_results.append({"step": step, **result})
        if not result["ok"]:
            raise CliRuntimeError(
                f"install step failed for '{slug}' (exit {result['exit_code']}): {step}\n{result['stderr']}"
            )

    missing_after = [name for name in requested_bins if not check_binary(name)["available"]]
    if missing_after:
        raise CliRuntimeError(
            f"install finished but required binaries still missing for '{slug}': {', '.join(missing_after)}"
        )

    state = _load_state()
    state["skills"][slug] = {
        "bins": requested_bins,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
    }
    _save_state(state)

    return {
        "skill_slug": slug,
        "skipped": False,
        "bins": requested_bins,
        "missing_bins": [],
        "steps_run": step_results,
    }


def run_cli_command(
    argv: list[str],
    *,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Run a CLI as argv list (no shell). Prefer this for skill action execution."""
    if not isinstance(argv, list) or not argv:
        raise CliRuntimeError(
            "argv must be a non-empty list, e.g. ['agent-browser', 'screenshot', 'out.png']"
        )
    cleaned: list[str] = []
    for part in argv:
        token = str(part).strip()
        if not token:
            raise CliRuntimeError("argv entries must be non-empty strings")
        cleaned.append(token)
    if "/" in cleaned[0] or cleaned[0].startswith("."):
        raise CliRuntimeError("command binary must be a bare name on PATH (no paths)")
    if shutil.which(cleaned[0]) is None:
        raise CliRuntimeError(f"binary not found on PATH: {cleaned[0]}")
    return _run_subprocess(cleaned, timeout_seconds=_clamp_timeout(timeout_seconds), shell=False)
