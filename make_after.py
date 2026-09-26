"""Prepare the AFTER run: apply the patch, then rebuild steps against it.

WHY A FULL SECOND RUN RATHER THAN SPLICING

Only four steps change, so it is tempting to re-record those four and keep the
other ten recordings. We run all fourteen again instead.

A spliced receipt would be two runs presented as one, and the honest caption for
it is long. A second complete run of the corrected guide is one sentence: this
is what following the patched document costs. At roughly three Bobcoins for the
full pass that is cheap, and the evidence is unambiguous.

WHAT CHANGES

Four steps get a new quote and a new check, matching the corrected instruction.
The other ten are identical, which is the point -- the same harness, the same
prompts, a different document.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from coldstart.schema import STEPS_SCHEMA, dump_validated, load_validated

PRISTINE = Path("target/_pristine")
PATCHED = Path("target/_patched")
PATCH = Path("docs-fix.patch")


def py(expr: str) -> list[str]:
    return ["python", "-c", f"import sys,pathlib,re;{expr}"]


def path_exists(rel: str) -> list[str]:
    return py(f"sys.exit(0 if pathlib.Path({rel!r}).exists() else 1)")


def text_contains(rel: str, needle: str) -> list[str]:
    return py(
        f"t=pathlib.Path({rel!r}).read_text(encoding='utf-8',errors='replace');"
        f"sys.exit(0 if {needle!r} in t else 1)"
    )


# step id -> (new quote fragment to locate, new bob_prompt, new check, describes)
CORRECTED = {
    8: (
        "tox -e py310 -- test/core/parser/grammar/grammar_anyof_test.py",
        "The guide says that if your change is to the AnyOf() grammar, you should first "
        "run the grammar test file it names. Locate that test file and run it.",
        path_exists("test/core/parser/grammar/grammar_anyof_test.py"),
        "test/core/parser/grammar/grammar_anyof_test.py",
    ),
    10: (
        "plugins/sqlfluff-templater-dbt/test/fixtures/dbt/profiles_yml/profiles.yml",
        "The guide says the dbt templater tests need a local Postgres instance and that "
        "the connection parameters are in a profiles.yml at a specific path. Open that "
        "file and report the connection parameters.",
        path_exists(
            "plugins/sqlfluff-templater-dbt/test/fixtures/dbt/profiles_yml/profiles.yml"
        ),
        "plugins/sqlfluff-templater-dbt/test/fixtures/dbt/profiles_yml/profiles.yml",
    ),
    11: (
        "dbt180-py310",
        "The guide gives an explicit tox command for running the dbt-related tests. "
        "Confirm every tox environment it names is available in this repository.",
        text_contains("tox.ini", "dbt{170,180,190,1100}"),
        "a tox environment named dbt180, in tox.ini",
    ),
    14: (
        "GITHUB_TOKEN",
        "The release checklist says to store a GitHub personal access token in an "
        "environment variable with a specific name, then run the release script. "
        "Confirm the release script actually reads a variable with that name.",
        text_contains("util.py", "GITHUB_TOKEN"),
        "GITHUB_TOKEN, anywhere in util.py",
    ),
}


def apply_patch() -> str:
    if not PATCH.is_file():
        raise SystemExit(f"{PATCH} does not exist yet -- Bob is still writing it")

    if PATCHED.exists():
        shutil.rmtree(PATCHED)
    shutil.copytree(PRISTINE, PATCHED)

    git = shutil.which("git")
    if not git:
        raise SystemExit("git is not on PATH")

    check = subprocess.run(  # noqa: S603
        [git, "apply", "--check", "-v", str(PATCH.resolve())],
        cwd=PATCHED, capture_output=True, text=True, timeout=120,
    )
    if check.returncode != 0:
        raise SystemExit(f"patch does not apply:\n{check.stderr.strip()}")

    subprocess.run(  # noqa: S603
        [git, "apply", str(PATCH.resolve())],
        cwd=PATCHED, capture_output=True, text=True, timeout=120, check=True,
    )
    return (PATCHED / "CONTRIBUTING.md").read_text(encoding="utf-8")


def main() -> None:
    doc_text = apply_patch()
    lines = doc_text.splitlines()
    flat = " ".join(" ".join(line.split()) for line in lines)

    before = load_validated("steps.json")
    steps = []
    for step in before["steps"]:
        s = dict(step)
        if s["id"] in CORRECTED:
            frag, prompt, cmd, describes = CORRECTED[s["id"]]
            if frag not in flat:
                raise SystemExit(
                    f"step {s['id']}: the corrected text {frag!r} is not in the patched "
                    "document. The patch did not make the change it was meant to."
                )
            hit = next(
                (n for n, ln in enumerate(lines, 1) if frag in " ".join(ln.split())), 0
            )
            s["quote"] = frag
            s["doc_lines"] = [hit, hit]
            s["bob_prompt"] = prompt
            s["check"] = {"cmd": cmd, "describes": describes}
            s["expected"] = "green"
        steps.append(s)

    git = shutil.which("git")
    commit = subprocess.run(  # noqa: S603
        [git, "-C", str(PRISTINE), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout.strip()

    doc = {
        "schema": STEPS_SCHEMA,
        "source_repo": "sqlfluff/sqlfluff",
        "source_commit": commit,
        "doc_path": "CONTRIBUTING.md (patched)",
        "doc_sha256": hashlib.sha256(doc_text.encode("utf-8")).hexdigest(),
        "steps": steps,
    }
    dump_validated(doc, "steps.after.json")

    # Prove the corrected checks pass against the patched tree, before spending
    # a single coin on the second run.
    wrong = 0
    for s in steps:
        r = subprocess.run(  # noqa: S603
            s["check"]["cmd"], cwd=PATCHED, capture_output=True, timeout=60
        )
        actual = "green" if r.returncode == 0 else "red"
        if actual != s["expected"]:
            wrong += 1
            print(f"  !! step {s['id']:2} expected {s['expected']} got {actual}")

    print(f"patched tree ready at {PATCHED}")
    print(f"wrote steps.after.json: {len(steps)} steps, {len(CORRECTED)} corrected")
    print(f"dry check against the patched tree: {wrong} disagreement(s)")
    if wrong == 0:
        print("\nAll 14 checks now pass against the patched document. Safe to re-record.")


if __name__ == "__main__":
    main()
