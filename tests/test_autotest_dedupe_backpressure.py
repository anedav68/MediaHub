"""Anti-duplication + backpressure for the human-merge policy (Option 2): while a fix
PR awaits a (human) merge the symptom is still live on prod, so the finder keeps seeing
it. These guard against opening a SECOND PR for the same problem, and against fix PRs
piling up faster than they're merged.

Ground-truth tests (the ledger selection + the cap logic), no live coder/gh.
"""
from __future__ import annotations

import json

import pytest

from autotest import fix_loop, gitops, report


def _bug(fp, status="open", route="/review", category="semantic:user_brain", **kw):
    b = {"fingerprint": fp, "status": status, "severity": "high", "category": category,
         "route": route, "title": fp, "fix_attempts": 0, "present_last_run": True}
    b.update(kw)
    return b


@pytest.fixture
def ledger_of(tmp_path, monkeypatch):
    def _install(bugs):
        led = tmp_path / "ledger.json"
        led.write_text(json.dumps({"schema": report.SCHEMA_VERSION,
                                   "bugs": {b["fingerprint"]: b for b in bugs}, "skipped": {}}))
        monkeypatch.setattr(report, "LEDGER_PATH", led)
    return _install


# --- D: don't open a second fix for a problem already in flight -------------
def test_open_bug_at_an_in_flight_surface_is_suppressed(ledger_of):
    ledger_of([
        # A fix PR is already open for this surface (reworded — different fingerprint).
        _bug("inflight", status="fixing", route="/review", fix_pr="https://x/pr/1"),
        _bug("dupe_same_surface", status="open", route="/review"),   # same (cat,route)
        _bug("other_surface", status="open", route="/dashboard"),     # different surface
    ])
    fps = [b["fingerprint"] for b in fix_loop._open_bugs(10)]
    assert "dupe_same_surface" not in fps, "must not open a 2nd PR for an in-flight problem"
    assert "other_surface" in fps, "an unrelated problem is still eligible"
    assert "inflight" not in fps, "the in-flight bug itself stays excluded (has fix_pr)"


def test_regressed_at_in_flight_surface_also_suppressed(ledger_of):
    ledger_of([
        _bug("inflight", status="fixing", route="/review", fix_pr="https://x/pr/2"),
        _bug("regressed_same", status="regressed", route="/review"),
    ])
    assert fix_loop._open_bugs(10) == [], "a regressed dup at an in-flight surface is suppressed"


def test_distinct_surfaces_all_returned(ledger_of):
    ledger_of([
        _bug("a", route="/review"), _bug("b", route="/dashboard"), _bug("c", route="/activity"),
    ])
    assert len(fix_loop._open_bugs(10)) == 3, "distinct problems are not over-collapsed"


# --- B: count_open_fix_prs ---------------------------------------------------
def test_count_open_fix_prs_parses_gh(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _x: "/usr/bin/gh")

    class _P:
        stdout = "4\n"
        stderr = ""
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: _P())
    assert gitops.count_open_fix_prs() == 4


def test_count_open_fix_prs_zero_without_gh(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _x: None)
    assert gitops.count_open_fix_prs() == 0


def test_count_open_fix_prs_zero_on_bad_output(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _x: "/usr/bin/gh")

    class _P:
        stdout = "not a number"
        stderr = ""
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: _P())
    assert gitops.count_open_fix_prs() == 0   # don't throttle on an unknown count


# --- B: the cap pauses the fixer --------------------------------------------
def test_fixer_pauses_when_cap_reached(monkeypatch, capsys):
    monkeypatch.setenv("AUTOTEST_FIX_APPLY", "1")
    monkeypatch.setenv("AUTOTEST_MAX_OPEN_FIX_PRS", "3")
    monkeypatch.setattr(gitops, "count_open_fix_prs", lambda: 5)
    called = []
    monkeypatch.setattr(fix_loop, "fix_one", lambda bug: called.append(bug))
    monkeypatch.setattr(fix_loop, "_persist_to_main", lambda: None)
    monkeypatch.setattr(fix_loop, "_open_bugs", lambda limit: [{"fingerprint": "x", "title": "x"}])

    rc = fix_loop.main()
    assert rc == 0
    assert not called, "fixer must not open new PRs while >= cap are open"
    assert "paused" in capsys.readouterr().out


def test_fixer_proceeds_when_under_cap(monkeypatch):
    monkeypatch.setenv("AUTOTEST_FIX_APPLY", "1")
    monkeypatch.setenv("AUTOTEST_MAX_OPEN_FIX_PRS", "3")
    monkeypatch.setattr(gitops, "count_open_fix_prs", lambda: 1)   # under cap
    called = []
    monkeypatch.setattr(fix_loop, "fix_one", lambda bug: called.append(bug) or {"fp": bug["fingerprint"]})
    monkeypatch.setattr(fix_loop, "_persist_to_main", lambda: None)
    monkeypatch.setattr(fix_loop, "_open_bugs", lambda limit: [{"fingerprint": "x", "title": "x"}])

    fix_loop.main()
    assert called, "under the cap, the fixer proceeds normally"


def test_cap_disabled_with_zero(monkeypatch):
    monkeypatch.setenv("AUTOTEST_FIX_APPLY", "1")
    monkeypatch.setenv("AUTOTEST_MAX_OPEN_FIX_PRS", "0")
    # count would be huge, but cap=0 disables the check → count never consulted.
    monkeypatch.setattr(gitops, "count_open_fix_prs",
                        lambda: (_ for _ in ()).throw(AssertionError("should not be called")))
    monkeypatch.setattr(fix_loop, "fix_one", lambda bug: {"fp": bug["fingerprint"]})
    monkeypatch.setattr(fix_loop, "_persist_to_main", lambda: None)
    monkeypatch.setattr(fix_loop, "_open_bugs", lambda limit: [])
    assert fix_loop.main() == 0
