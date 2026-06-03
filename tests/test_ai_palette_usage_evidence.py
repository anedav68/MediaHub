"""tests/test_ai_palette_usage_evidence.py — AI-decides-palette-from-usage.

The brand-colour decision is made by the cloud LLM from rich colour-USAGE
evidence (frequency across the full site CSS, incl. linked stylesheets);
the deterministic colour-decision / fallback was removed. These tests
pin the new behaviour:

  - build_colour_usage_map counts frequency across combined HTML+CSS and
    sorts desc, applying the white/black/near-grey hygiene filter.
  - fetch_linked_css pulls a <link rel=stylesheet> via an injected
    fetcher, and degrades silently on failure.
  - _build_llm_prompt shows per-colour usage counts AND the default-
    palette ignore guidance.
  - _heuristic() emits NO palette_mentions but still returns voice /
    keywords / hashtags.
  - resolve_palette raises ClaudeUnavailableError when no LLM is
    configured (AI-only; no deterministic fallback).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from mediahub.brand import dna_capture  # noqa: E402
from mediahub.brand import palette  # noqa: E402
from mediahub.brand.link_learners import content_extractor  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Colour-usage map: frequency, sorted desc, hygiene filter
# ---------------------------------------------------------------------------

class TestColourUsageMap:
    def test_counts_frequency_and_sorts_desc(self):
        text = (
            "a{color:#1f336c}b{color:#1f336c}c{color:#1f336c}"  # navy x3
            ".d{color:#2ea3f2}.e{color:#2ea3f2}"               # blue x2
            ".f{color:#006799}"                                # x1
        )
        usage = dna_capture.build_colour_usage_map(text)
        assert usage[0] == ("#1f336c", 3)
        assert usage[1] == ("#2ea3f2", 2)
        assert ("#006799", 1) in usage
        # Strictly non-increasing counts.
        counts = [c for _, c in usage]
        assert counts == sorted(counts, reverse=True)

    def test_hygiene_filter_drops_white_black_grey(self):
        text = (
            "x{color:#ffffff}y{color:#000000}z{color:#808080}"
            "q{color:#eeeeee}r{color:#1a1a1a}brand{color:#c0392b}"
        )
        usage = dna_capture.build_colour_usage_map(text)
        hexes = {h for h, _ in usage}
        assert "#c0392b" in hexes
        for noise in ("#ffffff", "#000000", "#808080", "#eeeeee", "#1a1a1a"):
            assert noise not in hexes

    def test_combined_html_and_css_counted_together(self):
        html = "<body style='color:#1f336c'><a style='color:#1f336c'></a></body>"
        css = "a{color:#1f336c}.b{color:#2ea3f2}"
        usage = dna_capture.build_colour_usage_map(html + "\n" + css)
        as_dict = dict(usage)
        assert as_dict["#1f336c"] == 3  # 2 in HTML + 1 in CSS
        assert as_dict["#2ea3f2"] == 1

    def test_empty_text(self):
        assert dna_capture.build_colour_usage_map("") == []


# ---------------------------------------------------------------------------
# 2. Linked-CSS fetch helper (injected fetcher; silent degrade)
# ---------------------------------------------------------------------------

class TestFetchLinkedCss:
    HTML = (
        "<html><head>"
        "<link rel='stylesheet' href='/theme.css'>"
        "</head><body style='color:#1f336c'></body></html>"
    )

    def test_includes_stylesheet_colours(self):
        seen = {}

        def fetcher(url):
            seen["url"] = url
            return "a{color:#1f336c}b{color:#1f336c}c{color:#2ea3f2}"

        usage = dna_capture.colour_usage_evidence(
            self.HTML, "https://club.example/", css_fetcher=fetcher,
        )
        assert seen["url"].endswith("/theme.css")
        as_dict = dict(usage)
        # navy: 1 (HTML inline) + 2 (CSS) = 3
        assert as_dict["#1f336c"] == 3
        assert as_dict["#2ea3f2"] == 1

    def test_degrades_silently_on_fetch_failure(self):
        def boom(url):
            raise RuntimeError("network down")

        # Must not raise; falls back to HTML-only evidence.
        usage = dna_capture.colour_usage_evidence(
            self.HTML, "https://club.example/", css_fetcher=boom,
        )
        as_dict = dict(usage)
        assert as_dict.get("#1f336c") == 1  # only the inline HTML colour

    def test_fetcher_returning_none_is_ignored(self):
        usage = dna_capture.colour_usage_evidence(
            self.HTML, "https://club.example/", css_fetcher=lambda u: None,
        )
        assert dict(usage).get("#1f336c") == 1

    def test_bounds_max_three_sheets(self):
        html = "<html><head>" + "".join(
            f"<link rel='stylesheet' href='/s{i}.css'>" for i in range(8)
        ) + "</head></html>"
        calls = []

        def fetcher(url):
            calls.append(url)
            return "a{color:#1f336c}"

        dna_capture.fetch_linked_css(html, "https://club.example/", fetcher=fetcher)
        assert len(calls) <= 3


# ---------------------------------------------------------------------------
# 3. Prompt: per-colour usage counts + default-palette ignore guidance
# ---------------------------------------------------------------------------

class TestPromptEngineering:
    def test_prompt_includes_usage_counts(self):
        sources = palette.gather_colour_sources(
            colour_usage={"website": [("#1f336c", 21), ("#2ea3f2", 52)]},
        )
        prompt = palette._build_llm_prompt(
            org_name="Chelmsford", voice_summary="x", sources=sources,
            allow_fourth=False, usage_counts=sources.colour_usage,
        )
        assert "#1f336c×21" in prompt
        assert "#2ea3f2×52" in prompt
        assert "colours by CSS usage" in prompt

    def test_prompt_resolve_threads_counts_automatically(self):
        # resolve_palette pulls usage_counts off the sources object.
        sources = palette.gather_colour_sources(
            colour_usage={"website": [("#1f336c", 21)]},
        )
        prompt = palette._build_llm_prompt(
            org_name="x", voice_summary="", sources=sources, allow_fourth=False,
            usage_counts=getattr(sources, "colour_usage", {}),
        )
        assert "#1f336c×21" in prompt

    def test_prompt_has_default_palette_ignore_guidance(self):
        sources = palette.gather_colour_sources(
            colour_usage={"website": [("#1f336c", 21)]},
        )
        prompt = palette._build_llm_prompt(
            org_name="x", voice_summary="", sources=sources, allow_fourth=False,
            usage_counts=sources.colour_usage,
        )
        low = prompt.lower()
        assert "default" in low
        # Names at least the major page-builders to ignore.
        assert "wordpress" in low or "gutenberg" in low
        assert "material" in low
        assert "bootstrap" in low

    def test_system_prompt_names_defaults_and_usage(self):
        sys_low = palette._LLM_SYSTEM.lower()
        assert "usage" in sys_low
        assert "default" in sys_low
        assert "divi" in sys_low
        assert "elementor" in sys_low


# ---------------------------------------------------------------------------
# 4. Heuristic emits NO palette but keeps voice/keywords/hashtags
# ---------------------------------------------------------------------------

class TestHeuristicNoPalette:
    def test_heuristic_emits_no_palette_mentions(self):
        body = (
            "<html><body><style>.brand{color:#c0392b}</style>"
            "Riverside Rowing Club — proud since 1921. #RowAsOne</body></html>"
        )
        out = content_extractor._heuristic(body)
        assert out["palette_mentions"] == []
        # Voice / hashtags still work.
        assert out["voice_summary"]
        assert "#RowAsOne" in out["hashtag_patterns"]

    def test_extract_brand_dna_no_llm_has_no_palette(self, monkeypatch):
        import mediahub.media_ai.llm as _llm
        monkeypatch.setattr(_llm, "is_available", lambda: False, raising=False)
        out = content_extractor.extract_brand_dna(
            "<body><style>.x{color:#c0392b}</style>Club #Tag</body>",
            url="https://x", platform_intent="website",
        )
        assert out["palette_mentions"] == []
        assert "#Tag" in out["hashtag_patterns"]


# ---------------------------------------------------------------------------
# 5. resolve_palette is AI-only (raises without an LLM)
# ---------------------------------------------------------------------------

class TestResolveIsAiOnly:
    def test_raises_when_no_llm(self, monkeypatch):
        from mediahub.media_ai import llm as _llm
        monkeypatch.setattr(_llm, "is_available", lambda: False)
        sources = palette.gather_colour_sources(
            colour_usage={"website": [("#1f336c", 21), ("#2ea3f2", 52)]},
        )
        with pytest.raises(_llm.ClaudeUnavailableError):
            palette.resolve_palette(
                org_name="Chelmsford", voice_summary="", sources=sources,
                allow_fourth=False,
            )

    def test_universe_includes_usage_colours(self, monkeypatch):
        # A pick that is ONLY in the usage evidence (not in mentions /
        # logo) must still validate — the universe spans all evidence.
        from mediahub.media_ai import llm as _llm
        monkeypatch.setattr(_llm, "is_available", lambda: True)
        monkeypatch.setattr(
            _llm, "generate_json",
            lambda *a, **kw: {"primary": "#1f336c", "secondary": "#2ea3f2",
                              "reasoning": "navy dominant by usage."},
        )
        sources = palette.gather_colour_sources(
            colour_usage={"website": [("#1f336c", 21), ("#2ea3f2", 52)]},
        )
        out = palette.resolve_palette(
            org_name="Chelmsford", voice_summary="", sources=sources,
            allow_fourth=False,
        )
        assert out["primary"] == "#1f336c"
        assert out["secondary"] == "#2ea3f2"
