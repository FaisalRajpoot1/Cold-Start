"""check.py — run the post-checks for every step and write checks.json.

WHY THIS MODULE EXISTS

run.py asks Bob to perform each step. Bob always reports "success" (see
docs/ARCHITECTURE.md §runs.json for the citation). So the only ground truth is
whether the step's advertised postcondition actually holds. That is what this
module measures.

A check is exactly: run the argv list from steps.json[n].check.cmd inside the
step's workspace, read the exit code. 0 → pass, anything else → fail. No model,
no heuristic, no interpretation. See AGENTS.md rule 3.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from coldstart.schema import CHECKS_SCHEMA, dump_validated, load_validated

# How long to wait for a single check command before declaring it a failure.
# Most checks are tiny Python one-liners; 30 s is generous. We do NOT want to
# wait forever for a mis-specified command.
_CHECK_TIMEOUT = 30

# Maximum bytes captured from stdout/stderr. We keep the TAIL so that if a
# command fills a buffer before failing, we still see the relevant error at the
# end, not the boilerplate at the start.
_TAIL_BYTES = 500


def _workspace(target_dir: Path, step_id: int) -> Path:
    """Return the workspace directory for a step.

    Format matches run.py: target/ws-01, target/ws-02, etc. Zero-padded to two
    digits so directory listings sort correctly for up to 99 steps.
    """
    return target_dir / f"ws-{step_id:02d}"


def _tail(raw: bytes) -> str:
    """Return the last _TAIL_BYTES characters of subprocess output as a string.

    We decode with errors="replace" because a failed build step can emit
    arbitrary bytes. A replacement character in the tail is better than a
    UnicodeDecodeError hiding the real failure message.
    """
    text = raw.decode("utf-8", errors="replace")
    return text[-_TAIL_BYTES:]


def run_check(cmd: list[str], cwd: Path) -> dict:
    """Run one check command and return a partial check record (no step_id).

    DECIDE FIRST, RUN SECOND.

    If the workspace is not a directory — whether it is absent or is a file —
    return a fail record immediately, without touching subprocess. The walk-up
    strategy used previously was wrong: walking up to a real directory could land
    in a directory that satisfies the check (e.g. Cold Start's own repo root
    contains pyproject.toml), producing a false green for a step whose workspace
    was never even created. See tests/test_check_isolation.py for measured proof.

    exit_code -2 marks "workspace missing" so it cannot be confused with a
    genuine process failure (which always has a non-negative exit code).
    """
    if not cwd.is_dir():
        return {
            "cmd": cmd,
            "exit_code": -2,
            "stdout_tail": "",
            "stderr_tail": f"workspace does not exist or is not a directory: {cwd}",
            "duration_ms": 0,
            "verdict": "fail",
        }

    t0 = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 — cmd is a validated argv list, not a shell string
            cmd,
            capture_output=True,
            timeout=_CHECK_TIMEOUT,
            cwd=cwd,
            shell=False,  # explicit: never a shell string (see AGENTS.md rule 2)
        )
        exit_code = proc.returncode
        stdout_tail = _tail(proc.stdout)
        stderr_tail = _tail(proc.stderr)
    except subprocess.TimeoutExpired:
        # Treat timeout as a failure: the step did not complete cleanly.
        exit_code = 124  # same convention as the Unix `timeout` command
        stdout_tail = ""
        stderr_tail = f"check timed out after {_CHECK_TIMEOUT}s"
    except FileNotFoundError:
        # The executable named in cmd[0] does not exist in this environment.
        # That is a legitimate "the step cannot work here" result.
        exit_code = 127  # same convention as POSIX shell: command not found
        stdout_tail = ""
        stderr_tail = f"command not found: {cmd[0]!r}"
    except (OSError, subprocess.SubprocessError) as exc:
        # Catch any other OS-level or subprocess failure so a single bad check
        # cannot abort the entire remaining batch.
        exit_code = 1
        stdout_tail = ""
        stderr_tail = f"check failed to launch: {exc}"

    duration_ms = int((time.monotonic() - t0) * 1000)
    verdict = "pass" if exit_code == 0 else "fail"

    return {
        "cmd": cmd,
        "exit_code": exit_code,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "duration_ms": duration_ms,
        "verdict": verdict,
    }


def check(
    steps_path: str | Path = "steps.json",
    target_dir: str | Path = "target",
    output_path: str | Path = "checks.json",
) -> Path:
    """Run all step checks and write checks.json.

    Reads  : steps_path  (validated steps.json)
    Runs   : check.cmd for each step, in its workspace under target_dir
    Writes : output_path (validated checks.json)
    """
    steps_doc = load_validated(steps_path)
    target = Path(target_dir)

    check_records: list[dict] = []
    for step in steps_doc["steps"]:
        sid: int = step["id"]
        cmd: list[str] = step["check"]["cmd"]
        cwd = _workspace(target, sid)

        record = run_check(cmd, cwd)
        record["step_id"] = sid
        check_records.append(record)

    out_doc = {
        "schema": CHECKS_SCHEMA,
        "checks": check_records,
    }

    return dump_validated(out_doc, output_path)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Run postcondition checks for each step and write checks.json."
    )
    parser.add_argument("--steps", default="steps.json", help="path to steps.json")
    parser.add_argument("--target", default="target", help="directory containing ws-NN workspaces")
    parser.add_argument("--output", default="checks.json", help="where to write checks.json")
    args = parser.parse_args()
    out = check(args.steps, args.target, args.output)
    print(f"wrote {out}")


if __name__ == "__main__":
    _cli()
