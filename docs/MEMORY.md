# Memory — Cold Start

> Verified facts, decisions and **why**, and what changed our minds.
>
> **Append, never rewrite.** A superseded entry stays, with its correction underneath.
> The record of being wrong is more useful than a tidy record.

---

# 1. Verified Facts

Every row below was **executed on this machine**, not read in a doc. Do not re-verify.

## Bob Shell

| # | Fact | How verified | Date |
|---|---|---|---|
| V1 | Bob Shell **2.0.5**, commit `2dc180906`, installed via `powershell -c "irm -Uri https://bob.ibm.com/download/bobshell.ps1 \| iex"` | ran it | 09-26 |
| V2 | **Headless requires an API key.** Browser login authenticates the interactive client only. `bob run` without `BOB_API_KEY` → `Error: Bob API key is required.` | ran it | 09-26 |
| V3 | Key type **`Inference`** needs no `--team-id`. Type `General` does | IBM docs + working key | 09-26 |
| V4 | Real flags on `bob run`: `-f/--format`, `-w/--workspace`, `--mode`, `--max-cost`, `--max-turns`, `--disable-mcp`, `--disable-subagents`, `--disable-tool-groups`, `--trust`, `-r/--resume`, `--accept-license`, `--team-id`, `--log-level` | `bob run --help` | 09-26 |
| V5 | Top-level commands: `chat`, `run`, `mcp`, `acp`. **No `login`, `whoami`, `account` or balance command** | `bob --help` | 09-26 |

## The cost signal — the heart of the project

| # | Fact |
|---|---|
| **V6** | The `result` event carries **`task_id`, `duration_ms`, `session_costs`, `max_cost`, `tool_calls`** — and nothing else. **No token counts. No cache ratios.** |
| **V7** | **`status` is ALWAYS the literal `"success"`.** Both emitters in `bob.js` (lines 6149, 6234) hardcode `status:"success"`. There is no failure branch. |
| **V8** | A run capped at `--max-cost 0.02` aborted after one tool call, wrote nothing it was asked to write, and emitted `{"type":"result","status":"success",...}` **with process exit code 0.** |
| **V9** | Failure appears **only** as `{"type":"error","severity":"error","message":"The task reached the cost limit of 0.020 (spent: 0.025)."}` |
| V10 | **The cap is soft.** Capped at 0.02, actually spent 0.025 — ~25% overshoot. Budget for it |

## Cost and concurrency

| # | Fact |
|---|---|
| V11 | **Parallel runs work.** 3 concurrent `bob run` with separate `--workspace`: 11.7 s wall vs ~24 s sequential. No throttling, no lock contention |
| V12 | **Cost is deterministic.** All three identical parallel runs returned `session_costs: 0.075452` — identical to six decimal places |
| V13 | Measured: 1 tool call / 2 files = **0.049862**. 2 tool calls / 1 file = **0.075452** |
| V14 | Budget: **40 Bobcoins**, team `ibm-hackathon-lablab`, plan Enterprise. 1 Bobcoin = **$0.50** |

## The demo target — sqlfluff/sqlfluff

All five verified by direct API call on 2026-09-26.

| # | The doc says | Reality |
|---|---|---|
| V15 | `tox -e py310 -- test/core/parser/grammar_test.py` | **HTTP 404.** Split into `test/core/parser/grammar/` |
| V16 | config in `plugins/sqlfluff-templater-dbt/test/fixtures/dbt/profiles.yml` | **404.** Moved to `.../dbt/profiles_yml/profiles.yml` (that path returns 200) |
| V17 | `tox -e cov-init,dbt019-py310,cov-report-dbt` | **`dbt019` is not in tox.ini.** Real envs: `dbt{170,180,190,1100}` |
| V18 | set `SQLFLUFF_GITHUB_TOKEN` | **`util.py` never reads it.** It reads `GITHUB_TOKEN` |
| V19 | `make release 3.4.2` | Makefile takes `VERSION=`; a positional is parsed as a second goal |
| V20 | CONTRIBUTING.md is **406 lines, 20,075 bytes**, and contains a section headed **"AI-Assisted Contributions"** — the project explicitly welcomes what we are doing |

## IBM's own surface

| # | Fact |
|---|---|
| V21 | **Bobalytics** has Metrics / Insights / Today. Scope is Team or User. Refresh **every 60 minutes**. It measures **people and adoption**, never code and never per-task cost attribution. It does not compete with us |

---

# 2. Decisions, And Why

| # | Decision | Reason |
|---|---|---|
| D1 | **Build Cold Start, not C1** | C1's colour axis was "did Bob finish", which V7/V8 prove is unreadable. Cold Start's verdict comes from an independent deterministic check, which C1 did not have |
| D2 | **Target sqlfluff/sqlfluff** | Two independent lanes converged on it. Five proven breaks of five different types, ~10 steps still work, MIT-compatible, Python, Windows-fine, no Docker — and V20 means the PR is welcome |
| D3 | **Modules talk through JSON files on disk** | Makes `render.py` a pure function, so the demo cannot break live. Also makes each module independently testable against golden files |
| D4 | **`--max-cost 1.5`, not 0.5** | Measured real maintenance tasks cost 1.3–3.3 coins. A 0.5 cap would abort legitimate work and paint a **false red** — a false accusation about someone else's project, on camera |
| D5 | **Zero runtime dependencies** | Nothing to install on a judge's machine, nothing to break at hour 25, and `render.py` has no way to reach the network even by accident |
| D6 | **`expected` is recorded but never read downstream** | It is our prediction. If we let it drive a colour, the runway would show what we assumed instead of what happened |
| D7 | **Validate before writing** | A rejected artifact never reaches disk, so a later module cannot read it and produce a plausible wrong answer |
| D8 | **Copy from one pristine clone, never clone 14 times** | Faster, and it is rude to hammer someone's repo |

---

# 3. What Changed Our Minds

### R1 — The whole first idea was unbuildable

**Believed:** C1, the Module Cost Map, colouring modules by whether Bob finished.
**Found:** V7 and V8. Bob always reports success, with exit code 0.
**Changed to:** Cold Start, where an independent deterministic check supplies the verdict.
**Cost of finding out late:** this would have surfaced around hour 20 as a runway of
meaningless green tiles.

### R2 — Three August research claims were false

All from `AI-Hackathon-Research-OS/experiments/ibm-bob-2-2026/`, all falsified by running things:

1. *"`--mode`, `--disable-subagents`, `--disable-mcp`, `--disable-tool-groups` do not exist;
   the real flag is `--chat-mode`."* **All four exist. There is no `--chat-mode` on `bob run`.**
2. *"The result event carries total/input/output tokens and cache ratios."* **It carries none.**
3. Headless auth was not mentioned at all, and it is a hard gate.

**Lesson:** desk research against documentation is a hypothesis. Ten minutes of running the
tool is worth more than a day of reading about it.

### R3 — A weak error message is a real defect

The first `schema.py` rejected a shell-string `cmd` with *"expected list, got str"*. A test
demanded the message explain **why**. Fixed to name the injection risk and the Windows
quoting hazard. At hour 19 the difference between those two messages is twenty minutes.

---

# 4. Open Questions

| # | Question | Blocks | When |
|---|---|---|---|
| Q1 | What does a **real** prose step cost at `--max-cost 1.5`? | Whether 14 steps fit in the budget | Phase 1 probe |
| Q2 | Which NDJSON frame carries `MaxCostReachedError` in a long run? | The amber/grey tile state | Phase 2 |
| Q3 | Does the patch actually turn the reds green? | The payoff shot | Phase 4, ~hour 14 |
| Q4 | Will a sqlfluff maintainer accept the PR in time? | Nice-to-have, not load-bearing | after submission |

---

# 5. Log

| Date | Entry |
|---|---|
| 2026-09-26 13:29 | Bob IDE found installed; Bob Shell absent. ~30.5 h to deadline |
| 2026-09-26 14:08 | Bob Shell 2.0.5 installed, Inference key created, **cost gate PASSED** |
| 2026-09-26 15:00 | 30-agent workflow: C1 killed on V7/V8, Cold Start selected 50/60 |
| 2026-09-26 16:15 | 4-agent hunt: **sqlfluff/sqlfluff** chosen, 5 breaks verified by hand |
| 2026-09-26 16:45 | Phase 0 complete: contracts frozen, 14 tests green, ruff clean |
| | **NEXT: Phase 1 — `split.py`, `check.py`, and the one-step cost probe** |
