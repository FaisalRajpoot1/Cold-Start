# Bob Task 04 — fix `run.py`: Bob cannot be launched on Windows

Found by a live one-step probe, which is what probes are for. Cost 0 coins
because Bob never started.

## The prompt

```
A live probe of coldstart/run.py failed before Bob ever started:

  error_frame: "failed to launch bob: [WinError 2] The system cannot find the
               file specified"
  cost: 0.0000

THE CAUSE

run.py line 221 builds the command starting with the bare string "bob".

On Windows there is no bob.exe. The installer provides a shim named bob.CMD, and
CreateProcess cannot resolve a bare "bob" to it. Verified on this machine:

  shutil.which("bob")  ->  C:\nvm4w\nodejs\bob.CMD
  subprocess.run([shutil.which("bob"), "--version"])  ->  rc 0, prints "2.0.5"

Note that ruff's S607 rule ("starting a process with a partial executable path")
is exactly this defect. It fired on a `git` call elsewhere in the project today
and the same trap was in run.py.

FIX 1 — resolve the executable once, at startup

  - Add a module-level helper that returns shutil.which("bob").
  - Call it ONCE when the run begins, not per step.
  - If it returns None, exit immediately with a clear message: Bob Shell is not
    on PATH, install it with
    powershell -c "irm -Uri https://bob.ibm.com/download/bobshell.ps1 | iex"
    Do NOT start fourteen steps that are all going to fail the same way.
  - Use that resolved absolute path as argv[0]. Keep shell=False.
  - Record the resolved path in runs.json as a new top-level field "bob_executable"
    so the recording says which binary produced it. Add it to the schema in
    coldstart/schema.py as an OPTIONAL field, so existing artifacts still validate.

FIX 2 — --dry-run must prepare the workspaces

The spec said dry-run "prepares the workspaces and PRINTS the exact command line".
The current implementation only prints. That left the copy path untested until a
real run, which is the opposite of what a dry run is for.

Make --dry-run do the workspace preparation exactly as a real run does, and still
execute nothing and spend nothing.

TESTS — add to tests/test_run.py

  - @pytest.mark.contract: the command's argv[0] is an ABSOLUTE path, never the
    bare string "bob". Assert os.path.isabs(argv[0]).
  - when the executable cannot be resolved, the run exits with a clear message
    and NO step is attempted (use a tripwire on subprocess.run).
  - --dry-run creates the workspace directories and still never calls
    subprocess.run.
  - runs.json carries bob_executable, and a runs.json WITHOUT that field still
    validates (it is optional).

WHEN DONE
  py -m pytest -q       must pass
  py -m ruff check .    must be clean

Do not run bob for real. I will re-probe.
```

Screenshot → `docs/bob-sessions/04-run-fix.png`. Expected 1–2 Bobcoins.
