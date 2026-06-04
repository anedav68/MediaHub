"""Step 8 — provenance + hardening for results-from-a-link.

Covers the per-session rate limit, the source_url provenance round-trip (the
sidecar _start_run writes and _run_source_url reads), and the invariant that a
re-fetch stages a brand-new run rather than mutating a finished one.
"""

from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture
def app_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs_v4"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads_v4"))
    monkeypatch.setenv("SWIM_CONTENT_PROFILES_DIR", str(tmp_path / "club_profiles"))
    monkeypatch.setenv("MEDIAHUB_RESULTS_FETCH_ENABLED", "1")
    for sub in ("runs_v4", "uploads_v4", "club_profiles"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    import mediahub.web.club_profile as cp
    import mediahub.web.web as wm

    importlib.reload(cp)
    importlib.reload(wm)
    app = wm.create_app()
    app.config["TESTING"] = True
    app.secret_key = "test"
    return app, wm


def _make_zip_html() -> bytes:
    import io
    import zipfile

    html = (
        "<html><body><table><tr><th>Place</th><th>Name</th><th>Time</th></tr>"
        "<tr><td>1</td><td>Ada</td><td>1:02.34</td></tr></table></body></html>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("event1.html", html)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


def test_rate_limit_returns_429(app_mod, monkeypatch):
    app, wm = app_mod
    monkeypatch.setattr("mediahub.web_research.safe_fetch.is_url_safe", lambda u: True)

    # Keep the started jobs from doing real network work.
    from mediahub.results_fetch.crawl import CrawlResult

    monkeypatch.setattr(
        "mediahub.results_fetch.crawl.crawl_results_site",
        lambda url, **kw: CrawlResult(entry_url=url),
    )

    c = app.test_client()
    statuses = []
    for _ in range(wm._URL_FETCH_RATE_MAX + 2):
        r = c.post("/upload/from-url", data={"url": "https://results.example.org/x/"})
        statuses.append(r.status_code)
    assert statuses[: wm._URL_FETCH_RATE_MAX] == [200] * wm._URL_FETCH_RATE_MAX
    assert 429 in statuses[wm._URL_FETCH_RATE_MAX :]


# ---------------------------------------------------------------------------
# source_url provenance round-trip
# ---------------------------------------------------------------------------


def test_run_source_url_reads_sidecar(app_mod):
    app, wm = app_mod
    run_dir = wm.RUNS_DIR / "abc123abc123"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "source_url.txt").write_text("https://results.example.org/meet/", encoding="utf-8")
    assert wm._run_source_url("abc123abc123") == "https://results.example.org/meet/"
    # absent sidecar → None (a normal file upload)
    (wm.RUNS_DIR / "deadbeefdead").mkdir(parents=True, exist_ok=True)
    assert wm._run_source_url("deadbeefdead") is None


def test_stage_carries_source_url_into_meta(app_mod):
    app, wm = app_mod
    rid = wm._stage_results_zip(_make_zip_html(), "https://results.example.org/meet/2026/", None)
    meta = json.loads((wm.RUNS_DIR / rid / "upload_meta.json").read_text())
    assert meta["source_url"] == "https://results.example.org/meet/2026/"
    assert (wm.RUNS_DIR / rid / "input.bin").exists()


def test_refetch_stages_a_distinct_run(app_mod):
    """A re-fetch must be a NEW run, never a mutation of the previous one."""
    app, wm = app_mod
    url = "https://results.example.org/meet/"
    rid1 = wm._stage_results_zip(_make_zip_html(), url, None)
    rid2 = wm._stage_results_zip(_make_zip_html(), url, None)
    assert rid1 != rid2
    assert (wm.RUNS_DIR / rid1 / "input.bin").exists()
    assert (wm.RUNS_DIR / rid2 / "input.bin").exists()
    # both carry the same origin, independently
    for rid in (rid1, rid2):
        meta = json.loads((wm.RUNS_DIR / rid / "upload_meta.json").read_text())
        assert meta["source_url"] == url
