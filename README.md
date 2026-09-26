# Cold Start

Your onboarding doc is a promise. This is the receipt.

---

## The result

Target: [sqlfluff/sqlfluff](https://github.com/sqlfluff/sqlfluff) at commit `c7401613`,
`CONTRIBUTING.md`, 14 steps.

|                                        | Before      | After the patch |
|----------------------------------------|-------------|-----------------|
| Cost to walk the guide                 | $1.51       | $1.06           |
| Wasted on steps that fail              | $1.02       | $0.00           |
| Steps that cannot work                 | 4 of 14     | 0 of 14         |
| Bob claimed success, check disagreed   | 3 of 13     | 0               |

1 Bobcoin = $0.50 (IBM published rate). Figures read from Bob's own `result` event in
the committed recordings under `recordings/` and `recordings-after/`.

---

## The finding

Step 11 tells you to run `tox -e cov-init,dbt019-py310,...`. There is no `dbt019`
environment. Bob silently substituted `dbt190`, added "(substituting whichever dbt version
you actually want to test against)", and reported the task complete — it never said the
documentation was wrong.

A human following the guide literally gets an error. That is exactly why a deterministic
check exists: "the agent said it worked" cannot be the verdict.

---

## How it works

```
CONTRIBUTING.md  →  (curated by hand)  →  steps.json
steps.json       →  run.py     →  recordings/*.ndjson + runs.json   ← only stage with network
steps + repo     →  check.py   →  checks.json                       ← no model, ever
all three        →  render.py  →  web/index.html                    ← pure function of committed files
recordings       →  reparse.py →  runs.json                         ← re-read the tape, spend nothing
```

`run.py` is the only stage that touches the network. `render.py` is a pure function of
`steps.json`, `runs.json` and `checks.json`, all of which are committed. The demo cannot
break.

A check is: run one argv, read the exit code. Zero is pass, anything else is fail. No
model, no heuristic, no "this output probably means it worked."

---

## Run it yourself

```sh
# 1. Install. No runtime dependencies; Python 3.10+.
pip install -e ".[dev]"

# 2. Rebuild BOTH receipts from the committed recordings.
#    No API key, no Bobcoins, no network. This re-reads the raw transcripts
#    and reproduces every figure in the table above.
py -m coldstart.reparse
py -m coldstart.render --runs runs.json --checks checks.json --out web/index.html

py -m coldstart.reparse --steps steps.after.json --recordings recordings-after --out runs.after.json
py -m coldstart.render  --steps steps.after.json --runs runs.after.json --checks checks.after.json --out web/after.html

# 3. Open them
start web/index.html      # Windows. macOS: open web/index.html
start web/after.html
```

`check.py` is not in that list on purpose: it runs the deterministic checks inside the
per-step workspaces, and those are 42 MB clones that are not committed. It runs as part of
a live pass.

To do a live pass yourself you need an Inference-type `BOB_API_KEY`. The before run cost
**3.0156 Bobcoins ($1.51)**; the after run cost **1.9696 ($0.98)**.

```sh
git clone --depth 1 https://github.com/sqlfluff/sqlfluff.git target/_pristine
py -m coldstart.run   --steps steps.json --pristine target/_pristine                       --workspaces target --recordings recordings --out runs.json                       --max-cost 1.2 --max-turns 25 --concurrency 4 --budget 13
py -m coldstart.check --steps steps.json --target target --output checks.json
py -m coldstart.render --out web/index.html
```

---

## Honest limits

- **The 14 steps are curated by hand.** Cold Start does not auto-split a document. A human
  read `CONTRIBUTING.md` and wrote `steps.json`. The tool currently runs on one document
  that a human prepared.

- **One repository, one run each way.** n=1. These are not aggregate statistics.

- **2 of 14 sessions in the second run returned no result event at all** — an intermittent
  Bob headless failure. Both were re-run manually. We only saw this because the raw NDJSON
  transcripts are committed and inspected. A tool that trusted `bob run`'s exit code would
  have silently recorded those sessions as successful.

- **`result.status` is the literal string `"success"` in both of Bob's result emitters.**
  A run capped at `--max-cost 0.02` that aborted after one tool call and wrote nothing still
  reports `status: "success"` with exit code 0. Cold Start never branches on `result.status`
  or on the exit code of `bob run`. Failure is read only from `{"type":"error",...}` frames
  in the NDJSON stream. This is a fact about the platform, stated neutrally.

---

## What IBM Bob did

Bob is the engine the product drives: `run.py` calls `bob run --format stream-json`
headless, one session per step, four concurrent, each with `--workspace` on its own clean
clone and `--max-cost` as a hard cap.

Bob also built the product. It wrote `coldstart/check.py`, `coldstart/run.py` and
`docs-fix.patch` in Agent mode, from written specs in `docs/bob-tasks/`. The full task
history is exported as `docs/bob-sessions/sessions.json` — machine-readable evidence, not
a screenshot.

---

## The patch

Four changes to `CONTRIBUTING.md`: a test file that was split into a package, a fixture
that moved down one directory, a tox environment that no longer exists, and an environment
variable the release script never reads. See [`docs/PR_BODY.md`](docs/PR_BODY.md).

We are sending this to sqlfluff. Their guide has a section headed "AI-Assisted
Contributions." The receipt is addressed to them.

---

## Licence

MIT. Author: Muhammad Faisal.
