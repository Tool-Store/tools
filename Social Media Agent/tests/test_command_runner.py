import sys

import pytest

import command_runner
from command_runner import run_command
from errors import CommandError


def test_successful_command_returns_its_output():
    result = run_command([sys.executable, "-c", "print('hello')"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""


def test_failing_command_returns_exit_code_instead_of_raising():
    result = run_command([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])

    assert result.exit_code == 3
    assert result.stderr == "boom"


def test_slow_command_raises_timeout_error():
    with pytest.raises(CommandError, match="did not finish within 1s"):
        run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout_seconds=1)


def test_missing_binary_is_rejected():
    with pytest.raises(CommandError, match="not installed or not on PATH"):
        run_command(["no-such-binary-for-tests"])


@pytest.mark.parametrize("argv", [[], [""], ["echo", ""], "echo hello"], ids=["empty", "blank", "blank-arg", "string"])
def test_invalid_argv_is_rejected(argv):
    with pytest.raises(CommandError, match="argv must be a non-empty list"):
        run_command(argv)


def test_long_output_is_capped(monkeypatch):
    monkeypatch.setattr(command_runner, "MAX_COMMAND_OUTPUT_CHARS", 10)

    result = run_command([sys.executable, "-c", "print('x' * 50)"])

    assert result.stdout == "x" * 10 + command_runner.TRUNCATION_MARKER
