# Phases — Cold Start

> Build order, checkpoints, and the cut list.
>
> **27.5 hours remaining** at the time of writing (2026-09-26 16:30 PKT).
> Deadline: **2026-09-27 20:00 PKT.**

---

# The Rule

**Every phase ends with something submittable.** If the clock stops at any checkpoint, we
still have an entry. That is the opposite of how HEAT-HOURS was built, where the demo plan
did not exist until days after the research finished.

---

# Budget

| Resource | Total | Reserved | Free |
|---|---|---|---|
| Hours | 27.5 | 6 for video, slides, statements, submission | **21.5 for build** |
| Bobcoins | 39.7 | 15 for the re-record after the patch | **~20 for the first pass** |

**Submission assets are reserved time, not leftover time.** Both previous entries left them
to the end. One of them has an unticked submission checkbox to this day.

---

# Phase 0 — Foundations · 1.5 h · NO BOBCOINS

| | |
|---|---|
| Build | `pyproject.toml`, pytest, ruff, the five JSON schemas, `schema.py` validators, golden-file test harness |
| Checkpoint | `pytest` runs green on an empty suite. `ruff check` clean |
| If we stop here | Nothing. This is the only phase with no standalone value |

**Why first anyway:** the schema validators are what stop two AI-written modules quietly
disagreeing about a field name at hour 19.

---

# Phase 1 — The Spine · 3 h · ~2 Bobcoins

| | |
|---|---|
| Build | `split.py` → `steps.json` for sqlfluff, 14 steps, 5 known reds. `check.py` → `checks.json`. The five deterministic checks are already written and verified |
| Probe | ONE real `bob run` on ONE prose step of sqlfluff at `--max-cost 1.5`, to measure true per-step cost |
| Checkpoint | `steps.json` validates. `check.py` correctly reports 5 fails against a fresh clone **with no Bob involved at all** |
| If we stop here | A table of five provably broken steps in a real project, with the fix for each. Thin, but real and honest |

**The probe is the gate.** If one prose step costs more than ~2 coins, we cut from 14 steps
to 8 and say so in the deck. We do **not** shrink `--max-cost` — that manufactures false reds.

---

# Phase 2 — The Real Pass · 4 h · ~12 Bobcoins

| | |
|---|---|
| Build | `run.py`: pristine clone, per-step workspace copy, 4-way parallel `bob run`, NDJSON capture, error-frame parsing, `runs.json` |
| Run | All 14 steps, for real, recorded |
| Checkpoint | 14 committed `.ndjson` files. `runs.json` has real costs. **The overrule count is known** |
| If we stop here | Measured evidence: what each documented step costs, which ones fail, what Bob claimed vs what is true. That is already a submission |

**This phase produces the headline number.** Everything after it is presentation.

⚠️ **Hard stop at 20 cumulative coins.** If the batch approaches it, abort and keep what we have.

---

# Phase 3 — The Runway · 5 h · NO BOBCOINS

| | |
|---|---|
| Build | `render.py`: the three JSON files → one static HTML file, inline SVG, inline CSS. Tiles with cost and minutes, the overrule flip, click-through to the real failing command and error text |
| Checkpoint | Byte-stability test passes. Opens from `file://` with the network disconnected |
| If we stop here | **A complete, demoable submission.** This is the real floor |

**Test it with the wi-fi off.** That is the actual requirement, and it is testable.

---

# Phase 4 — The Payoff · 3 h · ~10 Bobcoins

| | |
|---|---|
| Build | `docs-fix.patch` — the five corrections, already drafted from verified evidence |
| Run | Re-record **only the red steps** against the patched doc |
| Checkpoint | Second runway: the reds turn green. Wasted-cost total drops to near zero |
| If we stop here | The before/after, which is the money shot |

**Re-record only the fixed steps.** The renderer is a pure function of committed files, so
the nine green recordings stay valid. This is 3–5 coins instead of 12–16.

⚠️ **This phase can fail.** The patch might not turn everything green. If so, we show what
did change and say the rest honestly. A partial, true result beats a fabricated clean one.

---

# Phase 5 — Submission · 6 h · NO BOBCOINS

Reserved, not leftover.

| Asset | Time | Note |
|---|---|---|
| 3-min video | 2.0 h | **≥90 s must show the solution working.** Screen capture, hard cuts, narration |
| Slide deck | 1.0 h | Slide 1 names the prior art and what it does not do |
| Long description, 500 words | 0.75 h | Problem and solution |
| **IBM Bob Usage Statement, 500 words** | 0.75 h | Required. We have a genuinely strong story here |
| Bob task-session screenshots | 0.5 h | Required deliverable. Capture as we go, not at the end |
| Cover image | 0.25 h | The runway, cropped, legible as a thumbnail |
| README + disclosure | 0.5 h | Limits above the fold |
| **Submit** | 0.25 h | **Do this with 2 hours to spare, then improve** |

**Submit early, then improve.** A finished entry filed at hour 25 beats a better one that
misses at hour 28.

---

# The Cut List — in the order we cut

1. The vocabulary/insight panel. Nice, not needed
2. Click-through to the full transcript. The error text alone carries it
3. Steps 10–14. Ship 9 tiles and say the doc has 14
4. The amber state. Fold into red with a footnote
5. **The patch re-record.** Painful, but Phase 3 alone is still a submission

**Never cut:** the deterministic check, the committed recordings, the overrule count, the
per-step cost, or the disclosure section. Those are the entry.

---

# Checkpoints Against The Clock

| Time | Must be true |
|---|---|
| **20:00 today** | Phase 0 + 1 done. Real per-step cost known |
| **01:00** | Phase 2 done. Recordings committed. Overrule count known |
| **09:00** | Phase 3 done. Runway renders offline |
| **13:00** | Phase 4 done or cut |
| **15:00** | Video recorded |
| **18:00** | **SUBMITTED** |
| 18:00–20:00 | Improve, re-upload if better |

**If a checkpoint slips by more than 2 hours, cut from the list above rather than compress
Phase 5.** Presentation is a judged criterion; an unpolished demo of a real result scores;
an unsubmitted masterpiece does not.
