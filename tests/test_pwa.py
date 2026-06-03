"""Tests for the installable PWA + service worker (Section 6 step 7b)."""

from __future__ import annotations

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from mediahub.web.web import create_app

    app = create_app()
    app.config["TESTING"] = True
    if not app.secret_key:
        app.secret_key = "test-secret"
    return app.test_client()


def test_manifest_is_valid_and_installable(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.mimetype == "application/manifest+json"
    m = r.get_json(force=True)
    assert m["name"] == "MediaHub" and m["short_name"] == "MediaHub"
    assert m["display"] == "standalone"
    assert m["start_url"] and m["scope"]  # present (prefix-resolved)
    assert m["theme_color"] and m["background_color"]
    assert m["icons"] and m["icons"][0]["src"]  # at least one icon


def test_service_worker_served_with_root_scope(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.mimetype
    # must be allowed to control the whole app, not just /sw.js's directory
    assert r.headers.get("Service-Worker-Allowed") == "/"
    body = r.get_data(as_text=True)
    for hook in (
        "addEventListener('install'",
        "addEventListener('activate'",
        "addEventListener('fetch'",
    ):
        assert hook in body
    assert "offline" in body.lower()


def test_service_worker_is_network_first(client):
    """Network-first: it tries fetch() before ever consulting the cache, so an
    online user can never be served a stale shell."""
    body = client.get("/sw.js").get_data(as_text=True)
    assert "await fetch(req)" in body
    assert body.index("await fetch(req)") < body.index("caches.match")


def test_pages_link_manifest_and_register_sw(client):
    html = client.get("/").get_data(as_text=True)
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert 'name="apple-mobile-web-app-capable"' in html
    assert "serviceWorker.register" in html
