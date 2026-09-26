# Submission — Cold Start

Everything to paste into the lablab.ai form. Figures are from the committed
recordings; nothing here is estimated.

---

## Project Title

**Cold Start — your onboarding doc is a promise, this is the receipt**

## Short Description

Cold Start makes IBM Bob actually perform your setup guide, one step per parallel
headless session on its own clean clone, then a deterministic check decides whether each
step really worked. On sqlfluff it found four broken instructions — and caught Bob
reporting success on three of them.

---

## Long Description — Problem & Solution (486 words)

**The problem.** Every project has a setup guide, and every setup guide rots. A path moves,
a test environment is renamed, a script starts reading a different variable. Nobody notices,
because the people who wrote it never follow it again. The new hire notices — after they have
burned an afternoon on a step that cannot work.

Two things make this worse now. First, teams point AI coding agents at these guides. Second,
agents are very good at getting around a broken instruction without telling you. That second
one is the part nobody measures.

**What Cold Start does.** Point it at a repository. It splits the setup guide into discrete
steps and gives each step to its own headless IBM Bob session, running in parallel, each on
its own clean clone so no step inherits another's mess. It records every session verbatim.

Then — and this is the whole design — a **deterministic check** runs in that same workspace
after Bob exits. No model, no heuristic. It runs one command and reads the exit code. Zero is
pass, anything else is fail. The check is the verdict; Bob's opinion is only evidence.

The output is an itemised receipt: every step with the real money and the real minutes it
consumed, read from Bob's own result event. Broken steps are struck through with the exact
artefact the check looked for. And the page carries a patch that fixes the document.

**What it found on sqlfluff/sqlfluff** (9.9k stars, commit `c7401613`):

| | Before | After the patch |
|---|---|---|
| Cost to walk the guide | **$1.51** | $1.06 |
| Wasted on steps that cannot work | **$1.02 (67%)** | **$0.00** |
| Steps that cannot work | **4 of 14** | **0 of 14** |
| Bob claimed success, check disagreed | **3 of 13** | **0** |

**The finding that matters.** Step 11 tells you to run `tox -e cov-init,dbt019-py310,...`.
There is no `dbt019` environment. Bob silently substituted `dbt190`, added *"(substituting
whichever dbt version you actually want to test against)"*, and reported the task complete.
It never said the documentation was wrong. A human following the guide literally gets an
error; the agent quietly papered over it.

That is why "the agent said it worked" cannot be the verdict, and it is the reason the
deterministic check exists.

**Who it is for.** Any team that maintains a setup guide, and — more urgently — any team
pointing coding agents at their own repository and trusting what comes back. The overrule
rate generalises well beyond documentation: every agent-completed ticket could carry an
independent check and a number.

**What we shipped.** Four stdlib-only Python modules with no runtime dependencies, 76 tests,
28 committed raw transcripts, two receipts rendered as pure functions of those transcripts,
and a verified four-change patch we are sending sqlfluff as a pull request.

---

## IBM Bob Usage Statement (497 words)

Bob was used two ways: as the **engine inside the product**, and as the **developer that
built it**. Both are evidenced in the repository.

**Bob as the engine.** Cold Start drives `bob run --format stream-json` headless, one session
per documented step, four concurrent, each with `--workspace` pointed at its own clean clone
and `--max-cost` as a hard cap. Every session's NDJSON is committed verbatim under
`recordings/` and `recordings-after/` — 28 transcripts. Cost, duration and tool-call counts
come from Bob's own `result` event; nothing is estimated. Authentication is an Inference-type
API key via `BOB_API_KEY`, which never appears in any artifact or log and is excluded by both
`.gitignore` and `.bobignore`.

**Bob as the developer.** Bob wrote `coldstart/check.py`, `coldstart/run.py` and
`docs-fix.patch`, in Agent mode, from written specs in `docs/bob-tasks/`. `AGENTS.md` gives it
the frozen data contracts and the project rules; its own telemetry confirms this loads as
1,321 tokens of `projectRules` into every task. `coldstart/sessions.py` exports the full task
history from Bob's local database as `docs/bob-sessions/sessions.json` — machine-readable
evidence a judge can check rather than take on trust.

Bob did some things better than the spec asked. It chose POSIX exit conventions (124 for
timeout, 127 for command-not-found) over the values we specified. It found a Windows
`NotADirectoryError` unprompted. Told to mention `GITHUB_REPOSITORY_OWNER` in the patch, it
worked out *why* — a contributor fixing only the token name hits a second `KeyError` one line
later — and documented that.

**The honest part.** Review caught Bob being confidently wrong three times, and caught us
being wrong twice more.

Bob's first `check.py` handled a missing workspace by walking up the directory tree and
running the check somewhere else. We measured it: two of three paths reported **pass** for a
step whose workspace never existed, because the check found our own `pyproject.toml` further
up. A false green, inside the module whose entire job is to be the thing that cannot be
fooled. Bob fixed it in one pass once given a failing test.

Its NDJSON parser read the `result` fields from the top level when they are nested under
`stats`, so a run that cost 0.625934 coins reported 0.0000 — every figure on the receipt would
have been zero.

And our own claim logic treated silence as success: a session that produced no result event at
all was recorded as "completed", which rendered green. Two of fourteen sessions in the second
run returned nothing, an intermittent headless failure we only saw because the raw transcripts
are kept.

One more, verified in Bob's own bundle: **`result.status` is the literal string `"success"` in
both emitters.** A capped run that wrote nothing still reports success, with exit code 0. The
local database records `error` for that same task. Bob knows; the headless result event does
not say.

Cold Start's thesis proved itself on Cold Start. Total spend: 26.9 Bobcoins.

---

## Video Script — 3:00, ≥90s showing the solution working

Screen capture only. No talking head. Hard cuts, no music under narration.

| Time | On screen | Narration |
|---|---|---|
| **0:00–0:15** | sqlfluff's CONTRIBUTING.md scrolling. Ordinary, well written | "This is sqlfluff's setup guide. Nine thousand stars, a real project, a careful document. Four of its instructions point at things that no longer exist — and nobody knows." |
| 0:15–0:30 | `steps.json` in an editor, then the command line | "Cold Start splits the guide into fourteen steps and hands each one to its own IBM Bob session. Fourteen sessions, four at a time, each on its own clean clone." |
| **0:30–1:15** | **Terminal: `bob run --format stream-json` streaming live.** Tool calls scrolling | "Bob is actually performing the steps. Not reading them — doing them. Every session is recorded verbatim." *(let it run, minimal talking)* |
| 1:15–1:35 | `check.py` running, verdicts printing | "Then a deterministic check runs in the same workspace. No model. One command, one exit code. Zero is pass." |
| **1:35–2:05** | **`web/index.html` — the receipt assembling** | "Following this guide costs a dollar fifty-one. A dollar two of that buys nothing." *(pause on the hero number)* |
| **2:05–2:25** | **Scroll to step 11. Hold on the OVERRULED flag** | "Bob was told to run the dbt019 environment. It doesn't exist. Bob silently substituted dbt190, said nothing was wrong, and reported success." *(4 seconds of silence on the stamp)* |
| 2:25–2:40 | `git apply docs-fix.patch`, then `web/after.html` | "Here's the patch. Same harness, same prompts, the corrected document." |
| 2:40–2:55 | Before and after side by side | "A dollar two wasted, down to zero. Four broken steps, down to none." |
| 2:55–3:00 | The PR body | "We're sending this to sqlfluff. Their guide invites AI-assisted contributions." |

**Hold the OVERRULED stamp for four full seconds in silence.** That frame is the submission.

---

## Cover Image

`web/cover.html` → screenshot at 1200×630. Two elements, one colour.

---

## Checklist

- [ ] Project title, short description, long description
- [ ] IBM Bob Usage Statement
- [ ] Public repo URL
- [ ] **Bob task-session screenshots** in `docs/bob-sessions/`
- [ ] Demo video, ≤3 min, MP4
- [ ] Slide presentation
- [ ] Cover image
- [ ] Application URL — `web/index.html` (static, host on Netlify or GitHub Pages)
- [ ] **Submitted before 27 Sept 20:00 PKT**
