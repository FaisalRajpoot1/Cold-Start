"""Build steps.json for the sqlfluff CONTRIBUTING.md run.

CURATED, NOT AUTO-SPLIT, AND SAID SO OUT LOUD

`split.py` was cut (see docs/PHASES.md). Every step below was read out of
sqlfluff's CONTRIBUTING.md by hand and every check was verified against the
clone at target/_pristine before being written here.

WHY EACH CHECK IS SHAPED THE WAY IT IS

A check must be true or false for a reason a sqlfluff maintainer would accept.
Three near-misses while writing this file, all caught before they shipped:

  1. `grep dbt180 tox.ini` reports NOT FOUND, because the envlist writes it as
     the brace expansion `dbt{170,180,190,1100}`. A literal grep would have
     painted a false red on a step that works perfectly.
  2. The same for `py310`, inside `py{310,311,312,313,314}`.
  3. `pre-commit` and `cov-report-dbt` are absent from envlist entirely but
     exist as `[testenv:*]` sections, which `tox -e` resolves happily.

A false red is a false accusation about someone else's project, published on
camera. So the tox checks below test the string tox actually resolves, and the
only tox env marked red is `dbt019`, which appears nowhere in the file in any
form.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from coldstart.schema import STEPS_SCHEMA, dump_validated

PRISTINE = Path("target/_pristine")
DOC = PRISTINE / "CONTRIBUTING.md"


def py(expr: str) -> list[str]:
    """A check as an argv list. Never a shell string -- see AGENTS.md rule 2."""
    return ["python", "-c", f"import sys,pathlib,re;{expr}"]


def path_exists(rel: str) -> list[str]:
    return py(f"sys.exit(0 if pathlib.Path({rel!r}).exists() else 1)")


def text_contains(rel: str, needle: str) -> list[str]:
    return py(
        f"t=pathlib.Path({rel!r}).read_text(encoding='utf-8',errors='replace');"
        f"sys.exit(0 if {needle!r} in t else 1)"
    )


# (title, kind, quote, bob_prompt, check_cmd, describes, expected)
STEPS = [
    (
        "Use tox to set up the development environment",
        "prose",
        "The simplest way to set up a development environment is to use [`tox`]"
        "(https://tox.wiki/en/latest/installation.html).",
        "The contributing guide says the simplest way to set up a development "
        "environment for this project is to use tox. Locate the tox configuration "
        "in this repository that this instruction refers to, and confirm it is present.",
        path_exists("tox.ini"),
        "the tox configuration the instruction depends on",
        "green",
    ),
    (
        "Confirm the minimum supported Python version",
        "prose",
        "**IMPORTANT:** Python 3.10 is the minimum version we support. Feel free "
        "to test on anything between `python3.10` and `python3.14`.",
        "The guide states a minimum supported Python version. Determine what it is, "
        "then confirm the Python available in this environment satisfies it.",
        py("sys.exit(0 if sys.version_info >= (3,10) else 1)"),
        "the interpreter meets the documented minimum",
        "green",
    ),
    (
        "Build the virtual environment with the dbt180 tox env",
        "command",
        "tox -e dbt180 --devenv .venv",
        "The guide tells a new contributor to build and activate a virtual environment "
        "using the tox environment named dbt180. Confirm that tox environment is "
        "actually available in this repository.",
        # dbt180 lives inside the brace expansion dbt{170,180,190,1100}.
        # Testing for the literal 'dbt180' would be a FALSE RED.
        text_contains("tox.ini", "dbt{170,180,190,1100}"),
        "the dbt180 tox environment, via its brace expansion in envlist",
        "green",
    ),
    (
        "Install the example plugin in editable mode",
        "command",
        "This virtual environment will already have the package installed in editable "
        "mode for you, as well as `requirements_dev.txt` and "
        "`plugins/sqlfluff-plugin-example`.",
        "The guide says the development environment installs an example plugin from a "
        "path inside this repository. Find that plugin directory and confirm it exists.",
        path_exists("plugins/sqlfluff-plugin-example"),
        "the example plugin the environment installs",
        "green",
    ),
    (
        "Run a targeted tox environment",
        "command",
        "tox -e generate-fixture-yml,py310,linting,mypy",
        "The guide gives a targeted tox invocation for day-to-day work naming four "
        "environments. Confirm the linting environment among them is defined in this "
        "repository.",
        text_contains("tox.ini", "[testenv:linting]"),
        "the linting tox environment",
        "green",
    ),
    (
        "Regenerate the parse fixtures",
        "command",
        "`python test/generate_parse_fixture_yml.py -d mysql` will do the same.",
        "For dialect work the guide says you can regenerate parse fixtures by running a "
        "script directly, and gives its path. Confirm that script is present.",
        path_exists("test/generate_parse_fixture_yml.py"),
        "the fixture generation script named in the guide",
        "green",
    ),
    (
        "Resync the Rust dialects",
        "command",
        "with sqlfluff installed in a virtual environment, run `utils/rustify.py build` "
        "to resync the languages.",
        "The guide says that after changing a dialect you must resync the Rust dialects "
        "by running a script at a given path. Confirm that script exists.",
        path_exists("utils/rustify.py"),
        "the rustify script named in the guide",
        "green",
    ),
    (
        "Run the grammar tests for an AnyOf() change",
        "command",
        "1. If your change is to the `AnyOf()` grammar, first running "
        "`tox -e py310 -- test/core/parser/grammar_test.py` would be wise.",
        "The guide says that if your change is to the AnyOf() grammar, you should first "
        "run the grammar test file it names. Locate that test file and run it.",
        path_exists("test/core/parser/grammar_test.py"),
        "the grammar test file the guide names",
        "red",  # VERIFIED: 404. Split into the package test/core/parser/grammar/
    ),
    (
        "Run the yaml rule test cases",
        "command",
        "`pytest test/rules/yaml_test_cases_test.py -k AL01`",
        "When developing an isolated rule, the guide says to run the yaml test cases "
        "file it names, filtered to one rule. Confirm that test file is present.",
        path_exists("test/rules/yaml_test_cases_test.py"),
        "the yaml rule test file",
        "green",
    ),
    (
        "Find the dbt connection parameters",
        "prose",
        "The dbt templater tests require a locally running Postgres instance. See the "
        "required connection parameters in "
        "`plugins/sqlfluff-templater-dbt/test/fixtures/dbt/profiles.yml`.",
        "The guide says the dbt templater tests need a local Postgres instance and that "
        "the connection parameters are in a profiles.yml at a specific path. Open that "
        "file and report the connection parameters.",
        path_exists("plugins/sqlfluff-templater-dbt/test/fixtures/dbt/profiles.yml"),
        "the profiles.yml at the documented path",
        "red",  # VERIFIED: 404. Moved down one level into profiles_yml/
    ),
    (
        "Run the dbt templater tests",
        "command",
        "tox -e cov-init,dbt019-py310,cov-report-dbt -- plugins/sqlfluff-templater-dbt",
        "The guide gives an explicit tox command for running the dbt-related tests. "
        "Confirm every tox environment it names is available in this repository.",
        text_contains("tox.ini", "dbt019"),
        "the dbt019 tox environment the command requires",
        "red",  # VERIFIED: 'dbt019' appears nowhere in tox.ini, in any form.
    ),
    (
        "Install the pre-commit hooks",
        "command",
        "tox -e pre-commit -- install",
        "The guide offers pre-commit hooks installed through a named tox environment. "
        "Confirm that environment is defined.",
        # Absent from envlist but present as a [testenv:*] section, which tox -e resolves.
        text_contains("tox.ini", "[testenv:pre-commit]"),
        "the pre-commit tox environment",
        "green",
    ),
    (
        "Read the documentation website guide",
        "prose",
        "See the [Documentation Website README.md](./docs/README.md) file for more "
        "information on how to build and test this.",
        "The guide links to a separate README for building and testing the documentation "
        "website. Open it and confirm it is there.",
        path_exists("docs/README.md"),
        "the documentation README the guide links to",
        "green",
    ),
    (
        "Store the release token for the release script",
        "prose",
        "Once generated, store it in your env (zshrc, etc) as `SQLFLUFF_GITHUB_TOKEN`.",
        "The release checklist says to store a GitHub personal access token in an "
        "environment variable with a specific name, then run the release script. "
        "Confirm the release script actually reads a variable with that name.",
        text_contains("util.py", "SQLFLUFF_GITHUB_TOKEN"),
        "the release script reads the variable the guide names",
        "red",  # VERIFIED: util.py reads GITHUB_TOKEN and GITHUB_REPOSITORY_OWNER.
    ),
]


def main() -> None:
    if not DOC.is_file():
        raise SystemExit(f"missing {DOC} -- clone the target first")

    doc_text = DOC.read_text(encoding="utf-8")
    doc_lines = doc_text.splitlines()
    sha = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

    # Whitespace-collapsed document, plus the offset each line starts at in it,
    # so a quote that wraps across lines can still be located and reported with
    # a line number.
    flat_parts, line_offsets, cursor = [], [], 0
    for line in doc_lines:
        line_offsets.append(cursor)
        collapsed = " ".join(line.split())
        flat_parts.append(collapsed)
        cursor += len(collapsed) + 1
    line_offsets.append(cursor)
    flat = " ".join(flat_parts)
    commit = subprocess.run(  # noqa: S603
        ["git", "-C", str(PRISTINE), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()

    steps = []
    missing_quotes = []
    for i, (title, kind, quote, prompt, cmd, describes, expected) in enumerate(STEPS, 1):
        # Every quote must genuinely appear in the document. A quote we cannot
        # locate is a fabrication, and CLAUDE.md forbids those absolutely.
        #
        # Matched against the WHOLE document with whitespace collapsed, not line
        # by line. Caught by this guard on the first run: step 14's sentence wraps
        # across two lines in CONTRIBUTING.md, so per-line matching reported a real
        # quote as missing. The guard was right to refuse; the matcher was wrong.
        needle = " ".join(quote.split())
        pos = flat.find(needle)
        if pos < 0:
            missing_quotes.append((i, needle[:60]))
            hit = 0
        else:
            # Map the character offset back to a 1-based line number.
            hit = next(n for n, off in enumerate(line_offsets, 1) if off > pos) - 1

        steps.append(
            {
                "id": i,
                "title": title,
                "doc_lines": [hit, hit],
                "quote": quote,
                "kind": kind,
                "bob_prompt": prompt,
                "check": {"cmd": cmd, "describes": describes},
                "expected": expected,
            }
        )

    if missing_quotes:
        for i, q in missing_quotes:
            print(f"  !! step {i}: quote not found in the document -- {q}")
        raise SystemExit("refusing to write steps.json with an unlocatable quote")

    doc = {
        "schema": STEPS_SCHEMA,
        "source_repo": "sqlfluff/sqlfluff",
        "source_commit": commit,
        "doc_path": "CONTRIBUTING.md",
        "doc_sha256": sha,
        "steps": steps,
    }
    out = dump_validated(doc, "steps.json")

    reds = [s for s in steps if s["expected"] == "red"]
    print(f"wrote {out}: {len(steps)} steps, {len(reds)} expected red")
    print(f"  repo   sqlfluff/sqlfluff @ {commit[:8]}")
    print(f"  doc    CONTRIBUTING.md  sha256 {sha[:16]}...  {len(doc_lines)} lines")
    for s in steps:
        mark = "RED " if s["expected"] == "red" else "    "
        print(f"  {mark} {s['id']:2}  L{s['doc_lines'][0]:<4} {s['title']}")
    print("\nNOTE: `expected` is a prediction only. Nothing downstream reads it.")
    print("      The run decides the colours, and it is free to prove us wrong.")


if __name__ == "__main__":
    main()
