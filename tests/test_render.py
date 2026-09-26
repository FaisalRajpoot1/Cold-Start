"""The renderer must be a pure, deterministic function of committed files.

The demo replays committed recordings, so these tests are what let us promise the
video cannot break. They also pin the derived-verdict matrix, which is the only
place in the project where a colour is decided.
"""

from __future__ import annotations

import pytest

from coldstart.render import build, render, verdict_for
from coldstart.schema import CHECKS_SCHEMA, RUNS_SCHEMA, STEPS_SCHEMA


def _steps(n: int = 2) -> dict:
    return {
        "schema": STEPS_SCHEMA,
        "source_repo": "sqlfluff/sqlfluff",
        "source_commit": "c7401613" + "0" * 32,
        "doc_path": "CONTRIBUTING.md",
        "doc_sha256": "a" * 64,
        "steps": [
            {
                "id": i,
                "title": f"Step {i}",
                "doc_lines": [10 * i, 10 * i],
                "quote": f"do thing {i}",
                "kind": "command",
                "bob_prompt": f"Carry out step {i}.",
                "check": {"cmd": ["python", "-c", "pass"], "describes": "a thing"},
                "expected": "green",
            }
            for i in range(1, n + 1)
        ],
    }


def _runs(costs, claims) -> dict:
    return {
        "schema": RUNS_SCHEMA,
        "bob_version": "2.0.5",
        "recorded_at": "2026-09-26T18:00:00Z",
        "max_cost": 1.2,
        "runs": [
            {
                "step_id": i,
                "task_id": f"t{i}",
                "ndjson": f"recordings/step-{i:02d}.ndjson",
                "session_costs": c,
                "duration_ms": 60_000,
                "tool_calls": 3,
                "bob_status": "success",
                "error_frames": [] if cl == "completed" else [{"message": "turn limit"}],
                "capped": cl != "completed",
                "bob_claim": cl,
                "bob_final_message": "done",
            }
            for i, (c, cl) in enumerate(zip(costs, claims, strict=True), 1)
        ],
    }


def _checks(verdicts) -> dict:
    return {
        "schema": CHECKS_SCHEMA,
        "checks": [
            {
                "step_id": i,
                "cmd": ["python", "-c", "pass"],
                "exit_code": 0 if v == "pass" else 1,
                "stdout_tail": "",
                "stderr_tail": "" if v == "pass" else "no such file in this repository",
                "duration_ms": 40,
                "verdict": v,
            }
            for i, v in enumerate(verdicts, 1)
        ],
    }


# ------------------------------------------------------------- the verdict matrix


@pytest.mark.contract
@pytest.mark.parametrize(
    ("claim", "check", "expect"),
    [
        ("completed", "pass", "ok"),
        ("completed", "fail", "overruled"),  # THE SAVE
        ("failed", "fail", "broken"),
        ("failed", "pass", "amber"),
    ],
)
def test_verdict_matrix(claim, check, expect):
    """Documented in docs/ARCHITECTURE.md. The overruled cell is the product."""
    assert verdict_for(claim, check) == expect


@pytest.mark.contract
def test_expected_never_decides_a_colour():
    """`expected` is our prediction. If it ever drove the colour, the receipt
    would show what we assumed instead of what happened."""
    steps = _steps(1)
    steps["steps"][0]["expected"] = "green"  # we predict pass
    data = build(steps, _runs([0.5], ["completed"]), _checks(["fail"]))  # reality: fail
    assert data["rows"][0]["state"] == "overruled"
    assert data["broken"] == 1


# --------------------------------------------------------------------- arithmetic


def test_only_failed_steps_count_as_wasted():
    data = build(
        _steps(3),
        _runs([0.40, 0.60, 0.20], ["completed", "completed", "failed"]),
        _checks(["pass", "fail", "fail"]),
    )
    assert data["total_coins"] == pytest.approx(1.20)
    # step 2 overruled + step 3 broken
    assert data["wasted_coins"] == pytest.approx(0.80)
    assert data["broken"] == 2
    assert data["overruled"] == 1
    assert data["claimed_ok"] == 2


def test_a_clean_repo_has_no_stamp_and_no_waste():
    data = build(_steps(2), _runs([0.3, 0.3], ["completed"] * 2), _checks(["pass"] * 2))
    assert data["wasted_coins"] == 0
    assert data["overruled"] == 0
    assert "OVERRULED" not in render(data)
    assert "check overruled Bob" not in render(data)


# ------------------------------------------------------------------ determinism


@pytest.mark.contract
def test_render_is_byte_stable():
    """Same inputs in, byte-identical HTML out.

    No clock, no random ids, no dict-order leak. This is what lets the demo
    replay committed recordings and produce the same receipt every time.
    """
    args = (_steps(3), _runs([0.4, 0.6, 0.2], ["completed", "completed", "failed"]),
            _checks(["pass", "fail", "fail"]))
    first = render(build(*args))
    second = render(build(*args))
    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")


@pytest.mark.contract
def test_no_network_calls_in_the_rendered_page_body():
    """Fonts may come from Google, but nothing else may. In particular there is
    no script tag, so the page cannot fetch anything at runtime."""
    page = render(build(_steps(2), _runs([0.3, 0.3], ["completed"] * 2), _checks(["pass"] * 2)))
    assert "<script" not in page.lower()
    for host in ("api.", "http://", "localhost", "bob.ibm.com"):
        assert host not in page.lower().replace("https://fonts.googleapis.com", "").replace(
            "https://fonts.gstatic.com", ""
        )


def test_page_carries_a_local_font_fallback():
    """The page must be correct with the network off, so every font rule needs a
    local stack behind the webfont."""
    page = render(build(_steps(1), _runs([0.3], ["completed"]), _checks(["pass"])))
    assert "ui-monospace" in page
    assert "system-ui" in page


# ----------------------------------------------------------------------- escaping


def test_content_is_escaped():
    steps = _steps(1)
    steps["steps"][0]["title"] = '<script>alert("x")</script> & co'
    page = render(build(steps, _runs([0.1], ["completed"]), _checks(["pass"])))
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "&amp; co" in page


def test_failure_reason_is_shown_under_the_row():
    data = build(_steps(1), _runs([0.5], ["failed"]), _checks(["fail"]))
    page = render(data)
    assert "no such file in this repository" in page


# ------------------------------------------------------------------- presentation


def test_money_uses_the_published_rate():
    """1 Bobcoin = $0.50, IBM's published rate, cited on the page."""
    data = build(_steps(1), _runs([2.0], ["completed"]), _checks(["pass"]))
    page = render(data)
    assert "$1.00" in page
    assert "1 Bobcoin = $0.50" in page


def test_no_green_success_markers_anywhere():
    """docs/DESIGN.md: passing steps get no colour at all. A receipt marks only
    the problems. No ticks, no PASS pills, no green."""
    page = render(build(_steps(3), _runs([0.3] * 3, ["completed"] * 3), _checks(["pass"] * 3)))
    lowered = page.lower()
    for banned in ("green", "#3fb950", "&#10003;", "✓", "passed", "success-badge"):
        assert banned not in lowered, f"{banned!r} must not appear: only problems are marked"
