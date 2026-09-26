"""Replay a committed recording to the terminal, at speed, for the demo video.

Nothing is simulated. Every line is read from the NDJSON that Bob actually
produced; only the pacing is ours, so a 42-second session can fill a 45-second
beat without re-running anything or spending a Bobcoin.

    py video/replay.py recordings/step-11.ndjson
    py video/replay.py recordings/step-11.ndjson --speed 1.5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

D, B, R, G, Y = "\033[2m", "\033[1m", "\033[31m", "\033[32m", "\033[33m"
X = "\033[0m"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("recording", type=Path)
    ap.add_argument("--speed", type=float, default=1.0, help="higher is faster")
    a = ap.parse_args()

    lines = [ln for ln in a.recording.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    events = []
    for ln in lines:
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue

    print(rf"{D}$ bob run --format stream-json --max-cost 1.2 --max-turns 25 \{X}")
    print(f"{D}      --trust --workspace target/ws-11{X}\n")
    time.sleep(1.0 / a.speed)

    for e in events:
        kind = e.get("type")
        if kind == "message" and e.get("role") == "user":
            print(f"{B}> {str(e.get('content',''))[:150]}{X}\n")
            time.sleep(1.2 / a.speed)
        elif kind == "tool_use":
            p = json.dumps(e.get("parameters", {}))[:90]
            print(f"  {Y}{e.get('tool_name','tool'):<16}{X}{D}{p}{X}")
            time.sleep(0.45 / a.speed)
        elif kind == "tool_result":
            out = " ".join(str(e.get("output", "")).split())[:100]
            colour = R if e.get("status") == "error" else G
            print(f"  {colour}{'->':<16}{X}{D}{out}{X}")
            time.sleep(0.30 / a.speed)
        elif kind == "message" and e.get("role") == "assistant":
            sys.stdout.write(str(e.get("content", "")))
            sys.stdout.flush()
            time.sleep(0.035 / a.speed)
        elif kind == "error":
            print(f"\n\n  {R}{B}error{X}  {R}{e.get('message','')}{X}")
            time.sleep(1.6 / a.speed)
        elif kind == "result":
            s = e.get("stats", {})
            print(f"\n\n{D}{'-'*66}{X}")
            print(f"  status        {G}{e.get('status')}{X}   {D}<- always 'success'{X}")
            print(f"  session_costs {B}{s.get('session_costs')}{X}")
            print(f"  duration_ms   {s.get('duration_ms')}")
            print(f"  tool_calls    {s.get('tool_calls')}")
            print(f"{D}{'-'*66}{X}")
            time.sleep(2.5 / a.speed)


if __name__ == "__main__":
    main()
