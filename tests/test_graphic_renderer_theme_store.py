"""Stage G4 — graphic renderer reads from the theme store.

_common_replacements() should accept an optional theme_json dict
and prefer its light-scheme roles over brief.palette. When no
theme JSON is provided but the brand_kit carries a profile_id that
resolves to a theme on disk, _common_replacements should resolve it
itself via theme_store.read_theme.

Without any theme source, behaviour is unchanged.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from mediahub.theming.theme_store import _read_cached
    _read_cached.cache_clear()
    return tmp_path


def _seed_theme(pid, primary):
    from mediahub.brand.kit import BrandKit
    kit = BrandKit(profile_id=pid, display_name=f"Test {pid}",
                   primary_colour=primary)
    return kit.ensure_derived_palette()


def _minimal_brief(palette=None):
    """Build the minimum CreativeBrief-shape object the helper
    consumes. Uses SimpleNamespace because we don't need a real
    dataclass — _common_replacements just attribute-accesses."""
    return SimpleNamespace(
        palette=palette or {
            "primary": "#FALLBK",
            "secondary": "#000000",
            "accent": "#FFFFFF",
        },
        text_layers={},
        confidence_label="STRONG SWIM",
        # The remaining fields _common_replacements reads — set to
        # defaults that won't crash the function:
        meet_name="Test Meet",
        meet_date="",
        venue="",
        meet_location="",
        athlete_full_name="",
        result_value="",
        event_label="",
    )


class TestThemeJSONParameter:
    """When theme_json is passed explicitly, it overrides brief.palette."""

    def test_theme_json_overrides_brief_palette(self, isolated_data_dir):
        theme = _seed_theme("explicit", "#A30D2D")
        from mediahub.graphic_renderer.render import _common_replacements

        brief = _minimal_brief(palette={"primary": "#OLDPRIM",
                                        "secondary": "#OLDSEC",
                                        "accent": "#OLDACC"})
        result = _common_replacements(
            brief, 1080, 1080, brand_kit=None,
            athlete_data_uri=None, logo_block="", result_chip="",
            sponsor_block="", theme_json=theme,
        )
        # The PRIMARY placeholder substitution should carry the
        # theme-store light primary.
        expected = theme["roles"]["light"]["primary"].upper()
        # The replacements dict's PRIMARY key should resolve to the
        # theme-store value (case may vary).
        assert result["PRIMARY"].upper() == expected, (
            f"PRIMARY = {result['PRIMARY']}, expected {expected}"
        )


class TestImplicitProfileLookup:
    """When theme_json is NOT passed but brand_kit carries a
    profile_id that maps to a theme on disk, _common_replacements
    resolves it automatically."""

    def test_brand_kit_with_profile_id_resolves(self, isolated_data_dir):
        theme = _seed_theme("implicit", "#06D6A0")
        from mediahub.graphic_renderer.render import _common_replacements

        brand_kit = SimpleNamespace(profile_id="implicit",
                                    primary_colour="#06D6A0",
                                    display_name="Test")
        brief = _minimal_brief()
        result = _common_replacements(
            brief, 1080, 1080, brand_kit=brand_kit,
            athlete_data_uri=None, logo_block="", result_chip="",
            sponsor_block="",
        )
        expected = theme["roles"]["light"]["primary"].upper()
        assert result["PRIMARY"].upper() == expected

    def test_brand_kit_dict_input(self, isolated_data_dir):
        theme = _seed_theme("dict-kit", "#06D6A0")
        from mediahub.graphic_renderer.render import _common_replacements
        brief = _minimal_brief()
        result = _common_replacements(
            brief, 1080, 1080,
            brand_kit={"profile_id": "dict-kit",
                       "primary_colour": "#06D6A0"},
            athlete_data_uri=None, logo_block="", result_chip="",
            sponsor_block="",
        )
        expected = theme["roles"]["light"]["primary"].upper()
        assert result["PRIMARY"].upper() == expected


class TestLegacyFallback:
    """Without theme_json or a profile_id, behaviour is unchanged —
    brief.palette wins."""

    def test_no_theme_no_kit_uses_brief_palette(self, isolated_data_dir):
        from mediahub.graphic_renderer.render import _common_replacements
        brief = _minimal_brief(palette={"primary": "#123456",
                                        "secondary": "#000000",
                                        "accent": "#FFFFFF"})
        result = _common_replacements(
            brief, 1080, 1080, brand_kit=None,
            athlete_data_uri=None, logo_block="", result_chip="",
            sponsor_block="",
        )
        assert result["PRIMARY"] == "#123456"

    def test_brand_kit_without_profile_id(self, isolated_data_dir):
        from mediahub.graphic_renderer.render import _common_replacements
        brief = _minimal_brief(palette={"primary": "#ABCDEF",
                                        "secondary": "#000",
                                        "accent": "#FFF"})
        # brand_kit has primary_colour but no profile_id
        result = _common_replacements(
            brief, 1080, 1080,
            brand_kit={"primary_colour": "#XYZ"},  # no profile_id
            athlete_data_uri=None, logo_block="", result_chip="",
            sponsor_block="",
        )
        # brief.palette wins (no theme source)
        assert result["PRIMARY"] == "#ABCDEF"


class TestZeroDriftAcrossSurfaces:
    """The headline guarantee: motion (dark scheme), email + static
    (light scheme) all draw from the same theme JSON, so a single
    finalise produces consistent output across the three surfaces."""

    def test_email_and_static_agree(self, isolated_data_dir):
        theme = _seed_theme("zero-drift", "#A30D2D")

        # Email path
        from mediahub.brand.newsletter_renderer import _resolve_email_primary
        email_primary = _resolve_email_primary({"profile_id": "zero-drift",
                                                 "brand_primary": "#A30D2D"})

        # Static path
        from mediahub.theming.theme_store import palette_for_static
        static_primary = palette_for_static(theme)["primary"]

        assert email_primary.upper() == static_primary.upper(), (
            "email + static primary must agree — both use light scheme"
        )

    def test_motion_uses_dark_not_light(self, isolated_data_dir):
        theme = _seed_theme("scheme-split", "#A30D2D")
        from mediahub.theming.theme_store import (
            palette_for_motion, palette_for_email,
        )
        motion = palette_for_motion(theme)
        email = palette_for_email(theme)
        # They WILL differ — motion uses dark, email uses light
        assert motion["primary"] != email["primary"]
        assert motion["scheme"] == "dark"
        assert email["scheme"] == "light"
