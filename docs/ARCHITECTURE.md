# Architecture — Cold Start

> The contracts come first. Everything else is negotiable.
>
> Last updated: 2026-09-26

---

# The One Rule That Shapes Everything

**Every module is a pure function from files on disk to files on disk.**

No module imports another module's internals. No module passes objects to another module.
They communicate through **JSON files that are committed to the repository.**

This is not architectural purity for its own sake. It buys four specific things:

| It buys | Why it matters here |
|---|---|
| **A deterministic demo** | The renderer is a pure function of committed files. No network, no API key, no model at render time. The video cannot break |
| **Independent testing** | Each module gets golden-file tests. AI-written code fails silently; golden files catch it |
| **Independent building** | If `run.py` is half-finished at hour 18, `render.py` still works against committed recordings |
| **A checkable claim** | A judge can re-render our exact runway from our committed data. Application of Technology becomes verifiable |

**The one exception is `run.py`**, which touches the network. It is quarantined on purpose,
and it is the only module that needs `BOB_API_KEY`.

---

# The Pipeline

```
  target/CONTRIBUTING.md
          │
          ▼  split.py          deterministic markdown parse + curation file
     steps.json
          │
          ▼  run.py            ← THE ONLY MODULE THAT TOUCHES THE NETWORK
     recordings/step-NN.ndjson   (raw, verbatim, committed)
     runs.json                   (parsed stats, committed)
          │
          ▼  check.py          deterministic post-check. NO MODEL.
     checks.json
          │
          ▼  render.py         pure function. no network. no key.
     web/index.html
```

Each arrow runs independently. Each can be re-run without the others.

---

# Data Contracts

These are frozen. A change here is a breaking change and needs a note in `MEMORY.md`.

## `steps.json`

Produced by `split.py`. The spine of everything.

```json
{
  "schema": "coldstart.steps/1",
  "source_repo": "sqlfluff/sqlfluff",
  "source_commit": "<40-char sha>",
  "doc_path": "CONTRIBUTING.md",
  "doc_sha256": "<hex>",
  "steps": [
    {
      "id": 1,
      "title": "Clone the repository",
      "doc_lines": [42, 47],
      "quote": "<verbatim text from the doc>",
      "kind": "command",
      "bob_prompt": "<what we ask Bob to DO for this step>",
      "check": {
        "cmd": ["python", "-c", "import pathlib,sys; sys.exit(0 if pathlib.Path('setup.py').exists() else 1)"],
        "describes": "the file the step says will exist"
      },
      "expected": "green"
    }
  ]
}
```

| Field | Rule |
|---|---|
| `id` | 1-based, contiguous, never reused |
| `quote` | **Verbatim from the doc.** Must match the bytes at `doc_lines`. Tested |
| `kind` | `command` or `prose`. Prose steps are the ones a doc-runner cannot execute |
| `bob_prompt` | What Bob is asked to do. Never mentions whether we expect it to fail |
| `check.cmd` | **argv list, never a shell string.** No shell injection, no quoting bugs |
| `expected` | `green` / `red` / `unknown`. Our prediction. Recorded so we can be wrong in public |

**`expected` is a prediction, not a control.** Nothing downstream may read it to decide a
colour. It exists so the run can prove us wrong. `render.py` may display it; it may never
use it.

## `runs.json`

Produced by `run.py`. One entry per step.

```json
{
  "schema": "coldstart.runs/1",
  "bob_version": "2.0.5",
  "recorded_at": "<iso8601>",
  "max_cost": 1.5,
  "runs": [
    {
      "step_id": 1,
      "task_id": "<bob task id>",
      "ndjson": "recordings/step-01.ndjson",
      "session_costs": 0.4831,
      "duration_ms": 41233,
      "tool_calls": 7,
      "bob_status": "success",
      "error_frames": [],
      "capped": false,
      "bob_claim": "completed",
      "bob_final_message": "<last assistant message, verbatim>"
    }
  ]
}
```

### ⚠️ `bob_status` is ALWAYS `"success"`. Never trust it.

Verified 2026-09-26, two independent ways:

1. **In Bob's own bundle.** Both `type:"result"` emitters in `bob.js` (lines 6149, 6234)
   contain the literal `status:"success"`. There is no failure branch.
2. **Live.** A run capped at `--max-cost 0.02` aborted after one tool call, having written
   nothing it was asked to write, and still emitted
   `{"type":"result","status":"success",...}` — **with process exit code 0.**

So the fields that actually carry failure are:

| Field | Source |
|---|---|
| `error_frames` | every `{"type":"error",...}` frame in the NDJSON |
| `capped` | true when an error frame matches `reached the cost limit` |
| `bob_claim` | parsed from Bob's final assistant message — what Bob *says* happened |

**`bob_claim` is evidence, not a verdict.** It is one half of the save.

## `checks.json`

Produced by `check.py`. **This module never calls a model and never touches the network.**

```json
{
  "schema": "coldstart.checks/1",
  "checks": [
    {
      "step_id": 1,
      "cmd": ["python", "-c", "..."],
      "exit_code": 0,
      "stdout_tail": "<last 500 chars>",
      "stderr_tail": "<last 500 chars>",
      "duration_ms": 120,
      "verdict": "pass"
    }
  ]
}
```

`verdict` is `pass` when `exit_code == 0`, `fail` otherwise. **There is no third option and
no judgement.** That is the whole point: the check is a fact.

## The derived verdict — computed in `render.py`, stored nowhere

| Bob claims | Check says | Tile | Meaning |
|---|---|---|---|
| completed | pass | 🟢 green | It works |
| completed | fail | 🔴 **red, flagged OVERRULED** | **The save.** Bob said it worked. It did not |
| failed/capped | fail | 🔴 red | Honestly broken |
| failed/capped | pass | 🟡 amber | Bob gave up but the state is fine. Rare, disclose it |

**The overruled count is the headline save**, and it must be printed verbatim as
`N of M` — *"the check overruled Bob on 2 of 9 claimed successes."*

---

# Module Responsibilities

| Module | Reads | Writes | Network | Model | Pure |
|---|---|---|---|---|---|
| `split.py` | the doc | `steps.json` | ❌ | ❌ | ✅ |
| `run.py` | `steps.json` | `recordings/*.ndjson`, `runs.json` | ✅ | ✅ (Bob) | ❌ |
| `check.py` | `steps.json`, workspaces | `checks.json` | ❌ | ❌ | ⚠️ runs subprocesses |
| `render.py` | all three JSON files | `web/index.html` | ❌ | ❌ | ✅ |
| `patch.py` | `steps.json` | `docs-fix.patch` | ❌ | ❌ | ✅ |

**`render.py` being pure is the demo's insurance policy.** HEAT-HOURS survived its API going
down twice during build week because everything was pre-computed. Same principle.

---

# Workspace Isolation

Each step runs on its **own clean copy** of the target repo. Otherwise step 7 inherits step
6's mess and the measurement is meaningless.

```
target/
  _pristine/          git clone --depth 1, done ONCE
  ws-01/ ws-02/ ...   filesystem copy per step, created fresh
```

**Copy, do not re-clone.** Cloning sqlfluff fourteen times over the network is slow and
rude. One shallow clone, then local copies.

Each `bob run` gets `--workspace target/ws-NN`, so Bob cannot see the other steps.

---

# Cost Control — Non-Negotiable

Budget is **40 Bobcoins**, about 39.7 remaining.

| Control | Value | Why |
|---|---|---|
| `--max-cost` | **1.5** per step | Measured real maintenance tasks cost 1.3–3.3. 0.5 would cap legitimate work and paint false reds |
| `--max-turns` | 12 | Stops a loop |
| Concurrency | 4 | Verified 3 concurrent runs work cleanly |
| Hard stop | abort the batch if cumulative spend exceeds **20 coins** | Half the budget stays for the re-record after the patch |

**The cap is soft.** A run capped at 0.02 actually spent 0.025. Budget for ~20% overshoot.

---

# What We Deliberately Do Not Build

- No database. JSON files on disk.
- No web framework. One static HTML file with inline SVG and inline CSS.
- No JS build step. No bundler, no npm install for the output.
- No live mode. The demo replays committed recordings, always.
- No model anywhere except inside `bob run`.
- No auth, no multi-user, no config UI.

**The Bob #1 project that placed shipped flat 2D rectangles plus 78 tests.** Scope discipline
is a documented winning trait at this event, not a compromise.
