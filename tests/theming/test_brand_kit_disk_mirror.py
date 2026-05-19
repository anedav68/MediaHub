"""Stage G — BrandKit.ensure_derived_palette() mirrors to disk.

After the hook lands, every call to ensure_derived_palette() should
also write the resolved palette to DATA_DIR/themes/<profile_id>.json
so the motion, email, and static-graphic renderers can read it
without loading the full ClubProfile.

A disk-write failure must NOT break the in-memory return value —
the legacy fallback paths still work.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from mediahub.brand.kit import BrandKit


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from mediahub.theming.theme_store import _read_cached
    _read_cached.cache_clear()
    return tmp_path


class TestDiskMirror:
    def test_palette_persists_to_themes_dir(self, isolated_data_dir):
        kit = BrandKit(profile_id="mirror-test", display_name="Mirror",
                       primary_colour="#0E2A47")
        palette = kit.ensure_derived_palette()

        from mediahub.theming.theme_store import read_theme
        on_disk = read_theme("mirror-test")
        assert on_disk is not None
        assert on_disk == palette

    def test_disk_content_round_trips(self, isolated_data_dir):
        kit = BrandKit(profile_id="round-trip", display_name="RT",
                       primary_colour="#06D6A0")
        palette = kit.ensure_derived_palette()

        from mediahub.theming.theme_store import theme_path
        path = theme_path("round-trip")
        assert path.is_file()
        # The file is real JSON
        import json
        loaded = json.loads(path.read_text())
        assert loaded["seed_hex"] == "#06D6A0"

    def test_force_rewrites_file(self, isolated_data_dir):
        kit = BrandKit(profile_id="force-test", display_name="F",
                       primary_colour="#0E2A47")
        kit.ensure_derived_palette()
        from mediahub.theming.theme_store import theme_path
        mtime1 = theme_path("force-test").stat().st_mtime_ns

        # Change the seed and force recompute
        kit.primary_colour = "#A30D2D"
        # Wait long enough that mtime can differ on coarse-mtime FS
        import time
        time.sleep(0.01)
        kit.ensure_derived_palette(force=True)
        mtime2 = theme_path("force-test").stat().st_mtime_ns

        # The file was rewritten — mtime may or may not differ on
        # all filesystems but at least the content reflects the new seed.
        from mediahub.theming.theme_store import read_theme
        on_disk = read_theme("force-test")
        assert on_disk["seed_hex"] == "#A30D2D"

    def test_disk_write_failure_does_not_break_in_memory(self, isolated_data_dir):
        """When write_theme raises (e.g. disk full), the in-memory
        palette is still authoritative — every consumer has a
        fallback path."""
        kit = BrandKit(profile_id="fail-write", display_name="FW",
                       primary_colour="#0E2A47")
        with patch("mediahub.theming.theme_store.write_theme",
                   side_effect=OSError("disk full")):
            palette = kit.ensure_derived_palette()
        # In-memory palette is set
        assert palette is not None
        assert palette["seed_hex"] == "#0E2A47"
        assert kit.derived_palette == palette
        # Disk file does NOT exist (write failed)
        from mediahub.theming.theme_store import read_theme
        assert read_theme("fail-write") is None

    def test_idempotent_no_duplicate_writes(self, isolated_data_dir):
        kit = BrandKit(profile_id="idem-test", display_name="I",
                       primary_colour="#0E2A47")
        kit.ensure_derived_palette()
        from mediahub.theming.theme_store import theme_path
        mtime1 = theme_path("idem-test").stat().st_mtime_ns
        # Second call should be a no-op (cached on instance)
        kit.ensure_derived_palette()
        mtime2 = theme_path("idem-test").stat().st_mtime_ns
        assert mtime1 == mtime2, "second call rewrote the file unexpectedly"
