"""Export a machine-readable record of every IBM Bob session used to build this.

WHY THIS EXISTS

The hackathon requires task-session screenshots as evidence that Bob did the work.
Screenshots are fine for a human, but they cannot be diffed, counted or checked.
Bob keeps its task history in a local SQLite database, so we export the same facts
in a form a judge can actually verify.

It is also, incidentally, the only place the truth about a failed task is written
down -- see the `status` note below.

READ-ONLY, BUT NOT `immutable`

Opened with `mode=ro` only.

The first version also passed `immutable=1`, reasoning that it would be safest while
Bob is running. It is not safe -- it is WRONG. `immutable=1` tells SQLite the file
cannot change, so it skips the write-ahead log, and every recent session lives in the
WAL until a checkpoint. The tool cheerfully reported 0.8583 Bobcoins for a task that
had actually cost 3.6533.

A read-only tool that silently reports stale numbers is the exact failure this whole
project is about, so it is written down here rather than quietly corrected.

`mode=ro` alone reads the WAL correctly and still cannot write.

NOTHING SENSITIVE IS EXPORTED

Only task metadata: id, title, status, cost, timestamps, context size. Message
bodies are counted, never read. `BOB_API_KEY` appears nowhere in these tables and
nothing here is written to the repository except the fields listed in FIELDS.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".bob" / "db" / "bob.db"

# Exported verbatim. Deliberately excludes `first_message` beyond a short prefix
# and excludes message bodies entirely.
FIELDS = ["id", "status", "task_type", "created_at", "updated_at"]


def _iso(ms: int | None) -> str | None:
    """Bob stores epoch milliseconds. Render UTC ISO-8601 so a reader can check it."""
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def export(db_path: Path = DEFAULT_DB, out_path: Path | None = None) -> dict:
    """Read Bob's task history and return a JSON-serialisable summary."""
    # mode=ro only. NEVER add immutable=1 -- see the module docstring: it skips the
    # write-ahead log and silently returns stale costs.
    uri = f"file:{db_path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row

    counts = {
        r["task_id"]: r["n"]
        for r in con.execute("select task_id, count(*) as n from messages group by task_id")
    }

    sessions = []
    for row in con.execute("select * from tasks order by created_at"):
        raw = dict(row)

        cost = 0.0
        context_tokens = 0
        try:
            parsed = json.loads(raw.get("costs") or "{}")
            cost = float(parsed.get("cost") or 0.0)
            context_tokens = int(parsed.get("contextTokens") or 0)
        except (ValueError, TypeError):
            pass

        title = (raw.get("title") or raw.get("first_message") or "").strip()

        sessions.append(
            {
                **{k: raw.get(k) for k in FIELDS},
                "created_utc": _iso(raw.get("created_at")),
                "prompt_prefix": title[:120],
                "bobcoins": round(cost, 6),
                "usd": round(cost * 0.50, 4),  # IBM published rate, 1 Bobcoin = $0.50
                "context_tokens": context_tokens,
                "messages": counts.get(raw["id"], 0),
            }
        )

    con.close()

    total = round(sum(s["bobcoins"] for s in sessions), 6)
    return {
        "schema": "coldstart.sessions/1",
        "source": "IBM Bob local task database (read-only)",
        "bobcoin_usd_rate": 0.50,
        "session_count": len(sessions),
        "total_bobcoins": total,
        "total_usd": round(total * 0.50, 4),
        "sessions": sessions,
        "note": (
            "A task capped by --max-cost is recorded here with status 'error', while the "
            "headless stream-json 'result' event for that same task reports "
            "status 'success'. Bob knows the task failed; the headless result event does "
            "not say so. This is why Cold Start reads failure from the stream's 'error' "
            "frames and from an independent deterministic check, never from result.status."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=Path("docs/bob-sessions/sessions.json"))
    args = parser.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"no Bob database at {args.db}")

    doc = export(args.db, args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"{doc['session_count']} Bob sessions")
    print(f"{doc['total_bobcoins']:.4f} Bobcoins  (${doc['total_usd']:.2f})")
    for s in doc["sessions"]:
        if s["bobcoins"] > 0:
            print(
                f"  {s['created_utc']}  {s['status']:8} "
                f"{s['bobcoins']:8.4f}  {s['messages']:3} msgs  {s['prompt_prefix'][:56]}"
            )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
