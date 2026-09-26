"""render.py — turn the recordings into a receipt.

A PURE FUNCTION, AND THAT IS THE POINT

Reads three committed JSON files, writes one HTML file. No network, no API key,
no model, no clock. Same inputs in, byte-identical HTML out.

That is not tidiness. The demo replays committed recordings, so the video cannot
break because a service is down or a model answered differently this morning. The
confirmed winning trait at this event series was "the same repository always
produces the same city". This is that property, enforced by a test.

THE DERIVED VERDICT

Neither runs.json nor checks.json holds the colour. It is computed here:

    Bob claims        check says     tile
    completed         pass           plain        it worked
    completed         fail           OVERRULED    the save: Bob was wrong
    failed/capped     fail           red          honestly broken
    failed/capped     pass           amber        Bob gave up, the state is fine

`expected` from steps.json is displayed but NEVER used to decide a colour. It is
our prediction, kept visible so the run can prove us wrong in public.

DESIGN

docs/DESIGN.md is the spec. Warm paper, near-black ink, one accent — stamp red —
and passing steps get no colour at all, because on a real receipt only the
problems are marked.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from coldstart.schema import load_validated

BOBCOIN_USD = 0.50  # IBM published rate

PAPER = "#FBFAF7"
PAPER_EDGE = "#F2F0EA"
INK = "#14110F"
INK_MUTED = "#8A8078"
RULE = "#E0DCD5"
STAMP = "#C1272D"
STAMP_WASH = "rgba(193,39,45,0.07)"


def _money(coins: float) -> str:
    return f"${coins * BOBCOIN_USD:,.2f}"


def _clock(ms: int) -> str:
    """Render a duration as m:ss. Receipts do not show milliseconds."""
    total = round(ms / 1000)
    return f"{total // 60}:{total % 60:02d}"


def verdict_for(claim: str, check_verdict: str) -> str:
    """The derived tile state. The only place a colour is decided."""
    if claim == "completed" and check_verdict == "pass":
        return "ok"
    if claim == "completed" and check_verdict == "fail":
        return "overruled"
    if check_verdict == "pass":
        return "amber"
    return "broken"


def build(steps_doc: dict, runs_doc: dict, checks_doc: dict) -> dict:
    """Join the three artifacts into the rows the template renders."""
    runs = {r["step_id"]: r for r in runs_doc.get("runs", [])}
    checks = {c["step_id"]: c for c in checks_doc.get("checks", [])}

    rows, total_coins, total_ms, wasted_coins, wasted_ms, overruled = [], 0.0, 0, 0.0, 0, 0

    for step in steps_doc["steps"]:
        sid = step["id"]
        run = runs.get(sid, {})
        chk = checks.get(sid, {})

        coins = float(run.get("session_costs") or 0.0)
        ms = int(run.get("duration_ms") or 0)
        claim = run.get("bob_claim", "unknown")
        cverdict = chk.get("verdict", "fail")
        state = verdict_for(claim, cverdict)

        total_coins += coins
        total_ms += ms
        if state in ("broken", "overruled"):
            wasted_coins += coins
            wasted_ms += ms
        if state == "overruled":
            overruled += 1

        reason = (chk.get("stderr_tail") or "").strip().splitlines()
        rows.append(
            {
                "id": sid,
                "title": step["title"],
                "quote": step["quote"],
                "line": step["doc_lines"][0],
                "kind": step["kind"],
                "expected": step["expected"],
                "state": state,
                "claim": claim,
                "check_cmd": " ".join(chk.get("cmd", step["check"]["cmd"])),
                "describes": step["check"]["describes"],
                "reason": reason[-1][:200] if reason else "",
                "coins": coins,
                "ms": ms,
                "tool_calls": int(run.get("tool_calls") or 0),
                "ndjson": run.get("ndjson", ""),
            }
        )

    claimed_ok = sum(1 for r in rows if r["claim"] == "completed")

    return {
        "repo": steps_doc["source_repo"],
        "commit": steps_doc["source_commit"],
        "doc_path": steps_doc["doc_path"],
        "rows": rows,
        "total_coins": total_coins,
        "total_ms": total_ms,
        "wasted_coins": wasted_coins,
        "wasted_ms": wasted_ms,
        "broken": sum(1 for r in rows if r["state"] in ("broken", "overruled")),
        "overruled": overruled,
        "claimed_ok": claimed_ok,
        "bob_version": runs_doc.get("bob_version", "2.0.5"),
    }


CSS = f"""
:root {{
  --paper:{PAPER}; --paper-edge:{PAPER_EDGE}; --ink:{INK}; --muted:{INK_MUTED};
  --rule:{RULE}; --stamp:{STAMP}; --wash:{STAMP_WASH};
}}
*{{box-sizing:border-box}}
body{{
  margin:0; background:var(--paper-edge); color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.45;
  -webkit-font-smoothing:antialiased;
}}
.sheet{{
  max-width:720px; margin:0 auto; background:var(--paper);
  padding:0 40px 44px;
}}
/* The perforated edge. Two gradients, no image. */
.perf{{
  height:14px; max-width:720px; margin:0 auto; background:var(--paper);
  --z:linear-gradient(45deg,transparent 33.33%,var(--paper) 33.33%,var(--paper) 66.66%,transparent 66.66%),
      linear-gradient(-45deg,transparent 33.33%,var(--paper) 33.33%,var(--paper) 66.66%,transparent 66.66%);
}}
.perf.top{{background:var(--paper-edge);background-image:var(--z);background-size:14px 28px;background-position:0 -14px}}
.perf.bot{{background:var(--paper-edge);background-image:var(--z);background-size:14px 28px;background-position:0 0}}
h1{{
  font-family:"IBM Plex Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;
  font-size:15px; font-weight:600; letter-spacing:.22em; text-transform:uppercase;
  margin:36px 0 2px;
}}
.sub{{font-size:13px;color:var(--muted);margin:0 0 2px}}
.meta{{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  font-size:11.5px; color:var(--muted); margin:14px 0 0; letter-spacing:.01em;
}}
hr{{border:0;border-top:1px solid var(--rule);margin:22px 0}}
hr.dot{{border-top:1px dashed var(--rule)}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}
td{{padding:7px 0;vertical-align:baseline}}
.n{{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  font-size:12px;color:var(--muted);width:30px;
}}
.what{{padding-right:14px}}
.num{{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  text-align:right;white-space:nowrap;font-size:13.5px;
  font-variant-numeric:tabular-nums;
}}
.t{{width:58px}} .c{{width:66px}}
tr.bad td{{background:var(--wash)}}
tr.bad .what strong{{text-decoration:line-through;text-decoration-thickness:1.5px}}
tr.bad .n,tr.bad .num{{color:var(--stamp)}}
.why{{
  font-size:12.5px;color:var(--muted);padding:0 0 10px 30px;
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}}
tr.bad + tr.why-row .why{{color:var(--stamp)}}
.flag{{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  font-size:10.5px;letter-spacing:.14em;color:var(--stamp);
  border:1px solid var(--stamp);padding:1px 5px;margin-left:8px;white-space:nowrap;
}}
.totals td{{padding:5px 0;font-size:13.5px}}
.totals .lbl{{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  letter-spacing:.14em;font-size:11.5px;text-transform:uppercase;
}}
.hero{{margin:26px 0 4px}}
.hero .fig{{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  font-size:64px;line-height:1;font-weight:600;color:var(--stamp);
  font-variant-numeric:tabular-nums;letter-spacing:-.02em;
}}
.hero .cap{{font-size:14px;color:var(--ink);margin-top:6px}}
.stamp{{
  display:inline-block;margin:26px 0 6px;padding:12px 20px;
  border:3px double var(--stamp);color:var(--stamp);
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  font-size:13px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  transform:rotate(-4deg);opacity:.9;line-height:1.5;
  animation:land .18s ease-out;
}}
@keyframes land{{from{{opacity:0;transform:rotate(-4deg) scale(1.06)}}to{{opacity:.9;transform:rotate(-4deg) scale(1)}}}}
@media (prefers-reduced-motion:reduce){{.stamp{{animation:none}}}}
.foot{{
  font-size:11.5px;color:var(--muted);margin-top:30px;
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;line-height:1.7;
}}
@media (max-width:640px){{
  .sheet{{padding:0 16px 32px}}
  .hero .fig{{font-size:46px}}
  .t{{width:48px}} .c{{width:58px}}
}}
@media print{{body{{background:var(--paper)}} .stamp{{animation:none}}}}
"""


def render(data: dict) -> str:
    e = html.escape
    out: list[str] = []
    w = out.append

    w("<!doctype html>")
    w('<html lang="en"><head><meta charset="utf-8">')
    w('<meta name="viewport" content="width=device-width,initial-scale=1">')
    w(f"<title>Cold Start — {e(data['repo'])}</title>")
    # Fonts are a progressive enhancement. The page must be correct offline,
    # so every rule carries a full local fallback stack.
    w('<link rel="preconnect" href="https://fonts.googleapis.com">')
    w('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    w(
        '<link href="https://fonts.googleapis.com/css2?'
        "family=IBM+Plex+Mono:wght@400;500;600&"
        'family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">'
    )
    w(f"<style>{CSS}</style></head><body>")
    w('<div class="perf top"></div><div class="sheet">')

    w("<h1>Cold Start</h1>")
    w(f"<p class=\"sub\">Itemised cost of following {e(data['doc_path'])}</p>")
    w(
        f"<p class=\"meta\">{e(data['repo'])} @ {e(data['commit'][:8])}<br>"
        f"{len(data['rows'])} steps &middot; IBM Bob {e(data['bob_version'])} &middot; "
        f"recorded headless, replayed from committed transcripts</p>"
    )
    w("<hr>")

    w("<table>")
    for r in data["rows"]:
        bad = r["state"] in ("broken", "overruled")
        w(f'<tr class="{"bad" if bad else ""}">')
        w(f'<td class="n">{r["id"]:02d}</td>')
        flag = '<span class="flag">OVERRULED</span>' if r["state"] == "overruled" else ""
        w(f'<td class="what"><strong>{e(r["title"])}</strong>{flag}</td>')
        w(f'<td class="num t">{_clock(r["ms"])}</td>')
        w(f'<td class="num c">{_money(r["coins"])}</td>')
        w("</tr>")
        if bad and r["reason"]:
            w('<tr class="why-row"><td></td><td colspan="3" class="why">')
            w(f"&#9492; {e(r['reason'])}")
            w("</td></tr>")
    w("</table>")

    w('<hr class="dot">')
    w('<table class="totals">')
    w(
        f'<tr><td class="lbl">Total</td><td class="num t">{_clock(data["total_ms"])}</td>'
        f'<td class="num c">{_money(data["total_coins"])}</td></tr>'
    )
    w(
        f'<tr><td class="lbl">Wasted</td><td class="num t">{_clock(data["wasted_ms"])}</td>'
        f'<td class="num c">{_money(data["wasted_coins"])}</td></tr>'
    )
    w("</table>")

    w('<div class="hero">')
    w(f'<div class="fig">{_money(data["wasted_coins"])}</div>')
    w(
        f'<div class="cap">wasted per new hire, on {data["broken"]} '
        f'step{"s" if data["broken"] != 1 else ""} that cannot work</div>'
    )
    w("</div>")

    if data["overruled"]:
        w(
            f'<div class="stamp">The check overruled Bob<br>on {data["overruled"]} '
            f'of {data["claimed_ok"]} claimed successes</div>'
        )

    w("<hr>")
    w('<p class="foot">')
    w("Every figure read from Bob&#39;s own headless result event. ")
    w("Nothing is estimated.<br>")
    w(f"1 Bobcoin = ${BOBCOIN_USD:.2f}, IBM published rate. ")
    w("Raw transcripts committed under recordings/.<br>")
    w("Steps that worked are unmarked, as on any receipt. Only problems are marked.")
    w("</p>")

    w('</div><div class="perf bot"></div>')
    w("</body></html>")
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Render the Cold Start receipt.")
    p.add_argument("--steps", default="steps.json")
    p.add_argument("--runs", default="runs.json")
    p.add_argument("--checks", default="checks.json")
    p.add_argument("--out", default="web/index.html")
    a = p.parse_args()

    data = build(
        load_validated(a.steps),
        load_validated(a.runs),
        load_validated(a.checks),
    )
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")

    print(f"wrote {out}")
    print(f"  total   {_clock(data['total_ms'])}  {_money(data['total_coins'])}")
    print(f"  wasted  {_clock(data['wasted_ms'])}  {_money(data['wasted_coins'])}")
    print(f"  {data['broken']} of {len(data['rows'])} steps cannot work")
    if data["overruled"]:
        print(f"  the check overruled Bob on {data['overruled']} of {data['claimed_ok']} claims")


if __name__ == "__main__":
    main()
