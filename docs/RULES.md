# Rules — Cold Start

> Engineering rules for a project written almost entirely by an AI, under time pressure,
> that will be judged by strangers who cannot ask us questions.
>
> These are not style preferences. Each one exists because of a specific way this project
> can fail.

---

# 1. Never Trust A Success Signal You Did Not Verify

**This project exists because of a lie in a success signal**, so we do not get to repeat it.

Found on 2026-09-26, the hard way:

```
bob run --max-cost 0.02 "read app.py, write tests, run them, write a README"
→ aborted after ONE tool call, wrote nothing
→ {"type":"result","status":"success", ...}
→ process exit code: 0
```

**Rules that follow:**

- Never branch on `result.status`. It is the literal string `"success"` in both emitters.
- Never branch on `bob run`'s process exit code. It was 0 on a capped, aborted run.
- Failure is detected **only** from `{"type":"error",...}` frames in the NDJSON stream.
- Any assumption about an external tool gets an **assertion with a loud message**. If Bob
  ships 2.0.6 mid-build and changes the stream, we want a crash with an explanation, not a
  silently wrong runway.

Generalised: **every external contract gets a probe test that would fail loudly if the
external thing changed.**

---

# 2. Golden Files Beat Opinions

AI-written code is confidently wrong in ways that read fine. The defence is committed
input/output pairs.

- `tests/golden/` holds real, committed samples: a chunk of NDJSON from a real run, a real
  `steps.json`, a real `checks.json`.
- Every module has at least one test that feeds it a golden input and asserts the exact
  output.
- **`render.py` must be byte-stable.** Same inputs in, byte-identical HTML out. There is a
  test that renders twice and compares. No timestamps, no random ids, no dict-order leaks.

Byte-stability is not fussiness. *"The same repository always produces the same city"* is a
documented trait of the project that won this event series.

---

# 3. Subprocesses Are argv Lists, Never Shell Strings

Every command — Bob runs and deterministic checks alike — is a Python list.

```python
subprocess.run(["python", "-c", "import sys; ..."], shell=False, ...)   # yes
subprocess.run(f"python -c \"{code}\"", shell=True)                      # never
```

**Why:** we are executing commands derived from a *third party's documentation*. Shell
interpolation of untrusted doc text is a command-injection hole, and on Windows the quoting
rules will silently corrupt a check and paint a false red. A false red is worse than a bug
here — it is a false accusation about someone else's project, on camera.

Every subprocess also gets an explicit `timeout=` and an explicit `cwd=`.

---

# 4. The Check Never Thinks

`check.py` may not import an LLM client, may not make a network call, and may not contain a
heuristic that "interprets" output.

A check is: run argv, read exit code. `0` is pass. Anything else is fail.

**This is the product.** The moment the check gets clever, it becomes another opinion and
the whole pitch collapses — we would be using a model to grade a model.

---

# 5. Disclose Every Limit, In The Repo, Before A Judge Finds It

From the FortyGuard post-mortem: our disclosure discipline was genuinely good and **no judge
ever saw it**, because it lived in a file nobody opened.

So limits go in `README.md`, above the fold:

- The step list for the demo target is **curated**, not blindly auto-split. Say so.
- We ran it on **one** repository. Say so.
- `n=1` per step. We are not claiming statistical significance, we are claiming a receipt.
- Prior art exists — `TNG/oh-my-agentic-coder`, `alphacrack/readme2demo` — and we name both
  and say precisely what they do not do.

**Naming the closest competitor first is what makes the rest credible.**

---

# 6. Tone: We Help, We Do Not Expose

We are about to publish an analysis of someone else's documentation and send them a pull
request.

| Say | Never say |
|---|---|
| "Three steps in this guide have drifted from the code" | "Their docs are broken" |
| "The fixture moved to `profiles_yml/`; the doc still points at the old path" | "They forgot to update their docs" |
| "Here is a patch" | "Here is what they got wrong" |

**The test:** would we be happy for a sqlfluff maintainer to read this sentence aloud?

sqlfluff's own CONTRIBUTING.md has a section headed **"AI-Assisted Contributions."** They
invited this. We honour that by sending a real, useful PR — not by scoring points.

---

# 7. Commit The Evidence, Not Just The Code

The repo must contain:

- `recordings/*.ndjson` — raw, verbatim, unedited Bob output
- `runs.json`, `checks.json`, `steps.json`
- Bob task-session screenshots (a hackathon deliverable)
- The exact `bob run` command lines used

**Committed transcripts are a documented winning trait** at this event: they turn
"Application of Technology" from a claim into something a judge can check.

Never hand-edit a recording. If a run is wrong, re-run it and say why in `MEMORY.md`.

---

# 8. Every Number On Screen Carries Its Unit And Its Basis

`0.48` is meaningless. `0.48 Bobcoins ($0.24)` is not.

- Bobcoins → USD uses **× 0.50**, IBM's published rate. Cite it in the README.
- Durations are wall-clock from Bob's own `duration_ms`. Not our stopwatch.
- The overruled rate is printed as **`N of M`**, never as a bare percentage.

A percentage with no denominator is how `n=3` gets sold as `2.3×`, which is what killed
candidate C2.

---

# 9. Secrets Never Reach Git

The hackathon brief is explicit: **if IBM security monitoring finds credentials in the repo,
the IBM Cloud account may be suspended immediately.**

- `bob.key`, `*.key`, `.env*` are gitignored. Already in place.
- `BOB_API_KEY` is read from the environment or from `bob.key`, and **never logged, never
  printed, never written into a JSON artifact.**
- Before every commit: `git diff --cached | grep -i "bob_"` must come back clean.
- Recordings get scanned for key-shaped strings before they are committed.

---

# 10. Ship Order Is Failure Order

Build so that every stopping point is still a submission.

If we stop after `check.py`, we have real numbers and a table.
If we stop after `render.py`, we have the runway.
The patch and the PR are the last mile, not the foundation.

**Never leave the tree in a state where nothing runs.** Commit working increments.

---

# 11. Attribution

Commits are authored **`FaisalRajpoot1 <144609495+FaisalRajpoot1@users.noreply.github.com>`**.

No AI tool is ever listed as an author, co-author or contributor, in any commit, PR or
document. Already configured in this repo.

This is separate from the IBM Bob Usage Statement, which is a required deliverable and
describes honestly and in detail how Bob was used to build the project. **Describing the
tool is required. Crediting it as an author is not done.**
