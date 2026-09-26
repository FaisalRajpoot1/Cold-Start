# Cold Start — context for IBM Bob

You are working on **Cold Start**, a tool that makes IBM Bob actually *perform* a project's
onboarding document, one step at a time, then prints an itemised receipt showing what each
step cost and which ones cannot work.

Read this before writing any code. The detail is in `docs/`.

---

## The pipeline

Four modules. **Each is a pure function from files on disk to files on disk.** They never
import each other — they communicate only through JSON files.

```
CONTRIBUTING.md → split.py  → steps.json
steps.json      → run.py    → recordings/*.ndjson + runs.json   ← ONLY module with network
steps + repo    → check.py  → checks.json                       ← NO model, ever
all three       → render.py → web/index.html                    ← pure, no network
```

The contracts are frozen in `docs/ARCHITECTURE.md` and enforced by `coldstart/schema.py`.
**Do not change a contract without saying so explicitly** — four modules depend on each one.

---

## The five rules that matter most

### 1. Never trust a success signal you did not verify

**`bob run` ALWAYS reports `status:"success"`, even when it fails.** Verified two ways: both
result emitters in `bob.js` hardcode the literal, and a run capped at `--max-cost 0.02`
aborted after one tool call, wrote nothing it was asked to write, and still reported success
**with process exit code 0**.

So: **never branch on `result.status`, and never branch on the exit code of `bob run`.**
Failure is read *only* from `{"type":"error",...}` frames in the NDJSON stream.

### 2. Subprocesses are argv lists, never shell strings

```python
subprocess.run(["python", "-c", "..."], shell=False, timeout=..., cwd=...)   # yes
subprocess.run(f"python -c '{code}'", shell=True)                            # never
```

These commands come from a **third party's documentation**. Shell interpolation is an
injection hole, and Windows quoting will silently corrupt a check — which paints a false red,
which is a false accusation about someone else's project, on camera.

### 3. `check.py` never thinks

A check is: run argv, read the exit code. `0` is pass, anything else is fail. **No model, no
network, no heuristic, no "this output probably means it worked".**

This is the product. The moment the check gets clever, we are using a model to grade a model.

### 4. Validate before writing

Every artifact goes through `coldstart.schema.dump_validated()`. A rejected artifact must
never reach disk, or a later module reads it and produces a plausible wrong answer.

### 5. Output must be byte-stable

Same inputs in, byte-identical file out. No timestamps in rendered output, no random ids, no
dict-ordering leaks. There is a test for this.

---

## House style

- **Python 3.10+, standard library only.** No new runtime dependencies, ever. `json`,
  `subprocess`, `pathlib`, `shutil`, `argparse`, `concurrent.futures`, `hashlib`, `html`.
- Type hints on every public function. `from __future__ import annotations` at the top.
- `pathlib.Path`, never `os.path`.
- Docstrings explain **why**, not what. If a line exists because of a specific bug or a
  specific failure, say so in the comment.
- Every `subprocess.run` gets an explicit `timeout=` and an explicit `cwd=`.
- Errors name the offending path: `steps.json.steps[3].check.cmd: ...`, never "invalid input".

## Testing

- `pytest` — tests live in `tests/`, golden files in `tests/golden/`.
- Every module needs a golden-file test: committed input → asserted exact output.
- **No network in any test.** Ever.
- Mark tests that assert something about an *external* tool with `@pytest.mark.contract` —
  those are the ones that must fail loudly if Bob ships a new version mid-build.

Run `py -m pytest -q` and `py -m ruff check .` before saying a task is done. Both must be
clean.

## Never do these

- Never read or print `BOB_API_KEY`, and never write it into a JSON artifact or a log.
- Never commit anything matching `*.key` or `.env*`.
- Never hand-edit a file in `recordings/` — it is raw evidence.
- Never add a runtime dependency.
- Never make `render.py` touch the network.

---

## Design constraints for anything visual

Full spec in `docs/DESIGN.md`. The short version:

- It is a **receipt**: warm paper `#FBFAF7`, near-black ink `#14110F`, and exactly one
  accent — stamp red `#C1272D`.
- **Passing steps get no colour at all.** No green, no ticks, no status pills, no badges.
  Only failures are marked, the way a real receipt is marked.
- IBM Plex Mono for every figure, IBM Plex Sans for prose. `tabular-nums` on all figures.
- No gradients, no shadows, no icons, no charts, no dark mode.
- Inline CSS and inline SVG in one HTML file. No framework, no build step, no CDN except the
  Google Fonts link — and the page must still be correct with the network off.
