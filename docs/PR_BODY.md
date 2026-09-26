# docs: fix four stale references in CONTRIBUTING.md

The setup guide works well overall. We followed it end-to-end and got a working
development environment. Four references have drifted from the current state of
the tree; this patch corrects them.

## What changed and why

| Location in CONTRIBUTING.md | Current text | Should be |
|---|---|---|
| Grammar test example (§ "Working incrementally") | `test/core/parser/grammar_test.py` | `test/core/parser/grammar/grammar_anyof_test.py` — the file was split into a package; the AnyOf example belongs in `grammar_anyof_test.py` |
| dbt profiles fixture path | `…/dbt/profiles.yml` | `…/dbt/profiles_yml/profiles.yml` — the file moved down one level |
| dbt coverage tox invocation | `dbt019-py310` | `dbt180-py310` — `dbt019` no longer exists in `tox.ini`; `dbt180` is already recommended elsewhere in the guide as the default |
| Release script env var | `SQLFLUFF_GITHUB_TOKEN` | `GITHUB_TOKEN` — `util.py` reads `os.environ["GITHUB_TOKEN"]`; the old name raises `KeyError` immediately. `GITHUB_REPOSITORY_OWNER` is also required and was not mentioned; a contributor following the current text hits a second `KeyError` right after fixing the first |

## Notes

- No prose was reflowed or reworded beyond the four changed lines.
- The patch was verified with `git apply --check` against the pristine file at
  commit `c7401613`.
- This contribution was prepared with the help of an AI assistant (IBM Bob).
  We reviewed every suggested change against the live tree before including it,
  in line with the **AI-Assisted Contributions** section of this guide.
