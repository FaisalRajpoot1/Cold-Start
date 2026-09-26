"""Rebuild runs.json from the committed recordings, without running Bob.

WHY THIS EXISTS

The recordings are the evidence; runs.json is only a parse of them. When the
parser is fixed -- and it has been fixed twice already, once for the `stats`
nesting and once for streamed message chunks -- the right response is to re-read
the recordings, not to spend Bobcoins repeating work we already have on tape.

This also proves something worth proving on camera: every figure on the receipt
is derived from committed raw transcripts, so a judge can delete runs.json,
re-run this, and get the same numbers back.

Costs nothing. Touches no network. Never modifies a recording.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from coldstart.run import _parse_ndjson, bob_version_from_binary
from coldstart.schema import RUNS_SCHEMA, dump_validated, load_validated


def reparse(steps_path: Path, recordings: Path, out_path: Path, previous: Path | None) -> dict:
    steps_doc = load_validated(steps_path)

    # Carry forward the run-level metadata from the previous runs.json if it is
    # there, so re-parsing does not silently invent a new recording date.
    meta = {"bob_version": "2.0.5", "max_cost": 1.2, "recorded_at": None, "bob_executable": None}
    if previous and previous.is_file():
        try:
            old = json.loads(previous.read_text(encoding="utf-8"))
            for k in list(meta):
                v = old.get(k)
                # "unknown" is an absence wearing a value. Do not carry it
                # forward, or the receipt keeps printing "IBM Bob unknown".
                if v is not None and v != "unknown":
                    meta[k] = v
        except (json.JSONDecodeError, OSError):
            pass
    if meta["bob_version"] in (None, "unknown"):
        meta["bob_version"] = bob_version_from_binary()
    if not meta["recorded_at"]:
        meta["recorded_at"] = datetime.now(tz=timezone.utc).isoformat()

    runs = []
    missing = []
    for step in steps_doc["steps"]:
        sid = step["id"]
        rec = recordings / f"step-{sid:02d}.ndjson"
        if not rec.is_file():
            missing.append(sid)
            continue

        parsed = _parse_ndjson(rec.read_bytes())
        runs.append(
            {
                "step_id": sid,
                "task_id": parsed["task_id"],
                "ndjson": rec.as_posix(),
                "session_costs": parsed["session_costs"],
                "duration_ms": parsed["duration_ms"],
                "tool_calls": parsed["tool_calls"],
                "bob_status": parsed["bob_status"],
                "error_frames": parsed["error_frames"],
                "tool_errors": parsed.get("tool_errors", []),
                "capped": parsed["capped"],
                "max_cost_applied": parsed.get("max_cost_applied", meta["max_cost"]),
                "bob_claim": "failed" if parsed["error_frames"] else "completed",
                "bob_final_message": parsed["bob_final_message"],
            }
        )

    doc = {
        "schema": RUNS_SCHEMA,
        "bob_version": meta["bob_version"],
        "recorded_at": meta["recorded_at"],
        "max_cost": meta["max_cost"],
        "runs": runs,
    }
    if meta["bob_executable"]:
        doc["bob_executable"] = meta["bob_executable"]

    dump_validated(doc, out_path)

    total = sum(r["session_costs"] for r in runs)
    print(f"re-parsed {len(runs)} recordings -> {out_path}")
    print(f"  {total:.4f} Bobcoins (${total * 0.5:.2f}) -- nothing spent, read from tape")
    if missing:
        print(f"  !! no recording for step(s): {missing}")
    return doc


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=Path, default=Path("steps.json"))
    p.add_argument("--recordings", type=Path, default=Path("recordings"))
    p.add_argument("--out", type=Path, default=Path("runs.json"))
    a = p.parse_args()
    reparse(a.steps, a.recordings, a.out, a.out)


if __name__ == "__main__":
    main()
