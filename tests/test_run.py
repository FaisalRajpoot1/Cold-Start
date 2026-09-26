"""Tests for coldstart/run.py.

NONE of these tests touch the network. subprocess.run is stubbed via
monkeypatch wherever a Bob invocation would otherwise be needed.

The most important test in this file is test_error_frame_overrides_status.
Bob's result event always carries status="success" — even on a capped run that
wrote nothing. The ONLY true failure signal is the presence of error_frames.
That test encodes this invariant explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from coldstart.run import (
    _parse_ndjson,
    _prepare_workspace,
    _run_one_step,
    run,
)
from coldstart.schema import validate_runs

# Fake absolute bob path used for all _run_one_step unit tests.
# Must be an absolute path so Path(...).is_absolute() checks pass.
_FAKE_BOB_EXE = str(Path("/fake/bob").resolve())

# ---------------------------------------------------------------------------
# Canned NDJSON fixtures
# ---------------------------------------------------------------------------

# A clean successful run: result event carries real cost/duration/tool data.
_CLEAN_NDJSON = "\n".join([
    json.dumps({"type": "message", "role": "assistant", "content": "Installing deps..."}),
    json.dumps({"type": "message", "role": "assistant", "content": "Done."}),
    json.dumps({
        "type": "result",
        "status": "success",
        "taskId": "abc123",
        "durationMs": 41233,
        "sessionCost": 0.4831,
        "toolCalls": 7,
    }),
]).encode()

# A capped run: result event still says "success" but an error frame carries
# the cost-limit wording. This is the exact scenario documented in
# docs/ARCHITECTURE.md — both emitters in bob.js hardcode "success".
_CAPPED_NDJSON = "\n".join([
    json.dumps({"type": "message", "role": "assistant", "content": "Working..."}),
    json.dumps({
        "type": "error",
        "message": "The task reached the cost limit of 1.500 (spent: 1.512).",
    }),
    json.dumps({
        "type": "result",
        "status": "success",   # <-- always "success", even on a cap
        "taskId": "def456",
        "durationMs": 5000,
        "sessionCost": 1.512,
        "toolCalls": 3,
    }),
]).encode()

# A run with a non-cap error frame.
_ERROR_NDJSON = "\n".join([
    json.dumps({"type": "error", "message": "Something went wrong."}),
    json.dumps({
        "type": "result",
        "status": "success",
        "taskId": "ghi789",
        "durationMs": 1000,
        "sessionCost": 0.1,
        "toolCalls": 1,
    }),
]).encode()

# NDJSON with a malformed line in the middle.
_MALFORMED_NDJSON = "\n".join([
    json.dumps({"type": "message", "role": "assistant", "content": "Hi"}),
    "NOT VALID JSON {{{",
    json.dumps({
        "type": "result",
        "status": "success",
        "taskId": "jkl000",
        "durationMs": 500,
        "sessionCost": 0.05,
        "toolCalls": 0,
    }),
]).encode()

# Minimal valid steps.json document used throughout.
def _steps_doc(n: int = 2) -> dict:
    from coldstart.schema import STEPS_SCHEMA
    return {
        "schema": STEPS_SCHEMA,
        "source_repo": "example/repo",
        "source_commit": "0" * 40,
        "doc_path": "CONTRIBUTING.md",
        "doc_sha256": "a" * 64,
        "steps": [
            {
                "id": i,
                "title": f"Step {i}",
                "doc_lines": [i * 2 - 1, i * 2],
                "quote": f"quote {i}",
                "kind": "command",
                "bob_prompt": f"Do step {i}.",
                "check": {
                    "cmd": ["python", "-c", "import sys; sys.exit(0)"],
                    "describes": "something",
                },
                "expected": "green",
            }
            for i in range(1, n + 1)
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_proc(stdout: bytes, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


def _write_steps(tmp_path: Path, n: int = 2) -> Path:
    from coldstart.schema import dump_validated
    p = tmp_path / "steps.json"
    dump_validated(_steps_doc(n), p)
    return p


def _make_pristine(tmp_path: Path) -> Path:
    pristine = tmp_path / "_pristine"
    pristine.mkdir()
    (pristine / "README.md").write_text("hello", encoding="utf-8")
    return pristine


# ---------------------------------------------------------------------------
# _parse_ndjson unit tests
# ---------------------------------------------------------------------------


def test_parse_clean_run():
    """Cost, duration, task_id and tool_calls are extracted correctly."""
    r = _parse_ndjson(_CLEAN_NDJSON)
    assert r["task_id"] == "abc123"
    assert r["duration_ms"] == 41233
    assert r["session_costs"] == pytest.approx(0.4831)
    assert r["tool_calls"] == 7
    assert r["bob_status"] == "success"
    assert r["error_frames"] == []
    assert r["capped"] is False
    assert r["bob_final_message"] == "Done."


def test_parse_capped_run():
    """An error frame matching the cost-limit wording sets capped=True."""
    r = _parse_ndjson(_CAPPED_NDJSON)
    assert r["capped"] is True
    assert len(r["error_frames"]) == 1
    assert "cost limit" in r["error_frames"][0]["message"].lower()
    # status is still "success" — that is the documented Bob behaviour
    assert r["bob_status"] == "success"


def test_parse_error_frame_non_cap():
    """An error frame that is not the cost-limit wording: capped stays False."""
    r = _parse_ndjson(_ERROR_NDJSON)
    assert r["error_frames"] != []
    assert r["capped"] is False


def test_parse_malformed_line_is_tolerated():
    """A line that is not valid JSON must not crash the parser."""
    r = _parse_ndjson(_MALFORMED_NDJSON)
    assert r["task_id"] == "jkl000"  # rest of the stream was parsed fine


def test_parse_empty_output():
    """Empty stdout produces zeros and empty strings, not an exception."""
    r = _parse_ndjson(b"")
    assert r["session_costs"] == 0.0
    assert r["task_id"] == ""
    assert r["error_frames"] == []
    assert r["capped"] is False


def test_parse_blank_lines_tolerated():
    """Blank lines in the stream must not cause a crash."""
    ndjson = b"\n\n" + json.dumps({"type": "result", "status": "success",
                                   "taskId": "x", "durationMs": 0,
                                   "sessionCost": 0.0, "toolCalls": 0}).encode() + b"\n\n"
    r = _parse_ndjson(ndjson)
    assert r["task_id"] == "x"


def test_parse_last_assistant_message_wins():
    """bob_final_message is the LAST assistant message, not the first."""
    ndjson = "\n".join([
        json.dumps({"type": "message", "role": "assistant", "content": "first"}),
        json.dumps({"type": "message", "role": "assistant", "content": "second"}),
        json.dumps({"type": "message", "role": "assistant", "content": "last"}),
        json.dumps({"type": "result", "status": "success", "taskId": "",
                    "durationMs": 0, "sessionCost": 0.0, "toolCalls": 0}),
    ]).encode()
    r = _parse_ndjson(ndjson)
    assert r["bob_final_message"] == "last"


# ---------------------------------------------------------------------------
# THE most important test in this file
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_error_frame_overrides_status(tmp_path, monkeypatch):
    """result.status="success" plus returncode=0 must NOT produce bob_claim="completed"
    when an error frame is present.

    This is the invariant the whole product is built on. Bob always reports
    "success" — even on a capped run — so we NEVER branch on result.status.
    Only the presence of error_frames determines bob_claim.
    """
    pristine = _make_pristine(tmp_path)
    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(_CAPPED_NDJSON),
    )

    record = _run_one_step(
        step=_steps_doc(1)["steps"][0],
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        max_cost=1.5,
        max_turns=12,
        bob_exe=_FAKE_BOB_EXE,
        bob_env={"BOB_API_KEY": "test"},
    )

    # result event said "success" — we record it faithfully
    assert record["bob_status"] == "success"
    # but bob_claim must be "failed" because error_frames is non-empty
    assert record["bob_claim"] == "failed", (
        "bob_claim must be derived from error_frames, not from result.status. "
        "Bob always emits status='success'; error_frames carry the truth."
    )
    assert record["capped"] is True
    assert len(record["error_frames"]) == 1


@pytest.mark.contract
def test_success_status_with_no_error_frames_gives_completed(tmp_path, monkeypatch):
    """Positive case: no error frames → bob_claim is 'completed'."""
    pristine = _make_pristine(tmp_path)
    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(_CLEAN_NDJSON),
    )

    record = _run_one_step(
        step=_steps_doc(1)["steps"][0],
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        max_cost=1.5,
        max_turns=12,
        bob_exe=_FAKE_BOB_EXE,
        bob_env={"BOB_API_KEY": "test"},
    )

    assert record["bob_claim"] == "completed"
    assert record["error_frames"] == []


# ---------------------------------------------------------------------------
# _run_one_step error-handling
# ---------------------------------------------------------------------------


def test_recording_written_before_parse_error(tmp_path, monkeypatch):
    """Raw NDJSON must be on disk even when the subsequent parse raises."""
    pristine = _make_pristine(tmp_path)
    raw = b"some raw bytes\n"

    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(raw),
    )
    # Make the parse blow up after the write.
    monkeypatch.setattr("coldstart.run._parse_ndjson", lambda b: (_ for _ in ()).throw(
        RuntimeError("parse exploded")
    ))

    rec_dir = tmp_path / "rec"
    record = _run_one_step(
        step=_steps_doc(1)["steps"][0],
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=rec_dir,
        max_cost=1.5,
        max_turns=12,
        bob_exe=_FAKE_BOB_EXE,
        bob_env={"BOB_API_KEY": "test"},
    )

    ndjson_file = rec_dir / "step-01.ndjson"
    assert ndjson_file.exists(), "recording must be on disk even when parse fails"
    assert ndjson_file.read_bytes() == raw
    assert record["bob_claim"] == "failed"
    assert record["error_frames"][0]["message"].startswith("NDJSON parse failed")


def test_subprocess_timeout_is_recorded(tmp_path, monkeypatch):
    """A TimeoutExpired is caught and recorded as an error_frame, not re-raised."""
    pristine = _make_pristine(tmp_path)

    def _timeout(*a, **kw):
        exc = __import__("subprocess").TimeoutExpired(cmd=["bob"], timeout=1)
        exc.output = b""
        raise exc

    monkeypatch.setattr("coldstart.run.subprocess.run", _timeout)

    record = _run_one_step(
        step=_steps_doc(1)["steps"][0],
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        max_cost=1.5,
        max_turns=12,
        bob_exe=_FAKE_BOB_EXE,
        bob_env={"BOB_API_KEY": "test"},
    )

    assert record["bob_claim"] == "failed"
    assert any("timed out" in f["message"] for f in record["error_frames"])


def test_os_error_is_recorded(tmp_path, monkeypatch):
    """An OSError from subprocess.run is caught and recorded."""
    pristine = _make_pristine(tmp_path)
    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("bob not found")),
    )

    record = _run_one_step(
        step=_steps_doc(1)["steps"][0],
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        max_cost=1.5,
        max_turns=12,
        bob_exe=_FAKE_BOB_EXE,
        bob_env={"BOB_API_KEY": "test"},
    )

    assert record["bob_claim"] == "failed"
    assert record["error_frames"]


# ---------------------------------------------------------------------------
# _prepare_workspace
# ---------------------------------------------------------------------------


def test_prepare_workspace_copies_and_excludes_git(tmp_path):
    """_prepare_workspace creates a copy of pristine without .git."""
    pristine = tmp_path / "_pristine"
    pristine.mkdir()
    (pristine / "README.md").write_text("hi", encoding="utf-8")
    git_dir = pristine / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]", encoding="utf-8")

    ws = tmp_path / "ws-01"
    _prepare_workspace(pristine, ws)

    assert (ws / "README.md").exists()
    assert not (ws / ".git").exists(), ".git must be excluded from the workspace"


def test_prepare_workspace_deletes_existing(tmp_path):
    """An existing workspace is deleted before the fresh copy."""
    pristine = tmp_path / "_pristine"
    pristine.mkdir()
    (pristine / "file.txt").write_text("new", encoding="utf-8")

    ws = tmp_path / "ws-01"
    ws.mkdir()
    (ws / "stale.txt").write_text("stale", encoding="utf-8")

    _prepare_workspace(pristine, ws)

    assert not (ws / "stale.txt").exists()
    assert (ws / "file.txt").exists()


# ---------------------------------------------------------------------------
# Budget guard
# ---------------------------------------------------------------------------


def test_budget_guard_stops_new_steps(tmp_path, monkeypatch):
    """Once accumulated spend reaches --budget, no new step starts."""
    steps_path = _write_steps(tmp_path, n=3)
    pristine = _make_pristine(tmp_path)

    call_count = 0

    def _fake_run(*a, **kw):
        nonlocal call_count
        call_count += 1
        # Each call costs 10 coins — well above the 15-coin budget after step 2.
        return _make_fake_proc(
            "\n".join([
                json.dumps({"type": "result", "status": "success", "taskId": "t",
                            "durationMs": 100, "sessionCost": 10.0, "toolCalls": 1}),
            ]).encode()
        )

    monkeypatch.setattr("coldstart.run.subprocess.run", _fake_run)
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    monkeypatch.setenv("BOB_API_KEY", "test-key")

    out = tmp_path / "runs.json"
    run(
        steps_path=steps_path,
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=out,
        max_cost=1.5,
        max_turns=12,
        concurrency=1,  # serial so the guard fires predictably
        budget=15.0,
        dry_run=False,
    )

    doc = json.loads(out.read_text(encoding="utf-8"))
    # Step 3 should have been skipped — total after step 1 = 10, after step 2 = 20 >= 15
    skipped = [r for r in doc["runs"] if r.get("bob_status") == "skipped"]
    assert skipped, "at least one step must be skipped when budget is exceeded"


# ---------------------------------------------------------------------------
# API key must not leak
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_api_key_not_in_runs_json(tmp_path, monkeypatch):
    """BOB_API_KEY must never appear anywhere in runs.json."""
    steps_path = _write_steps(tmp_path, n=1)
    pristine = _make_pristine(tmp_path)
    secret = "super-secret-key-do-not-leak"  # noqa: S105 — test sentinel, not a real credential

    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(_CLEAN_NDJSON),
    )
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    monkeypatch.setenv("BOB_API_KEY", secret)

    out = tmp_path / "runs.json"
    run(
        steps_path=steps_path,
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=out,
        budget=999.0,
    )

    content = out.read_text(encoding="utf-8")
    assert secret not in content, "API key must never appear in runs.json"


@pytest.mark.contract
def test_api_key_not_in_printed_output(tmp_path, monkeypatch, capsys):
    """BOB_API_KEY must never appear in any printed output."""
    steps_path = _write_steps(tmp_path, n=1)
    pristine = _make_pristine(tmp_path)
    secret = "top-secret-key-xyz"  # noqa: S105 — test sentinel, not a real credential

    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(_CLEAN_NDJSON),
    )
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    monkeypatch.setenv("BOB_API_KEY", secret)

    run(
        steps_path=steps_path,
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=tmp_path / "runs.json",
        budget=999.0,
    )

    out, err = capsys.readouterr()
    assert secret not in out, "API key must not appear in stdout"
    assert secret not in err, "API key must not appear in stderr"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_output_validates_against_schema(tmp_path, monkeypatch):
    """The runs.json produced must pass validate_runs without errors."""
    steps_path = _write_steps(tmp_path, n=2)
    pristine = _make_pristine(tmp_path)

    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(_CLEAN_NDJSON),
    )
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    monkeypatch.setenv("BOB_API_KEY", "test")

    out = tmp_path / "runs.json"
    run(
        steps_path=steps_path,
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=out,
        budget=999.0,
    )

    doc = json.loads(out.read_text(encoding="utf-8"))
    validate_runs(doc)  # raises ContractError on any schema violation


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_dry_run_prints_commands_without_running(tmp_path, monkeypatch, capsys):
    """--dry-run prints the exact argv for each step and never calls subprocess.run."""
    steps_path = _write_steps(tmp_path, n=2)
    pristine = _make_pristine(tmp_path)

    def _tripwire(*a, **kw):
        raise AssertionError("subprocess.run must not be called during --dry-run")

    monkeypatch.setattr("coldstart.run.subprocess.run", _tripwire)
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    # No API key needed for dry-run — the key-loading step is bypassed.

    out = tmp_path / "runs.json"
    run(
        steps_path=steps_path,
        pristine=pristine,
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=out,
        dry_run=True,
        budget=999.0,
    )

    stdout, _ = capsys.readouterr()
    assert "DRY-RUN" in stdout
    assert "bob" in stdout
    assert "--format" in stdout
    assert "--max-cost" in stdout


# ---------------------------------------------------------------------------
# New tests: executable resolution, dry-run workspace, bob_executable field
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_argv0_is_absolute_path(tmp_path, monkeypatch):
    """The command's argv[0] must be an absolute path, never the bare string 'bob'.

    On Windows, CreateProcess cannot resolve 'bob' to bob.CMD without a full
    path. This test pins the invariant so a future refactor cannot regress it.
    """
    captured_argv: list[list[str]] = []

    def _capture(*a, **kw):
        captured_argv.append(list(a[0]))
        return _make_fake_proc(_CLEAN_NDJSON)

    monkeypatch.setattr("coldstart.run.subprocess.run", _capture)
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    monkeypatch.setenv("BOB_API_KEY", "test")

    run(
        steps_path=_write_steps(tmp_path, n=1),
        pristine=_make_pristine(tmp_path),
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=tmp_path / "runs.json",
        budget=999.0,
    )

    assert captured_argv, "subprocess.run was never called"
    argv0 = captured_argv[0][0]
    assert Path(argv0).is_absolute(), (
        f"argv[0] must be an absolute path, got {argv0!r}. "
        "A bare 'bob' fails on Windows with WinError 2 because the installer "
        "provides bob.CMD, not bob.exe."
    )


@pytest.mark.contract
def test_missing_bob_executable_exits_before_any_step(tmp_path, monkeypatch):
    """When bob is not on PATH, run() must exit with a clear message before
    attempting any step. Fourteen identical WinError 2 failures is not helpful.
    """
    subprocess_called = []

    def _tripwire(*a, **kw):
        subprocess_called.append(True)
        raise AssertionError("subprocess.run was called despite bob being absent")

    monkeypatch.setattr("coldstart.run.subprocess.run", _tripwire)
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: (_ for _ in ()).throw(
        SystemExit("Bob Shell is not on PATH.")
    ))
    monkeypatch.setenv("BOB_API_KEY", "test")

    with pytest.raises(SystemExit, match="not on PATH"):
        run(
            steps_path=_write_steps(tmp_path, n=2),
            pristine=_make_pristine(tmp_path),
            workspaces=tmp_path / "ws",
            recordings=tmp_path / "rec",
            output_path=tmp_path / "runs.json",
            budget=999.0,
        )

    assert not subprocess_called, "no step should start when bob is absent"


def test_dry_run_creates_workspace_directories(tmp_path, monkeypatch):
    """--dry-run must prepare (copy) the workspaces even though it runs nothing.

    This is the whole point of a dry run: verify the workspace copy works before
    spending money. If the copy path is never exercised, the dry run is useless.
    """
    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("subprocess.run must not be called in dry-run")
        ),
    )
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)

    pristine = _make_pristine(tmp_path)
    ws_dir = tmp_path / "ws"

    run(
        steps_path=_write_steps(tmp_path, n=2),
        pristine=pristine,
        workspaces=ws_dir,
        recordings=tmp_path / "rec",
        output_path=tmp_path / "runs.json",
        dry_run=True,
        budget=999.0,
    )

    assert (ws_dir / "ws-01").is_dir(), "ws-01 must be created by dry-run"
    assert (ws_dir / "ws-02").is_dir(), "ws-02 must be created by dry-run"


def test_runs_json_carries_bob_executable(tmp_path, monkeypatch):
    """runs.json must include bob_executable with the resolved absolute path."""
    monkeypatch.setattr(
        "coldstart.run.subprocess.run",
        lambda *a, **kw: _make_fake_proc(_CLEAN_NDJSON),
    )
    monkeypatch.setattr("coldstart.run._resolve_bob", lambda: _FAKE_BOB_EXE)
    monkeypatch.setenv("BOB_API_KEY", "test")

    out = tmp_path / "runs.json"
    run(
        steps_path=_write_steps(tmp_path, n=1),
        pristine=_make_pristine(tmp_path),
        workspaces=tmp_path / "ws",
        recordings=tmp_path / "rec",
        output_path=out,
        budget=999.0,
    )

    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "bob_executable" in doc, "runs.json must carry bob_executable"
    assert doc["bob_executable"] == _FAKE_BOB_EXE


def test_runs_json_without_bob_executable_still_validates(tmp_path):
    """An older runs.json without bob_executable must still pass validate_runs.

    The field is optional — existing artifacts must not break.
    """
    from coldstart.schema import RUNS_SCHEMA, validate_runs

    doc = {
        "schema": RUNS_SCHEMA,
        "bob_version": "2.0.5",
        "recorded_at": "2026-09-26T16:30:00+00:00",
        "max_cost": 1.5,
        "runs": [],
    }
    validate_runs(doc)  # must not raise
