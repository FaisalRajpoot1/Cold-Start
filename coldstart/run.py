"""run.py — give each step to a fresh Bob session and record what happens.

THIS IS THE ONLY MODULE THAT TOUCHES THE NETWORK OR SPENDS MONEY.

For each step in steps.json, run.py:
  1. Prepares a clean workspace by copying target/_pristine (never re-cloning).
  2. Runs `bob run --format stream-json ...` as a subprocess with the step's
     bob_prompt.
  3. Writes the raw stdout verbatim to recordings/step-NN.ndjson BEFORE parsing.
  4. Parses the NDJSON to extract cost, durations, error frames, etc.
  5. Writes a validated runs.json.

Steps run in parallel (default 4 workers) but the budget guard is exact: once
accumulated spend reaches --budget, no new step starts.

CRITICAL: result.status is ALWAYS the literal "success" — Bob's own bundle
hardcodes it in both result emitters, and a capped run still reports it with
process exit code 0. We therefore NEVER branch on result.status or on the
subprocess return code. Failure is read from error_frames only. See
docs/ARCHITECTURE.md §runs.json for the citation.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from coldstart.schema import RUNS_SCHEMA, dump_validated, load_validated

# Default Bob subprocess timeout per step (seconds).
# A legitimate run should be well under this; it exists to prevent a hung
# process from blocking the thread forever.
_BOB_TIMEOUT = 900

# Wording that Bob emits in the error frame when a cost cap is hit. Checked
# case-insensitively because Bob's phrasing may change between versions.
_COST_LIMIT_RE = re.compile(r"reached the cost limit", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Executable resolution
# ---------------------------------------------------------------------------


def _resolve_bob() -> str:
    """Return the absolute path to the bob executable.

    On Windows the installer creates a shim named bob.CMD, not bob.exe.
    CreateProcess cannot resolve a bare "bob" to a .CMD file, so we must
    pass the full path. shutil.which() handles the PATHEXT lookup that finds
    bob.CMD on Windows (and bob / bob.sh on POSIX).

    We exit immediately when bob is not found rather than starting fourteen
    steps that will all fail with WinError 2. That is always a
    user-environment problem, not a data problem.
    """
    exe = shutil.which("bob")
    if exe is None:
        raise SystemExit(
            "Bob Shell is not on PATH.\n"
            "Install it with:\n"
            "  powershell -c \"irm -Uri https://bob.ibm.com/download/bobshell.ps1 | iex\""
        )
    return exe


# ---------------------------------------------------------------------------
# API-key helpers
# ---------------------------------------------------------------------------


def _load_api_key() -> str:
    """Return the BOB_API_KEY, reading bob.key as a fallback.

    NEVER log, print, or embed this value in any artifact. The caller puts it
    in the child environment only — it must not appear in runs.json, in an
    error message, or in the printed summary.
    """
    key = os.environ.get("BOB_API_KEY", "").strip()
    if key:
        return key

    key_file = Path("bob.key")
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key

    raise SystemExit(
        "BOB_API_KEY is not set and bob.key was not found.\n"
        "Create an Inference-type key at https://www.ibm.com/products/ibm-bob "
        "and either export BOB_API_KEY=<key> or write it to bob.key."
    )


# ---------------------------------------------------------------------------
# Workspace preparation
# ---------------------------------------------------------------------------


def _prepare_workspace(pristine: Path, workspace: Path) -> None:
    """Delete any existing workspace, then copy pristine into it.

    The .git directory is excluded — it is the bulk of the bytes and Bob does
    not need version history. Excluding it also prevents Bob from accidentally
    committing to the wrong repository.

    We copy, never re-clone, because hammering a public repository's git server
    fourteen times in parallel is both slow and antisocial.
    """
    if workspace.exists():
        shutil.rmtree(workspace)

    def _ignore_git(src: str, names: list[str]) -> list[str]:
        return [n for n in names if n == ".git"]

    shutil.copytree(str(pristine), str(workspace), ignore=_ignore_git)


# ---------------------------------------------------------------------------
# NDJSON parser
# ---------------------------------------------------------------------------


def _parse_ndjson(raw: bytes) -> dict:
    """Parse the raw stdout from a `bob run --format stream-json` invocation.

    Returns a dict with:
        task_id           str   — from result.stats
        duration_ms       int   — from result.stats (already milliseconds, no conversion)
        session_costs     float — from result.stats
        tool_calls        int   — from result.stats
        max_cost_applied  float — from result.stats (the cap that was in force)
        bob_status        str   — verbatim from the result event top-level (always "success")
        error_frames      list  — every {"type":"error",...} object in order
        tool_errors       list  — every {"type":"tool_error",...} object in order
        capped            bool  — True if any error message matches the cost-limit wording
        bob_final_message str   — content of the LAST assistant message event

    WHY stats-nested: verified against a real recording committed as
    tests/golden/real_run_turn_limit.ndjson. The result event shape is:
        {"type":"result","status":"success","stats":{"task_id":...,"session_costs":...}}
    The old camelCase top-level spellings (taskId, durationMs, sessionCost, toolCalls)
    never matched the real event, so every run was silently reported as 0 cost.
    """
    task_id = ""
    duration_ms = 0
    session_costs = 0.0
    tool_calls = 0
    max_cost_applied = 0.0
    bob_status = "unknown"
    error_frames: list[dict] = []
    tool_errors: list[dict] = []
    message_chunks: list[str] = []

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # A partial trailing line or a log line that is not JSON. Tolerate
            # it: the recording is the evidence, not the parse.
            continue

        if not isinstance(obj, dict):
            continue

        kind = obj.get("type")

        if kind == "result":
            # All cost/timing fields live under "stats" — verified in the real
            # recording at tests/golden/real_run_turn_limit.ndjson. The old
            # top-level camelCase fallbacks (taskId, durationMs, sessionCost)
            # never matched and silently zeroed everything out.
            stats = obj.get("stats") or {}
            task_id = str(stats.get("task_id") or "")
            # duration_ms is already in milliseconds — do NOT multiply.
            duration_ms = int(stats.get("duration_ms") or 0)
            session_costs = float(stats.get("session_costs") or 0.0)
            tool_calls = int(stats.get("tool_calls") or 0)
            max_cost_applied = float(stats.get("max_cost") or 0.0)
            # status is genuinely top-level (always "success" — see ARCHITECTURE.md)
            bob_status = str(obj.get("status") or "success")

        elif kind == "error":
            msg = obj.get("message") or obj.get("error") or str(obj)
            error_frames.append({"message": str(msg)})

        elif kind == "tool_result" and obj.get("status") == "error":
            # tool_result events with status="error" are normal mid-task tool
            # failures (e.g. a command that returned exit code 1). The error
            # detail is in obj["error"]["message"]. These do NOT affect bob_claim;
            # only a top-level "error" frame signals task failure.
            # The real recording (tests/golden/real_run_turn_limit.ndjson) carries
            # two of these from failed tox/python invocations.
            err_obj = obj.get("error") or {}
            if isinstance(err_obj, dict):
                msg = err_obj.get("message") or str(err_obj)
            else:
                msg = str(err_obj)
            tool_errors.append({"message": str(msg)})

        elif kind == "message" and obj.get("role") == "assistant":
            # ACCUMULATE, do not replace.
            #
            # Bob streams one message event PER TOKEN: "Let", " me find", " the".
            # Taking the last event therefore yields the last token, not the last
            # message. A real recording produced bob_final_message =
            # "UFF_GITHUB_TOKEN`." -- the tail of a word -- which is useless as
            # evidence of what Bob claimed. Joining the chunks gives the answer.
            content = obj.get("content") or ""
            if isinstance(content, list):
                # content can be a list of content blocks; join text blocks.
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                content = "".join(parts)
            message_chunks.append(str(content))

    # Keep only the tail: the final answer, not the whole running commentary.
    bob_final_message = "".join(message_chunks).strip()[-600:]

    capped = any(_COST_LIMIT_RE.search(f["message"]) for f in error_frames)

    return {
        "task_id": task_id,
        "duration_ms": duration_ms,
        "session_costs": session_costs,
        "tool_calls": tool_calls,
        "max_cost_applied": max_cost_applied,
        "bob_status": bob_status,
        "error_frames": error_frames,
        "tool_errors": tool_errors,
        "capped": capped,
        "bob_final_message": bob_final_message,
    }


# ---------------------------------------------------------------------------
# Single-step runner
# ---------------------------------------------------------------------------


def _run_one_step(
    *,
    step: dict,
    pristine: Path,
    workspaces: Path,
    recordings: Path,
    max_cost: float,
    max_turns: int,
    bob_exe: str,
    bob_env: dict[str, str],
    timeout: int = _BOB_TIMEOUT,
    dry_run: bool = False,
) -> dict:
    """Prepare workspace, run Bob, record output, parse result.

    Returns a runs.json run-record (without step_id — caller adds it).
    On any failure the step is recorded with session_costs 0.0 and an
    error_frame so the error does not cascade to other steps.

    ``bob_exe`` must be an absolute path returned by _resolve_bob(). On
    Windows the bare string "bob" cannot be resolved by CreateProcess because
    the installer provides a bob.CMD shim, not an .exe. Passing the absolute
    path avoids WinError 2.
    """
    sid: int = step["id"]
    ws = workspaces / f"ws-{sid:02d}"
    ndjson_path = recordings / f"step-{sid:02d}.ndjson"
    ndjson_rel = str(ndjson_path)  # relative path stored in runs.json

    # Build the argv list. Every flag here has been verified to exist in Bob.
    # shell=False is explicit and non-negotiable (see AGENTS.md rule 2).
    # argv[0] is the resolved absolute path, never the bare string "bob".
    cmd = [
        bob_exe,
        "run",
        "--format", "stream-json",
        "--max-cost", str(max_cost),
        "--max-turns", str(max_turns),
        "--trust",
        "--accept-license",
        "--workspace", str(ws.resolve()),
        step["bob_prompt"],
    ]  # fmt: skip

    # --- 1. Prepare workspace (done for BOTH real runs and dry-run) ---
    # dry-run is meant to test that the workspace preparation works before
    # spending money. Skipping it here would leave the copy path untested.
    try:
        _prepare_workspace(pristine, ws)
    except OSError as exc:
        return {
            "task_id": "",
            "ndjson": ndjson_rel,
            "session_costs": 0.0,
            "duration_ms": 0,
            "tool_calls": 0,
            "bob_status": "unknown",
            "error_frames": [{"message": f"workspace preparation failed: {exc}"}],
            "capped": False,
            "bob_claim": "failed",
            "bob_final_message": "",
        }

    # For dry-run: workspace is prepared above so the copy path is exercised,
    # then we stop before touching the network or spending anything.
    if dry_run:
        print(f"[step {sid:02d}] DRY-RUN: {' '.join(cmd)}")
        return {
            "task_id": "",
            "ndjson": ndjson_rel,
            "session_costs": 0.0,
            "duration_ms": 0,
            "tool_calls": 0,
            "bob_status": "dry-run",
            "error_frames": [],
            "capped": False,
            "bob_claim": "skipped",
            "bob_final_message": "",
        }

    # --- 2. Run Bob ---
    raw_stdout = b""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 — argv list, shell=False, verified flags only
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            cwd=str(ws),
            env=bob_env,
            shell=False,
        )
        raw_stdout = proc.stdout
    except subprocess.TimeoutExpired as exc:
        raw_stdout = exc.output or b""
        duration_ms = int((time.monotonic() - t0) * 1000)
        # Write whatever we captured before the timeout.
        recordings.mkdir(parents=True, exist_ok=True)
        ndjson_path.write_bytes(raw_stdout)
        return {
            "task_id": "",
            "ndjson": ndjson_rel,
            "session_costs": 0.0,
            "duration_ms": duration_ms,
            "tool_calls": 0,
            "bob_status": "unknown",
            "error_frames": [{"message": f"bob run timed out after {timeout}s"}],
            "capped": False,
            "bob_claim": "failed",
            "bob_final_message": "",
        }
    except (OSError, subprocess.SubprocessError) as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return {
            "task_id": "",
            "ndjson": ndjson_rel,
            "session_costs": 0.0,
            "duration_ms": duration_ms,
            "tool_calls": 0,
            "bob_status": "unknown",
            "error_frames": [{"message": f"failed to launch bob: {exc}"}],
            "capped": False,
            "bob_claim": "failed",
            "bob_final_message": "",
        }

    duration_ms = int((time.monotonic() - t0) * 1000)

    # --- 3. Write the raw recording BEFORE parsing ---
    # If the parse below throws, the evidence is already safely on disk.
    recordings.mkdir(parents=True, exist_ok=True)
    ndjson_path.write_bytes(raw_stdout)

    # --- 4. Parse ---
    try:
        parsed = _parse_ndjson(raw_stdout)
    except Exception as exc:
        # Parsing must never crash the pipeline. Record the error and move on.
        return {
            "task_id": "",
            "ndjson": ndjson_rel,
            "session_costs": 0.0,
            "duration_ms": duration_ms,
            "tool_calls": 0,
            "bob_status": "unknown",
            "error_frames": [{"message": f"NDJSON parse failed: {exc}"}],
            "capped": False,
            "bob_claim": "failed",
            "bob_final_message": "",
        }

    # bob_claim: "completed" iff no error frames — it is Bob's claim, not a verdict.
    bob_claim = "failed" if parsed["error_frames"] else "completed"

    return {
        "task_id": parsed["task_id"],
        "ndjson": ndjson_rel,
        "session_costs": parsed["session_costs"],
        "duration_ms": parsed["duration_ms"] or duration_ms,
        "tool_calls": parsed["tool_calls"],
        "max_cost_applied": parsed["max_cost_applied"],
        "bob_status": parsed["bob_status"],
        "error_frames": parsed["error_frames"],
        "tool_errors": parsed["tool_errors"],
        "capped": parsed["capped"],
        "bob_claim": bob_claim,
        "bob_final_message": parsed["bob_final_message"],
    }


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def run(
    *,
    steps_path: str | Path = "steps.json",
    pristine: str | Path = "target/_pristine",
    workspaces: str | Path = "target",
    recordings: str | Path = "recordings",
    output_path: str | Path = "runs.json",
    max_cost: float = 1.5,
    max_turns: int = 25,
    concurrency: int = 4,
    budget: float = 15.0,
    timeout: int = _BOB_TIMEOUT,
    dry_run: bool = False,
) -> Path:
    """Run all steps and write runs.json.

    This is the ONLY function in the project that spends money. Every other
    guard in this file exists to limit how much it can spend.
    """
    steps_doc = load_validated(steps_path)
    steps = steps_doc["steps"]

    pristine_p = Path(pristine)
    workspaces_p = Path(workspaces)
    recordings_p = Path(recordings)
    recordings_p.mkdir(parents=True, exist_ok=True)

    # Resolve the bob executable ONCE before starting any steps. On Windows the
    # installer provides bob.CMD; CreateProcess cannot find it from a bare "bob".
    # Failing here is better than all fourteen steps failing with WinError 2.
    bob_exe = _resolve_bob()

    if not dry_run:
        api_key = _load_api_key()
        bob_env = {**os.environ, "BOB_API_KEY": api_key}
    else:
        bob_env = dict(os.environ)

    # Budget guard state — shared across threads, protected by a lock.
    budget_lock = threading.Lock()
    spent_total = 0.0
    budget_exhausted = False

    # Collect results in step-id order.
    run_records: list[dict] = [{}] * len(steps)

    def _run_step(idx: int, step: dict) -> None:
        nonlocal spent_total, budget_exhausted

        sid = step["id"]

        # Check budget BEFORE starting. This is the gate that protects real money.
        with budget_lock:
            if budget_exhausted:
                run_records[idx] = {
                    "step_id": sid,
                    "task_id": "",
                    "ndjson": str(recordings_p / f"step-{sid:02d}.ndjson"),
                    "session_costs": 0.0,
                    "duration_ms": 0,
                    "tool_calls": 0,
                    "bob_status": "skipped",
                    "error_frames": [{"message": "budget exhausted; step skipped"}],
                    "capped": False,
                    "bob_claim": "failed",
                    "bob_final_message": "",
                }
                return

        record = _run_one_step(
            step=step,
            pristine=pristine_p,
            workspaces=workspaces_p,
            recordings=recordings_p,
            max_cost=max_cost,
            max_turns=max_turns,
            bob_exe=bob_exe,
            bob_env=bob_env,
            timeout=timeout,
            dry_run=dry_run,
        )
        record["step_id"] = sid

        # Accumulate cost and check budget AFTER the step finishes.
        with budget_lock:
            spent_total += record["session_costs"]
            if spent_total >= budget:
                budget_exhausted = True

        run_records[idx] = record

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_run_step, i, step): step for i, step in enumerate(steps)}
        for fut in concurrent.futures.as_completed(futures):
            # Re-raise any unexpected exception from the thread. _run_step itself
            # catches all expected failures; this only fires on programming errors.
            fut.result()

    # Count skipped steps and print the budget warning.
    skipped = sum(1 for r in run_records if r.get("bob_status") == "skipped")
    if skipped:
        print(
            f"BUDGET GUARD: stopped after ${spent_total:.4f} Bobcoins — "
            f"{skipped} step(s) skipped."
        )

    # Determine the Bob version from the first result event that has one, or
    # fall back to "unknown". We do NOT run `bob --version` because that costs
    # nothing but could behave differently across environments.
    bob_version = _extract_bob_version(recordings_p, steps)

    recorded_at = datetime.now(tz=timezone.utc).isoformat()

    out_doc = {
        "schema": RUNS_SCHEMA,
        "bob_version": bob_version,
        "bob_executable": bob_exe,
        "recorded_at": recorded_at,
        "max_cost": max_cost,
        "runs": run_records,
    }

    out_path = dump_validated(out_doc, output_path)

    # Print per-step summary.
    total_cost = sum(r.get("session_costs", 0.0) for r in run_records)
    error_count = sum(1 for r in run_records if r.get("error_frames"))
    _print_summary(run_records, total_cost, error_count)

    return out_path


def _extract_bob_version(recordings_p: Path, steps: list[dict]) -> str:
    """Try to read the Bob version from an already-written recording.

    Bob emits a {"type":"system","version":"..."} event (or similar) in some
    versions. If we cannot find one, "unknown" is correct and honest.
    """
    for step in steps:
        sid = step["id"]
        p = recordings_p / f"step-{sid:02d}.ndjson"
        if not p.exists():
            continue
        for raw_line in p.read_bytes().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                v = obj.get("bobVersion") or obj.get("bob_version") or obj.get("version")
                if v and isinstance(v, str):
                    return v
    return "unknown"


def _print_summary(run_records: list[dict], total_cost: float, error_count: int) -> None:
    """Print a per-step receipt and the totals line."""
    print()
    for r in run_records:
        sid = r.get("step_id", "?")
        claim = r.get("bob_claim", "?")
        cost = r.get("session_costs", 0.0)
        dur = r.get("duration_ms", 0)
        tools = r.get("tool_calls", 0)
        print(
            f"  step {sid:>2}  claim={claim:<10}  cost={cost:.4f}  "
            f"dur={dur}ms  tools={tools}"
        )
    total_usd = total_cost * 0.50
    print()
    print(f"total: {total_cost:.4f} Bobcoins  (${total_usd:.2f} USD)")
    m = len(run_records)
    print(f"{error_count} of {m} steps reported an error frame")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run each step in steps.json through a headless Bob session "
            "and write runs.json."
        )
    )
    parser.add_argument("--steps", default="steps.json", help="path to steps.json")
    parser.add_argument(
        "--pristine", default="target/_pristine", help="pristine repo clone to copy from"
    )
    parser.add_argument(
        "--workspaces", default="target", help="directory to create ws-NN copies in"
    )
    parser.add_argument(
        "--recordings", default="recordings", help="directory for step-NN.ndjson files"
    )
    parser.add_argument("--out", default="runs.json", help="where to write runs.json")
    parser.add_argument("--max-cost", type=float, default=1.5, help="per-step cost cap")
    parser.add_argument("--max-turns", type=int, default=12, help="per-step turn cap")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel workers")
    parser.add_argument(
        "--budget", type=float, default=15.0, help="total Bobcoin budget before stopping"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_BOB_TIMEOUT,
        help="subprocess timeout per step (seconds)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the exact bob command for each step without running anything",
    )
    args = parser.parse_args()

    run(
        steps_path=args.steps,
        pristine=args.pristine,
        workspaces=args.workspaces,
        recordings=args.recordings,
        output_path=args.out,
        max_cost=args.max_cost,
        max_turns=args.max_turns,
        concurrency=args.concurrency,
        budget=args.budget,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    _cli()
