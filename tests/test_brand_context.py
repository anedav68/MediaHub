"""tests/test_brand_context.py — single canonical brand briefing.

Every content tool must consume the same `brand_context_for_llm()`
helper so behaviour stays consistent across the site. This test
suite pins the helper's output shape against the four sources of
brand truth (identity, captured DNA, voice profile, uploaded
guidelines).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from mediahub.brand.context import brand_context_for_llm  # noqa: E402
from mediahub.web.club_profile import ClubProfile  # noqa: E402


class TestEmptyAndDictProfile:
    def test_none_returns_empty(self):
        assert brand_context_for_llm(None) == ""

    def test_blank_profile_returns_empty(self):
        p = ClubProfile(profile_id="x", display_name="")
        assert brand_context_for_llm(p) == ""

    def test_accepts_dict_form(self):
        out = brand_context_for_llm({"display_name": "Dict Club"})
        assert "Dict Club" in out


class TestIdentitySection:
    def test_includes_display_name(self):
        p = ClubProfile(
            profile_id="x", display_name="City Aquatics",
            short_name="City AC", governing_body="Swim England",
            country="United Kingdom",
        )
        out = brand_context_for_llm(p)
        assert "City Aquatics" in out
        assert "City AC" in out
        assert "Swim England" in out
        assert "United Kingdom" in out

    def test_sponsor_called_out(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            sponsor_name="Acme Sports",
        )
        out = brand_context_for_llm(p)
        assert "Acme Sports" in out


class TestCapturedDnaSection:
    def test_voice_summary_surfaced(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_voice_summary="A warm community swimming club.",
        )
        out = brand_context_for_llm(p)
        assert "warm community swimming club" in out

    def test_phrases_to_use_and_avoid(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_phrases_to_use=["Big PB", "Massive shout out"],
            brand_phrases_to_avoid=["elite athletes only"],
        )
        out = brand_context_for_llm(p)
        assert "Big PB" in out
        assert "Massive shout out" in out
        assert "elite athletes only" in out
        # The "avoid" phrase must be flagged as such
        assert "off-brand" in out or "never use" in out.lower() or "do not use" in out.lower()


class TestVoiceProfileSection:
    def test_emoji_zero_means_explicit_no_emoji(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            voice_profile={"emoji_rate_per_caption": 0},
        )
        out = brand_context_for_llm(p)
        assert "does NOT use emoji" in out

    def test_swimmer_address_surfaced(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            voice_profile={"preferred_swimmer_address": "surname_only"},
        )
        out = brand_context_for_llm(p)
        assert "surname only" in out.lower()


class TestGuidelinesSection:
    """The new bit — uploaded brand-guidelines document must flow
    through into the canonical briefing every content tool sees."""

    def test_summary_surfaced(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_guidelines={
                "summary": "Warm, inclusive, never cynical.",
            },
        )
        out = brand_context_for_llm(p)
        assert "Warm, inclusive, never cynical" in out

    def test_dos_and_donts_surfaced(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_guidelines={
                "tone_dos": ["Use first names", "Celebrate effort"],
                "tone_donts": ["Compare swimmers", "Use jargon"],
            },
        )
        out = brand_context_for_llm(p)
        assert "Use first names" in out
        assert "Celebrate effort" in out
        assert "Compare swimmers" in out
        # The do's vs don'ts must be distinguished — the LLM relies
        # on the wording, not on the data structure.
        do_idx = out.find("Use first names")
        dont_idx = out.find("Compare swimmers")
        assert do_idx != -1 and dont_idx != -1
        # "DO NOT" must appear before the don't items
        do_not_idx = out.find("DO NOT")
        assert do_not_idx != -1 and do_not_idx < dont_idx

    def test_prohibited_words_emphasised(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_guidelines={
                "prohibited_words": ["loser", "failure"],
            },
        )
        out = brand_context_for_llm(p)
        assert "loser" in out
        assert "failure" in out
        # Must be marked as banned, not just listed neutrally
        assert "Prohibited" in out or "never use" in out.lower()

    def test_preferred_terminology_pairs_directional(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_guidelines={
                "preferred_terminology": {"members": "swimmers", "kids": "juniors"},
            },
        )
        out = brand_context_for_llm(p)
        # The direction matters: "wrong → right"
        assert '"members" → "swimmers"' in out
        assert '"kids" → "juniors"' in out

    def test_hashtag_and_sponsor_rules(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_guidelines={
                "hashtag_rules": "Always include #ClubLife.",
                "sponsor_mention_rules": "Tag @sponsor in every meet recap.",
            },
        )
        out = brand_context_for_llm(p)
        assert "#ClubLife" in out
        assert "@sponsor" in out

    def test_key_messages_woven_in(self):
        p = ClubProfile(
            profile_id="x", display_name="City",
            brand_guidelines={
                "key_messages": ["Inclusion", "Effort over outcome"],
            },
        )
        out = brand_context_for_llm(p)
        assert "Inclusion" in out
        assert "Effort over outcome" in out


class TestAllSectionsCombined:
    def test_full_profile_produces_all_sections(self):
        p = ClubProfile(
            profile_id="x",
            display_name="City Aquatics",
            governing_body="Swim England",
            country="United Kingdom",
            sponsor_name="Acme",
            brand_voice_summary="Inclusive community club.",
            brand_phrases_to_use=["Big PB"],
            brand_phrases_to_avoid=["elite only"],
            brand_keywords=["community", "inclusive"],
            voice_profile={
                "sentence_length_avg": 9,
                "emoji_rate_per_caption": 0.0,
                "preferred_swimmer_address": "first_name",
            },
            brand_guidelines={
                "summary": "Warm, inclusive.",
                "voice_attributes": ["warm"],
                "tone_dos": ["Use first names"],
                "tone_donts": ["Be cynical"],
                "prohibited_words": ["loser"],
                "key_messages": ["Inclusion"],
            },
        )
        out = brand_context_for_llm(p)
        # All four sources represented
        assert "City Aquatics" in out                # identity
        assert "Inclusive community club" in out    # captured DNA
        assert "9 words on average" in out          # voice profile
        assert "Warm, inclusive" in out             # uploaded guidelines
        # Banned word present and flagged
        assert "loser" in out
