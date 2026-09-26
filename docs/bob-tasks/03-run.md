# Bob Task 03 — `coldstart/run.py`

> The only module that touches the network and spends Bobcoins.
> Screenshot the session to `docs/bob-sessions/03-run.png`.

---

## The prompt

```
Read AGENTS.md and docs/ARCHITECTURE.md first, then implement coldstart/run.py.

WHAT IT DOES

For each step in steps.json, run.py gives that ONE step to a fresh headless Bob
session on its OWN clean copy of the target repository, in parallel, and records
exactly what happened. It writes the raw stream verbatim plus a parsed summary.

This is the only module in the project that touches the network or spends money,
so it is also the only one that can do real damage. Treat the budget guard and
the key handling as load-bearing, not as nice-to-haves.

INPUTS
  steps.json                    validated via coldstart.schema.load_validated()
  a pristine clone directory    target/_pristine, already cloned, DO NOT MODIFY IT
OUTPUTS
  recordings/step-NN.ndjson     the raw stdout of each bob run, byte for byte
  runs.json                     written via coldstart.schema.dump_validated()

The exact shape of runs.json is in docs/ARCHITECTURE.md. Match it precisely.

PER STEP, IN THIS ORDER

1. Prepare the workspace.
   Delete <workspaces>/ws-NN if it exists, then copy target/_pristine to it with
   shutil.copytree. NN is the step id zero padded to two digits.
   COPY, never re-clone: one network clone already happened and hammering someone
   else's repository fourteen times is both slow and rude.
   Exclude the .git directory from the copy -- it is the bulk of the bytes and Bob
   does not need it.

2. Run Bob, headless, with exactly these arguments:

     bob run
       --format stream-json
       --max-cost <max_cost>
       --max-turns <max_turns>
       --trust
       --accept-license
       --workspace <absolute path to ws-NN>
       <the step's bob_prompt>

   argv list, shell=False, explicit timeout (default 900 s), explicit cwd.
   Every one of those flags is verified to exist. Do not invent or guess any other
   flag -- inventing a flag is a fabrication and fails the task.

3. Write stdout to recordings/step-NN.ndjson VERBATIM, before parsing anything.
   If parsing later throws, the raw evidence must already be safely on disk.
   Never modify a recording after writing it.

4. Parse the NDJSON. One JSON object per line; tolerate blank lines and tolerate a
   trailing partial line without crashing.

     from the "result" event:  task_id, duration_ms, session_costs, tool_calls
     error_frames:             EVERY {"type":"error",...} object, kept in order
     capped:                   True if any error frame message matches the cost
                               limit wording, case-insensitively
     bob_final_message:        the content of the LAST {"type":"message",
                               "role":"assistant"} object
     bob_status:               copied verbatim from the result event

CRITICAL, READ TWICE

  result.status is ALWAYS the literal string "success". Both emitters in Bob's
  own bundle hardcode it, and a run capped at --max-cost 0.02 that aborted after
  one tool call and wrote nothing still reported success WITH PROCESS EXIT CODE 0.

  So: never branch on result.status. Never branch on the subprocess return code.
  Record both faithfully, and derive nothing from either.

  bob_claim is "completed" when there are no error frames, otherwise "failed".
  It is Bob's CLAIM, not a verdict. check.py supplies the verdict.

THE BUDGET GUARD -- this protects real money

  Accumulate session_costs across completed steps. Before starting any new step,
  if the running total is at or above --budget, STOP: do not start it, do not
  start anything after it, and record the remaining steps as skipped.
  Print loudly how many steps were skipped and why.
  Default budget 15.0 Bobcoins. We hold 36 in total and the rest is committed.

CONCURRENCY

  concurrent.futures.ThreadPoolExecutor, default 4 workers. Verified: 3 concurrent
  bob run processes work cleanly with separate --workspace directories.
  The budget check must be correct with several threads in flight -- guard the
  running total with a threading.Lock. When the budget trips, in-flight steps are
  allowed to finish; no NEW step starts.

THE API KEY

  Read BOB_API_KEY from the environment. If it is absent, fall back to reading
  bob.key from the repository root and set it in the child environment only.
  NEVER print it, NEVER log it, NEVER put it in runs.json, and NEVER include it in
  an error message. If it is missing entirely, exit with a clear instruction to
  create an Inference-type key -- do not attempt to run without one.

FAILURES MUST NOT CASCADE

  A subprocess timeout, an OSError, or unparseable output must be recorded against
  THAT step and must not stop the others. A step that could not run at all gets
  session_costs 0.0, an error_frame explaining why, and bob_claim "failed".

CLI

  py -m coldstart.run --steps steps.json --pristine target/_pristine \
      --workspaces target --recordings recordings --out runs.json \
      --max-cost 1.5 --max-turns 12 --concurrency 4 --budget 15

  Add --dry-run, which prepares the workspaces and PRINTS the exact command line
  for each step without executing any of them and without spending anything.
  I will use --dry-run to review the commands before we spend real coins.

  Print per step: id, claim, cost, duration, tool calls.
  Print at the end: total Bobcoins, total USD at 0.50 per coin, and
  "N of M steps reported an error frame".

TESTS -- tests/test_run.py, and NONE of them may hit the network

  Stub subprocess.run with monkeypatch and feed it canned NDJSON.

  - a clean run parses cost, duration, tool_calls and task_id correctly
  - a run containing an error frame sets capped True and bob_claim "failed",
    EVEN THOUGH the result event says status "success" -- this is the single most
    important test in the file
  - result.status "success" plus returncode 0 must NEVER on its own produce
    bob_claim "completed" when an error frame is present
  - malformed JSON on one line does not crash the parse
  - the raw recording is written even when parsing afterwards raises
  - the budget guard stops starting new steps once the total is reached
  - BOB_API_KEY never appears in runs.json or in any printed output
  - the output validates against coldstart.schema.validate_runs

WHEN DONE
  py -m pytest -q       must pass
  py -m ruff check .    must be clean

Do not run bob for real. I will do that after reviewing with --dry-run.
Report anything in this spec you think is wrong rather than guessing.
```

---

## After Bob finishes

1. Screenshot → `docs/bob-sessions/03-run.png`
2. `py -m pytest -q` and `py -m ruff check .`
3. Tell me — I review before we spend a single coin on a real pass.

**Expected 3–5 Bobcoins.** Past 6, stop and tell me.
