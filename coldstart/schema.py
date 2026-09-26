"""Contract validators for the three JSON artifacts.

WHY THIS MODULE EXISTS

Four modules in this project talk to each other exclusively through JSON files on
disk. Every one of them is written by an AI under time pressure. The failure mode
that costs a hackathon is not a crash -- it is ``run.py`` writing ``"cost"`` while
``render.py`` reads ``"session_costs"``, producing a runway of zeroes that looks
plausible right up until a judge asks about it.

So every artifact is validated the moment it is written and again the moment it is
read. A contract violation raises loudly, with the offending path named.

No third-party dependency. ``jsonschema`` would be one more thing to install and one
more thing to break; these contracts are small enough to check by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STEPS_SCHEMA = "coldstart.steps/1"
RUNS_SCHEMA = "coldstart.runs/1"
CHECKS_SCHEMA = "coldstart.checks/1"


class ContractError(ValueError):
    """An artifact does not match its declared contract.

    Always carries the JSON path of the offending field, because "invalid
    steps.json" at hour 19 is not an actionable error message.
    """


def _fail(where: str, msg: str) -> None:
    raise ContractError(f"{where}: {msg}")


def _require(obj: Any, key: str, kind: type | tuple[type, ...], where: str) -> Any:
    if not isinstance(obj, dict):
        _fail(where, f"expected an object, got {type(obj).__name__}")
    if key not in obj:
        _fail(where, f"missing required field {key!r}")
    val = obj[key]
    if not isinstance(val, kind):
        names = kind.__name__ if isinstance(kind, type) else "/".join(k.__name__ for k in kind)
        _fail(f"{where}.{key}", f"expected {names}, got {type(val).__name__}")
    return val


# --------------------------------------------------------------------------- steps

VALID_KIND = {"command", "prose"}
VALID_EXPECTED = {"green", "red", "unknown"}


def validate_steps(doc: Any, where: str = "steps.json") -> dict:
    """Validate ``steps.json``. Returns the document so calls can be chained."""
    if _require(doc, "schema", str, where) != STEPS_SCHEMA:
        _fail(f"{where}.schema", f"expected {STEPS_SCHEMA!r}, got {doc['schema']!r}")

    for key in ("source_repo", "source_commit", "doc_path", "doc_sha256"):
        _require(doc, key, str, where)

    steps = _require(doc, "steps", list, where)
    if not steps:
        _fail(f"{where}.steps", "no steps -- a runway with no tiles is not a demo")

    seen: set[int] = set()
    for i, step in enumerate(steps):
        at = f"{where}.steps[{i}]"

        sid = _require(step, "id", int, at)
        if sid in seen:
            _fail(f"{at}.id", f"duplicate id {sid}; ids must be unique")
        seen.add(sid)

        for key in ("title", "quote", "bob_prompt"):
            text = _require(step, key, str, at)
            if not text.strip():
                _fail(f"{at}.{key}", "must not be blank")

        kind = _require(step, "kind", str, at)
        if kind not in VALID_KIND:
            _fail(f"{at}.kind", f"expected one of {sorted(VALID_KIND)}, got {kind!r}")

        expected = _require(step, "expected", str, at)
        if expected not in VALID_EXPECTED:
            _fail(f"{at}.expected", f"expected one of {sorted(VALID_EXPECTED)}, got {expected!r}")

        lines = _require(step, "doc_lines", list, at)
        if len(lines) != 2 or not all(isinstance(n, int) for n in lines):
            _fail(f"{at}.doc_lines", "expected exactly two integers [start, end]")
        if lines[0] > lines[1]:
            _fail(f"{at}.doc_lines", f"start {lines[0]} is after end {lines[1]}")

        check = _require(step, "check", dict, at)
        # Caught by a test: the generic type error ("expected list, got str") did
        # not explain WHY a string is wrong. The reason matters -- see RULES.md
        # rule 3 -- so say it at the point of failure.
        if isinstance(check.get("cmd"), str):
            _fail(
                f"{at}.check.cmd",
                "got a shell string; must be an argv list. These commands come from a "
                "third party's documentation, so shell interpolation is an injection "
                "hole and Windows quoting would silently corrupt the check.",
            )
        cmd = _require(check, "cmd", list, f"{at}.check")
        if not cmd:
            _fail(f"{at}.check.cmd", "must not be empty")
        if not all(isinstance(part, str) for part in cmd):
            _fail(
                f"{at}.check.cmd", "every element must be a string (argv list, not a shell string)"
            )
        _require(check, "describes", str, f"{at}.check")

    expected_ids = list(range(1, len(steps) + 1))
    if sorted(seen) != expected_ids:
        _fail(f"{where}.steps", f"ids must be contiguous 1..{len(steps)}, got {sorted(seen)}")

    return doc


# ---------------------------------------------------------------------------- runs


def validate_runs(doc: Any, where: str = "runs.json") -> dict:
    """Validate ``runs.json``.

    Note what is NOT enforced here: ``bob_status``. It is recorded verbatim and is
    always the literal ``"success"`` -- Bob's own bundle hardcodes it in both result
    emitters, and a capped run that wrote nothing still reports it with exit code 0.
    Failure lives in ``error_frames`` and ``capped``. See docs/ARCHITECTURE.md.

    ``bob_executable`` is optional -- older artifacts written before the Windows
    fix do not carry it, and they must still validate cleanly.
    """
    if _require(doc, "schema", str, where) != RUNS_SCHEMA:
        _fail(f"{where}.schema", f"expected {RUNS_SCHEMA!r}, got {doc['schema']!r}")

    _require(doc, "bob_version", str, where)
    _require(doc, "recorded_at", str, where)
    _require(doc, "max_cost", (int, float), where)

    # Optional field added in the Windows-executable fix.  When present it must
    # be a string (an absolute path); when absent the artifact still validates.
    if "bob_executable" in doc:
        if not isinstance(doc["bob_executable"], str):
            _fail(
                f"{where}.bob_executable",
                f"expected str, got {type(doc['bob_executable']).__name__}",
            )

    runs = _require(doc, "runs", list, where)
    for i, run in enumerate(runs):
        at = f"{where}.runs[{i}]"

        _require(run, "step_id", int, at)
        _require(run, "task_id", str, at)
        _require(run, "ndjson", str, at)
        _require(run, "bob_status", str, at)
        _require(run, "bob_claim", str, at)

        cost = _require(run, "session_costs", (int, float), at)
        if cost < 0:
            _fail(f"{at}.session_costs", f"negative cost {cost}")

        duration = _require(run, "duration_ms", int, at)
        if duration < 0:
            _fail(f"{at}.duration_ms", f"negative duration {duration}")

        _require(run, "tool_calls", int, at)
        _require(run, "capped", bool, at)

        frames = _require(run, "error_frames", list, at)
        for j, frame in enumerate(frames):
            _require(frame, "message", str, f"{at}.error_frames[{j}]")

        # The one cross-field invariant worth enforcing: `capped` must be backed by
        # an actual error frame. If this ever fires, run.py invented a verdict.
        if run["capped"] and not frames:
            _fail(f"{at}.capped", "marked capped but carries no error_frames to prove it")

        # Optional: tool_errors was added when the real recording revealed
        # {"type":"tool_error",...} events. Older artifacts omit the field and
        # must still validate.
        if "tool_errors" in run:
            if not isinstance(run["tool_errors"], list):
                _fail(
                    f"{at}.tool_errors",
                    f"expected list, got {type(run['tool_errors']).__name__}",
                )
            for j, te in enumerate(run["tool_errors"]):
                _require(te, "message", str, f"{at}.tool_errors[{j}]")

        # Optional: max_cost_applied was added alongside tool_errors. Older
        # artifacts omit the field and must still validate.
        if "max_cost_applied" in run:
            if not isinstance(run["max_cost_applied"], (int, float)):
                _fail(
                    f"{at}.max_cost_applied",
                    f"expected int/float, got {type(run['max_cost_applied']).__name__}",
                )

    return doc


# -------------------------------------------------------------------------- checks

VALID_VERDICT = {"pass", "fail"}


def validate_checks(doc: Any, where: str = "checks.json") -> dict:
    """Validate ``checks.json``.

    The verdict is a mechanical function of the exit code, so this validator
    enforces exactly that. If a clever heuristic ever creeps into check.py, this
    test fails -- which is the point. See RULES.md rule 4.
    """
    if _require(doc, "schema", str, where) != CHECKS_SCHEMA:
        _fail(f"{where}.schema", f"expected {CHECKS_SCHEMA!r}, got {doc['schema']!r}")

    checks = _require(doc, "checks", list, where)
    for i, check in enumerate(checks):
        at = f"{where}.checks[{i}]"

        _require(check, "step_id", int, at)
        _require(check, "stdout_tail", str, at)
        _require(check, "stderr_tail", str, at)
        _require(check, "duration_ms", int, at)

        if isinstance(check.get("cmd"), str):
            _fail(f"{at}.cmd", "got a shell string; must be an argv list")
        cmd = _require(check, "cmd", list, at)
        if not all(isinstance(part, str) for part in cmd):
            _fail(f"{at}.cmd", "every element must be a string (argv list)")

        code = _require(check, "exit_code", int, at)
        verdict = _require(check, "verdict", str, at)
        if verdict not in VALID_VERDICT:
            _fail(f"{at}.verdict", f"expected one of {sorted(VALID_VERDICT)}, got {verdict!r}")

        implied = "pass" if code == 0 else "fail"
        if verdict != implied:
            _fail(
                f"{at}.verdict",
                f"exit_code {code} implies {implied!r} but verdict says {verdict!r}. "
                "The check never interprets -- 0 is pass, anything else is fail.",
            )

    return doc


# ------------------------------------------------------------------------ file I/O

_VALIDATORS = {
    STEPS_SCHEMA: validate_steps,
    RUNS_SCHEMA: validate_runs,
    CHECKS_SCHEMA: validate_checks,
}


def load_validated(path: str | Path) -> dict:
    """Read a JSON artifact and validate it against its own declared schema."""
    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ContractError(f"{p}: artifact does not exist yet") from None
    except json.JSONDecodeError as exc:
        raise ContractError(f"{p}: not valid JSON -- {exc}") from None

    if not isinstance(doc, dict) or "schema" not in doc:
        raise ContractError(f"{p}: artifact has no 'schema' field, so it cannot be validated")

    validator = _VALIDATORS.get(doc["schema"])
    if validator is None:
        raise ContractError(f"{p}: unknown schema {doc['schema']!r}")

    return validator(doc, where=str(p))


def dump_validated(doc: dict, path: str | Path) -> Path:
    """Validate an artifact, then write it.

    Validating BEFORE writing means a broken artifact never reaches disk, so a later
    module cannot read it and produce a plausible-looking wrong answer.

    Written with sorted keys and a trailing newline so the files are diff-stable in
    git -- a recording that changes only by key order is noise in a review.
    """
    validator = _VALIDATORS.get(doc.get("schema"))
    if validator is None:
        raise ContractError(f"cannot write {path}: unknown schema {doc.get('schema')!r}")
    validator(doc, where=str(path))

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p
