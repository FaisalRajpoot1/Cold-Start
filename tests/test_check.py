"""Tests for coldstart/check.py.

Golden-file test: committed input → asserted exact output.

The only non-deterministic field in a check record is ``duration_ms``.
We patch ``time.monotonic`` to return a fixed sequence so the output is
byte-identical regardless of machine speed.

No network. No model. Ever.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import coldstart.check as check_mod
from coldstart.check import check, run_check
from coldstart.schema import ContractError, validate_checks

GOLDEN_DIR = Path(__file__).parent / "golden"
INPUT_STEPS = GOLDEN_DIR / "checks_input_steps.json"
EXPECTED_OUTPUT = GOLDEN_DIR / "checks_output.json"


# ------------------------------------------------------------------ golden test


@pytest.mark.golden
def test_check_golden(tmp_path):
    """Committed input → byte-identical output.

    time.monotonic is patched to always return 0 so duration_ms is
    deterministic regardless of machine speed.
    """
    output_path = tmp_path / "checks.json"

    # Workspaces don't need to exist: the check commands are pure Python
    # one-liners (sys.exit) that don't look at the filesystem, so check.py
    # will fall back to the parent directory when ws-NN is absent.
    with patch.object(check_mod.time, "monotonic", return_value=0.0):
        check(
            steps_path=INPUT_STEPS,
            target_dir=tmp_path / "target",
            output_path=output_path,
        )

    actual = json.loads(output_path.read_text(encoding="utf-8"))
    expected = json.loads(EXPECTED_OUTPUT.read_text(encoding="utf-8"))
    assert actual == expected, (
        "check.py output does not match the golden file.\n"
        "If the contract changed intentionally, re-generate tests/golden/checks_output.json."
    )


@pytest.mark.golden
def test_check_output_is_byte_stable(tmp_path):
    """Same inputs in, byte-identical bytes out (AGENTS.md rule 5)."""
    out1 = tmp_path / "c1.json"
    out2 = tmp_path / "c2.json"

    with patch.object(check_mod.time, "monotonic", return_value=0.0):
        check(steps_path=INPUT_STEPS, target_dir=tmp_path / "target", output_path=out1)
        check(steps_path=INPUT_STEPS, target_dir=tmp_path / "target", output_path=out2)

    assert out1.read_bytes() == out2.read_bytes()


# ----------------------------------------------------- run_check unit tests


def test_run_check_pass(tmp_path):
    """exit 0 → verdict pass."""
    result = run_check(["python", "-c", "import sys; sys.exit(0)"], cwd=tmp_path)
    assert result["exit_code"] == 0
    assert result["verdict"] == "pass"
    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0


def test_run_check_fail(tmp_path):
    """exit non-zero → verdict fail."""
    result = run_check(["python", "-c", "import sys; sys.exit(2)"], cwd=tmp_path)
    assert result["exit_code"] == 2
    assert result["verdict"] == "fail"


def test_run_check_stdout_tail(tmp_path):
    """stdout is captured and the last 500 chars are stored."""
    result = run_check(
        ["python", "-c", "import sys; sys.stdout.write('hello'); sys.exit(0)"],
        cwd=tmp_path,
    )
    assert "hello" in result["stdout_tail"]


def test_run_check_stderr_tail(tmp_path):
    """stderr is captured and the last 500 chars are stored."""
    result = run_check(
        ["python", "-c", "import sys; sys.stderr.write('oops'); sys.exit(1)"],
        cwd=tmp_path,
    )
    assert "oops" in result["stderr_tail"]
    assert result["verdict"] == "fail"


def test_run_check_missing_workspace_falls_back(tmp_path):
    """If the workspace dir does not exist, the check still runs (in parent dir).

    The command will still fail if it relies on workspace content, which is the
    honest answer — the step was never run.
    """
    missing_ws = tmp_path / "ws-99"
    assert not missing_ws.exists()
    # A command that doesn't care about cwd, so we can observe it still runs.
    result = run_check(["python", "-c", "import sys; sys.exit(0)"], cwd=missing_ws)
    assert result["verdict"] == "pass"


def test_run_check_command_not_found(tmp_path):
    """A missing executable gets exit_code 127 and verdict fail."""
    result = run_check(["__no_such_binary_xyzzy__"], cwd=tmp_path)
    assert result["exit_code"] == 127
    assert result["verdict"] == "fail"
    assert "__no_such_binary_xyzzy__" in result["stderr_tail"]


def test_run_check_timeout(tmp_path):
    """A command that exceeds the timeout gets exit_code 124 and verdict fail."""
    # Patch the timeout to 0 so the sleep immediately exceeds it.
    with patch.object(check_mod, "_CHECK_TIMEOUT", 0):
        result = run_check(
            ["python", "-c", "import time; time.sleep(10)"],
            cwd=tmp_path,
        )
    assert result["exit_code"] == 124
    assert result["verdict"] == "fail"
    assert "timed out" in result["stderr_tail"]


# ------------------------------------------------------- integration: output validates


def test_output_passes_schema_validation(tmp_path):
    """The artifact check.py writes must pass the schema contract."""
    out = tmp_path / "checks.json"
    with patch.object(check_mod.time, "monotonic", return_value=0.0):
        check(steps_path=INPUT_STEPS, target_dir=tmp_path / "target", output_path=out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    validate_checks(doc)  # raises ContractError on any violation


def test_broken_artifact_never_reaches_disk(tmp_path):
    """If the output would be invalid, dump_validated must not write it.

    We trigger this by patching run_check to return a verdict that contradicts
    the exit code (exit_code=0 but verdict='fail'), which the schema enforces.
    """
    bad_record = {
        "step_id": 1,
        "cmd": ["python", "-c", "import sys; sys.exit(0)"],
        "exit_code": 0,
        "stdout_tail": "",
        "stderr_tail": "",
        "duration_ms": 0,
        "verdict": "fail",  # contradicts exit_code=0
    }

    def _bad_run_check(cmd, cwd):
        r = dict(bad_record)
        del r["step_id"]
        return r

    out = tmp_path / "checks.json"
    with patch.object(check_mod, "run_check", side_effect=_bad_run_check):
        with pytest.raises(ContractError):
            check(steps_path=INPUT_STEPS, target_dir=tmp_path / "target", output_path=out)
    assert not out.exists(), "a rejected artifact must not be left on disk"


# ------------------------------------------------------- tail truncation


def test_tail_truncation():
    """_tail keeps the last _TAIL_BYTES characters."""
    from coldstart.check import _tail

    long_output = b"x" * 1000
    result = _tail(long_output)
    assert len(result) == check_mod._TAIL_BYTES
    assert result == "x" * check_mod._TAIL_BYTES


def test_tail_replacement_on_bad_bytes():
    """_tail does not crash on non-UTF-8 bytes."""
    from coldstart.check import _tail

    bad = b"\xff\xfe"
    result = _tail(bad)
    assert isinstance(result, str)
