# IBM Bob Task Sessions — evidence

Required hackathon deliverable, in two forms.

## Screenshots

| File | What it shows |
|---|---|
| `all-tasks.png` | The Bob Tasks panel: all five build tasks with their Bobcoin cost |
| `00-all-tasks.png` | The same, full window, for context |

Every task title begins **"Read AGENTS.md"** — that is `AGENTS.md` being loaded into each
session, which Bob's own telemetry records as 1,321 tokens of `projectRules`.

## Machine-readable

`sessions.json` is exported by `coldstart/sessions.py` directly from Bob's local task
database, read-only. It carries every session's id, status, cost, message count and
timestamp — a judge can check it rather than take a screenshot on trust.

Two kinds of session are in there:

- **Build tasks** (the five in the screenshot) — Bob writing `check.py`, `run.py`,
  `docs-fix.patch`, the README and the deck, in Agent mode from specs in `docs/bob-tasks/`.
- **Headless product runs** — the 28 sessions Cold Start itself drove via
  `bob run --format stream-json`, one per documented step, twice over.

One thing the export records that the screenshot cannot: the task capped by `--max-cost`
is stored with `status: "error"`, while that same task's stream reported
`status: "success"`. Bob knows it failed. The headless result event does not say so. That
discrepancy is why Cold Start never trusts `result.status`.
