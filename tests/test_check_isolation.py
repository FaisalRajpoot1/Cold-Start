"""The check must never run outside the workspace it was given.

WHY THIS FILE EXISTS

The first implementation of `run_check` handled a missing workspace by walking up
the directory tree until it found one that existed, and running the command there
-- falling back to the current working directory at the filesystem root. The
reasoning given was that the command "will still fail because whatever
postcondition it checks for won't be present".

That reasoning does not hold, and the failure is silent.

A realistic check for "install the project" is:

    python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('pyproject.toml').exists() else 1)"

If the workspace is absent and the walk-up reaches Cold Start's own repository,
that command finds Cold Start's `pyproject.toml`, exits 0, and the step is
recorded as **passed** -- for a step whose workspace was never even created.

Measured before the fix, from the project root:

    workspaces/ws-04       exists=False  verdict=pass  <-- false green
    nope/deeper/ws-07      exists=False  verdict=pass  <-- false green
    target/ws-04           exists=False  verdict=fail

Two false greens out of three. This is precisely the failure Cold Start exists to
expose -- a confident, wrong success -- occurring inside the one module whose
entire job is to be the thing that cannot be fooled.

THE RULE

A missing workspace is a FAIL, decided without running anything. The check never
executes outside the directory it was handed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coldstart.check import run_check

# A realistic postcondition: "the project installed, so this file is here."
# Cold Start's own repository root contains pyproject.toml, which is what makes
# the escape dangerous rather than merely untidy.
LOOKS_FOR_PYPROJECT = [
    "python",
    "-c",
    "import pathlib,sys; sys.exit(0 if pathlib.Path('pyproject.toml').exists() else 1)",
]


@pytest.mark.contract
def test_missing_workspace_never_passes(tmp_path, monkeypatch):
    """A workspace that does not exist must fail, even standing in a directory
    where the check's target file is present."""
    # Stand somewhere that DOES contain pyproject.toml, so a leaked cwd would pass.
    (tmp_path / "pyproject.toml").write_text("[project]\nname='decoy'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    record = run_check(LOOKS_FOR_PYPROJECT, tmp_path / "does-not-exist" / "ws-04")

    assert record["verdict"] == "fail", (
        "A step whose workspace was never created was reported as PASSED. "
        "The check escaped its workspace and found a file elsewhere."
    )


@pytest.mark.contract
def test_missing_workspace_is_reported_distinctly(tmp_path):
    """'Your workspace is missing' and 'your command exited 1' are different
    problems and must not look identical in checks.json.

    -2 is reserved for it: never a real process exit code, so it cannot collide
    with a genuine failure.
    """
    record = run_check(LOOKS_FOR_PYPROJECT, tmp_path / "absent" / "ws-09")

    assert record["exit_code"] == -2
    assert record["verdict"] == "fail"
    assert "workspace" in record["stderr_tail"].lower(), (
        "stderr_tail must say the workspace was missing, or a reader cannot tell "
        "this apart from an ordinary failure"
    )


@pytest.mark.contract
def test_missing_workspace_runs_nothing_at_all(tmp_path, monkeypatch):
    """The verdict must be reached WITHOUT executing the command.

    Deciding first and running second is the only version that cannot leak. If a
    later refactor reintroduces a fallback directory, this fires.
    """
    called: list[object] = []

    def _tripwire(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("subprocess was invoked for a missing workspace")

    monkeypatch.setattr("coldstart.check.subprocess.run", _tripwire)

    record = run_check(["python", "-c", "pass"], tmp_path / "absent" / "ws-03")

    assert not called, "no command may run when the workspace is missing"
    assert record["verdict"] == "fail"
    assert record["exit_code"] == -2


@pytest.mark.contract
def test_a_file_where_the_workspace_should_be_is_also_a_fail(tmp_path):
    """Guards NotADirectoryError (WinError 267) on Windows.

    `Path.exists()` is True for a file, so an existence check alone is not enough
    -- the path must be a DIRECTORY.
    """
    not_a_dir = tmp_path / "ws-05"
    not_a_dir.write_text("this is a file, not a workspace", encoding="utf-8")

    record = run_check(["python", "-c", "pass"], not_a_dir)

    assert record["verdict"] == "fail"
    assert record["exit_code"] == -2


def test_a_real_workspace_still_works_normally(tmp_path):
    """The fix must not break the ordinary path.

    A check is only meaningful if it genuinely runs when the workspace is there.
    """
    ws = tmp_path / "ws-01"
    ws.mkdir()
    (ws / "pyproject.toml").write_text("[project]\nname='real'\n", encoding="utf-8")

    passing = run_check(LOOKS_FOR_PYPROJECT, ws)
    assert passing["verdict"] == "pass"
    assert passing["exit_code"] == 0

    empty = tmp_path / "ws-02"
    empty.mkdir()
    failing = run_check(LOOKS_FOR_PYPROJECT, empty)
    assert failing["verdict"] == "fail"
    assert failing["exit_code"] == 1


def test_the_check_really_runs_in_the_workspace(tmp_path):
    """Positive proof of isolation: the command sees the workspace's own files,
    not the caller's."""
    ws = tmp_path / "ws-07"
    ws.mkdir()
    (ws / "marker.txt").write_text("here", encoding="utf-8")

    record = run_check(
        ["python", "-c", "import pathlib; print(pathlib.Path('marker.txt').read_text())"],
        ws,
    )

    assert record["exit_code"] == 0
    assert "here" in record["stdout_tail"]
