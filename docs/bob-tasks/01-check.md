# Bob Task 01 — `coldstart/check.py`

> Paste the block below into IBM Bob (Agent mode) with this repository open.
> Capture the task-session summary screenshot when it finishes — it is a required
> hackathon deliverable.

**Why this module first:** it is the one that makes the whole pitch work, it needs no
Bobcoins to test, and it can be verified against a real repository immediately. If `check.py`
is right, the product is real even if everything else slips.

---

## The prompt

```
Read AGENTS.md and docs/ARCHITECTURE.md first, then implement coldstart/check.py.

WHAT IT DOES

check.py decides, deterministically, whether each step of an onboarding document
actually worked. It is the independent second opinion that overrules the agent, so
it must contain NO model, NO network call and NO heuristic.

A check is: run an argv list in a workspace directory, read the exit code.
0 means pass. Anything else means fail. There is no third option.

INPUTS
  steps.json           validated via coldstart.schema.load_validated()
  a workspace root     one directory per step, named ws-01, ws-02, ... ws-NN

OUTPUT
  checks.json          written via coldstart.schema.dump_validated()

The exact shape of checks.json is in docs/ARCHITECTURE.md. Match it precisely:
step_id, cmd, exit_code, stdout_tail, stderr_tail, duration_ms, verdict.

REQUIREMENTS

1. Public function:
       run_checks(steps_path, workspace_root, out_path, timeout=120) -> dict

2. For each step in steps.json, run step["check"]["cmd"] with:
       cwd     = <workspace_root>/ws-NN   (NN is the step id, zero padded to 2)
       shell   = False, always
       timeout = the timeout argument
       capture stdout and stderr as text, errors="replace"

3. stdout_tail and stderr_tail are the LAST 500 characters, not the first.
   The useful part of a traceback is at the end.

4. verdict is "pass" when exit_code == 0, otherwise "fail". Do not interpret the
   output. Do not special case anything.

5. A timeout is a FAILURE, not a crash. Record exit_code as -1, put a clear note
   in stderr_tail saying it timed out and after how long, and set verdict "fail".
   One hung check must never stop the other thirteen.

6. If the workspace directory for a step does not exist, that is also a fail:
   exit_code -2, an explanatory stderr_tail, verdict "fail". Do not create it.

7. duration_ms is measured with time.perf_counter() and is an int.

8. Never let a check's own exception escape. Catch OSError and
   subprocess.SubprocessError, record them as a fail with the message in
   stderr_tail, and carry on. A missing interpreter must not abort the batch.

9. Add a main() with argparse so it runs as:
       py -m coldstart.check --steps steps.json --workspaces target --out checks.json
   Print a one line summary per step: id, verdict, exit code, duration.
   Print a final line: "N of M checks failed".

TESTS — write these in tests/test_check.py

  - a passing check   (python -c "import sys; sys.exit(0)")  -> verdict "pass"
  - a failing check   (python -c "import sys; sys.exit(1)")  -> verdict "fail"
  - a check that times out, using a short timeout            -> exit_code -1, fail
  - a missing workspace directory                            -> exit_code -2, fail
  - a check whose argv contains a space and a quote character, proving no shell is
    involved and nothing is re-parsed
  - the output validates against coldstart.schema.validate_checks
  - stdout_tail really is the tail: emit 2000 characters and assert the LAST 500
    are what is kept

  Use tmp_path for workspaces. No network. Nothing may depend on the target repo
  being cloned.

WHEN DONE

  py -m pytest -q          must pass
  py -m ruff check .       must be clean

Report which tests you added and anything in the spec you think is wrong. If a
requirement above contradicts AGENTS.md, stop and say so rather than guessing.
```

---

## After Bob finishes

1. **Screenshot the task session summary.** Save to `docs/bob-sessions/01-check.png`.
2. Run `py -m pytest -q` and `py -m ruff check .` yourself — do not take Bob's word for it.
3. Tell me, and I will review the code against the contract before we move on.

**Expected cost:** ~1–2 Bobcoins. If it goes past 3, stop and tell me.
