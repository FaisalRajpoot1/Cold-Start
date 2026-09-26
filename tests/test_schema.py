"""Contract tests.

These are the tests that catch two AI-written modules quietly disagreeing about a
field name -- the failure that produces a plausible, wrong runway rather than a
crash. Each one asserts something that MUST hold for the demo to be honest.
"""

from __future__ import annotations

import copy

import pytest

from coldstart.schema import (
    CHECKS_SCHEMA,
    RUNS_SCHEMA,
    STEPS_SCHEMA,
    ContractError,
    dump_validated,
    load_validated,
    validate_checks,
    validate_runs,
    validate_steps,
)


def _steps() -> dict:
    return {
        "schema": STEPS_SCHEMA,
        "source_repo": "sqlfluff/sqlfluff",
        "source_commit": "0" * 40,
        "doc_path": "CONTRIBUTING.md",
        "doc_sha256": "a" * 64,
        "steps": [
            {
                "id": 1,
                "title": "Clone the repository",
                "doc_lines": [42, 47],
                "quote": "git clone https://github.com/sqlfluff/sqlfluff.git",
                "kind": "command",
                "bob_prompt": "Clone the repository as the document instructs.",
                "check": {
                    "cmd": ["python", "-c", "import sys; sys.exit(0)"],
                    "describes": "the clone exists",
                },
                "expected": "green",
            },
            {
                "id": 2,
                "title": "Run the grammar tests",
                "doc_lines": [120, 122],
                "quote": "tox -e py310 -- test/core/parser/grammar_test.py",
                "kind": "command",
                "bob_prompt": "Run the grammar test file named in the document.",
                "check": {
                    "cmd": ["python", "-c", "import sys; sys.exit(1)"],
                    "describes": "the test file exists",
                },
                "expected": "red",
            },
        ],
    }


def _runs() -> dict:
    return {
        "schema": RUNS_SCHEMA,
        "bob_version": "2.0.5",
        "recorded_at": "2026-09-26T16:30:00Z",
        "max_cost": 1.5,
        "runs": [
            {
                "step_id": 1,
                "task_id": "13c2f66791577ad505fd2a464f027d0d",
                "ndjson": "recordings/step-01.ndjson",
                "session_costs": 0.4831,
                "duration_ms": 41233,
                "tool_calls": 7,
                "bob_status": "success",
                "error_frames": [],
                "capped": False,
                "bob_claim": "completed",
                "bob_final_message": "Done.",
            }
        ],
    }


def _checks() -> dict:
    return {
        "schema": CHECKS_SCHEMA,
        "checks": [
            {
                "step_id": 1,
                "cmd": ["python", "-c", "import sys; sys.exit(0)"],
                "exit_code": 0,
                "stdout_tail": "",
                "stderr_tail": "",
                "duration_ms": 120,
                "verdict": "pass",
            }
        ],
    }


# --------------------------------------------------------------- happy paths


def test_valid_artifacts_pass():
    assert validate_steps(_steps())
    assert validate_runs(_runs())
    assert validate_checks(_checks())


# ------------------------------------------------------- the invariants that matter


@pytest.mark.contract
def test_verdict_must_follow_the_exit_code():
    """RULES.md rule 4: the check never interprets. 0 is pass, anything else is fail.

    If a heuristic ever creeps into check.py -- "exit 2 probably means it worked" --
    this fires. That heuristic would turn our one deterministic fact into another
    opinion and collapse the whole pitch.
    """
    doc = _checks()
    doc["checks"][0]["exit_code"] = 1  # now contradicts verdict "pass"
    with pytest.raises(ContractError, match="implies 'fail'"):
        validate_checks(doc)


@pytest.mark.contract
def test_capped_must_be_backed_by_an_error_frame():
    """`capped` is a claim about reality and must carry its evidence.

    Bob's result event says "success" even on a capped run, so `capped` can only
    come from an error frame. A capped=True with no frame means run.py invented it.
    """
    doc = _runs()
    doc["runs"][0]["capped"] = True
    with pytest.raises(ContractError, match="no error_frames"):
        validate_runs(doc)

    doc["runs"][0]["error_frames"] = [
        {"message": "The task reached the cost limit of 1.500 (spent: 1.512)."}
    ]
    assert validate_runs(doc)


@pytest.mark.contract
def test_check_cmd_is_an_argv_list_never_a_shell_string():
    """RULES.md rule 3.

    These commands are derived from a THIRD PARTY's documentation. A shell string
    would be a command-injection hole, and on Windows the quoting would silently
    corrupt a check -- painting a false red, which is a false accusation about
    someone else's project, on camera.
    """
    doc = _steps()
    doc["steps"][0]["check"]["cmd"] = 'python -c "import sys; sys.exit(0)"'
    with pytest.raises(ContractError, match="argv list"):
        validate_steps(doc)


def test_step_ids_must_be_contiguous():
    doc = _steps()
    doc["steps"][1]["id"] = 7
    with pytest.raises(ContractError, match="contiguous"):
        validate_steps(doc)


def test_duplicate_step_ids_rejected():
    doc = _steps()
    doc["steps"][1]["id"] = 1
    with pytest.raises(ContractError, match="duplicate id"):
        validate_steps(doc)


def test_blank_quote_rejected():
    doc = _steps()
    doc["steps"][0]["quote"] = "   "
    with pytest.raises(ContractError, match="must not be blank"):
        validate_steps(doc)


def test_expected_is_constrained():
    doc = _steps()
    doc["steps"][0]["expected"] = "probably fine"
    with pytest.raises(ContractError, match="expected one of"):
        validate_steps(doc)


def test_negative_cost_rejected():
    doc = _runs()
    doc["runs"][0]["session_costs"] = -1.0
    with pytest.raises(ContractError, match="negative cost"):
        validate_runs(doc)


def test_missing_field_names_the_path():
    """An error message must name the offending path.

    "invalid steps.json" at hour 19 is not actionable.
    """
    doc = _steps()
    del doc["steps"][1]["bob_prompt"]
    with pytest.raises(
        ContractError, match=r"steps\.json\.steps\[1\]: missing required field 'bob_prompt'"
    ):
        validate_steps(doc)


# ----------------------------------------------------------------- file round-trip


def test_round_trip(tmp_path):
    for doc, name in ((_steps(), "steps.json"), (_runs(), "runs.json"), (_checks(), "checks.json")):
        path = dump_validated(doc, tmp_path / name)
        assert load_validated(path) == doc


def test_broken_artifact_never_reaches_disk(tmp_path):
    """dump_validated validates BEFORE writing.

    So a later module cannot read a corrupt artifact and produce a plausible
    wrong answer from it.
    """
    doc = _steps()
    doc["steps"][0]["check"]["cmd"] = []
    target = tmp_path / "steps.json"
    with pytest.raises(ContractError):
        dump_validated(doc, target)
    assert not target.exists(), "a rejected artifact must not be left on disk"


def test_unknown_schema_is_refused(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"schema": "something.else/9"}', encoding="utf-8")
    with pytest.raises(ContractError, match="unknown schema"):
        load_validated(p)


def test_output_is_byte_stable(tmp_path):
    """RULES.md rule 2: same input in, byte-identical file out.

    Key order must not leak into the bytes, or every re-run shows a spurious diff
    and a judge cannot reproduce our artifacts.
    """
    a = dump_validated(_steps(), tmp_path / "a.json").read_bytes()
    shuffled = copy.deepcopy(_steps())
    shuffled["steps"][0] = dict(reversed(list(shuffled["steps"][0].items())))
    b = dump_validated(shuffled, tmp_path / "b.json").read_bytes()
    assert a == b
