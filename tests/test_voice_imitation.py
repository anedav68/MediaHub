"""
tests/test_voice_imitation.py — Deterministic tests for voice imitation.

All tests run without LLM access (mock or no key needed).
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

from mediahub.brand.voice_imitation import (
    _redact_pii,
    _compute_stats,
    analyse_examples,
)
from mediahub.web.club_profile import ClubProfile
from mediahub.web.ai_caption import _voice_profile_instructions


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

class TestRedactPii:
    def test_strips_full_name(self):
        result = _redact_pii(["Great swim by Sarah Johnson today!"])
        assert "Sarah Johnson" not in result[0]
        assert "[NAME]" in result[0]

    def test_strips_multiple_names(self):
        text = "Congrats to Emily Davis and Tom Wilson!"
        result = _redact_pii([text])
        assert "Emily Davis" not in result[0]
        assert "Tom Wilson" not in result[0]

    def test_preserves_club_names_single_word(self):
        text = "Great race from COMA today #swimming"
        result = _redact_pii([text])
        assert result[0] == text  # no change — not a 'First Last' pattern

    def test_empty_list(self):
        assert _redact_pii([]) == []

    def test_no_names(self):
        text = "Huge PBs for the squad! #swimming"
        result = _redact_pii([text])
        assert result[0] == text


# ---------------------------------------------------------------------------
# Sentence length stats
# ---------------------------------------------------------------------------

SHORT_EXAMPLES = [
    "Great swim!",
    "Huge PB! Well done!",
    "Amazing race today.",
]

LONG_EXAMPLES = [
    "What an incredible weekend for our club as we smashed five personal bests at the county championships!",
    "Massive congratulations to everyone who competed this weekend — you represented the club brilliantly.",
    "We are so proud of our junior squad for delivering their best performances of the season so far.",
]


class TestSentenceStats:
    def test_avg_sentence_len_short(self):
        stats = _compute_stats(SHORT_EXAMPLES)
        assert stats["sentence_length_avg"] < 6.0  # short sentences

    def test_avg_sentence_len_long(self):
        stats = _compute_stats(LONG_EXAMPLES)
        assert stats["sentence_length_avg"] >= 10.0  # long sentences

    def test_p90_ge_avg(self):
        stats = _compute_stats(SHORT_EXAMPLES + LONG_EXAMPLES)
        assert stats["sentence_length_p90"] >= stats["sentence_length_avg"]

    def test_empty_input(self):
        stats = _compute_stats([])
        assert stats["sentence_length_avg"] == 0.0
        assert stats["sentence_length_p90"] == 0.0


# ---------------------------------------------------------------------------
# Emoji rate
# ---------------------------------------------------------------------------

EMOJI_HEAVY = [
    "Great race! 🏊‍♀️🎉🏅",
    "PB for the squad! 🚀💥",
    "Unstoppable! 🔥🔥🔥",
]
EMOJI_FREE = [
    "Strong swim from the squad.",
    "County qualifier hit.",
    "Well done all.",
]


class TestEmojiCounting:
    def test_high_emoji_rate(self):
        stats = _compute_stats(EMOJI_HEAVY)
        assert stats["emoji_rate_per_caption"] >= 2.0

    def test_zero_emoji_rate(self):
        stats = _compute_stats(EMOJI_FREE)
        assert stats["emoji_rate_per_caption"] == 0.0


# ---------------------------------------------------------------------------
# Hashtag counting
# ---------------------------------------------------------------------------

HASHTAG_HEAVY = [
    "Great race! #swimming #pb #club #county",
    "Well done team! #swimming #competition",
    "Huge weekend! #swim #lifeinlanes #proud",
]
HASHTAG_FREE = [
    "Great swim from the squad.",
    "Well done everyone.",
    "Proud of this group.",
]


class TestHashtagCounting:
    def test_high_hashtag_avg(self):
        stats = _compute_stats(HASHTAG_HEAVY)
        assert stats["hashtag_count_avg"] >= 2.0

    def test_zero_hashtag_avg(self):
        stats = _compute_stats(HASHTAG_FREE)
        assert stats["hashtag_count_avg"] == 0.0


# ---------------------------------------------------------------------------
# analyse_examples — deterministic mode (LLM mocked out to nothing)
# ---------------------------------------------------------------------------

_NO_LLM_PATCH = mock.patch(
    "mediahub.brand.voice_imitation._llm_enrich",
    return_value={},
)


class TestAnalyseExamples:
    def test_returns_non_empty_dict(self):
        with _NO_LLM_PATCH:
            result = analyse_examples(SHORT_EXAMPLES + LONG_EXAMPLES)
        assert isinstance(result, dict)
        assert result  # non-empty

    def test_required_keys_present(self):
        with _NO_LLM_PATCH:
            result = analyse_examples(SHORT_EXAMPLES + LONG_EXAMPLES)
        for key in (
            "sentence_length_avg",
            "sentence_length_p90",
            "emoji_rate_per_caption",
            "hashtag_count_avg",
            "characteristic_openers",
            "characteristic_closers",
            "preferred_swimmer_address",
            "capitalisation_style",
        ):
            assert key in result, f"Missing key: {key}"

    def test_empty_input_returns_empty(self):
        with _NO_LLM_PATCH:
            result = analyse_examples([])
        assert result == {}

    def test_whitespace_only_returns_empty(self):
        with _NO_LLM_PATCH:
            result = analyse_examples(["", "   ", "\n"])
        assert result == {}

    def test_pii_not_in_output(self):
        examples = [
            "Huge PB for Sarah Johnson today!",
            "Well done Thomas Williams on that 200 free!",
            "Great swim from the squad at Manchester.",
        ]
        with _NO_LLM_PATCH:
            result = analyse_examples(examples)
        result_str = json.dumps(result)
        assert "Sarah Johnson" not in result_str
        assert "Thomas Williams" not in result_str

    def test_short_vs_long_sentence_len_differs(self):
        with _NO_LLM_PATCH:
            short_p = analyse_examples(SHORT_EXAMPLES * 3)
            long_p = analyse_examples(LONG_EXAMPLES * 3)
        assert long_p["sentence_length_avg"] > short_p["sentence_length_avg"]

    def test_emoji_rate_reflects_input(self):
        with _NO_LLM_PATCH:
            heavy = analyse_examples(EMOJI_HEAVY * 3)
            free = analyse_examples(EMOJI_FREE * 3)
        assert heavy["emoji_rate_per_caption"] > free["emoji_rate_per_caption"]

    def test_hashtag_avg_reflects_input(self):
        with _NO_LLM_PATCH:
            heavy = analyse_examples(HASHTAG_HEAVY * 3)
            free = analyse_examples(HASHTAG_FREE * 3)
        assert heavy["hashtag_count_avg"] > free["hashtag_count_avg"]


# ---------------------------------------------------------------------------
# ClubProfile backward compatibility
# ---------------------------------------------------------------------------

class TestClubProfileBackwardCompat:
    def test_old_profile_loads_with_defaults(self):
        old_data = {
            "profile_id": "legacy",
            "display_name": "Legacy Club",
            "brand_primary": "#FF0000",
        }
        p = ClubProfile.from_dict(old_data)
        assert p.voice_examples == []
        assert p.voice_profile == {}

    def test_round_trip_with_voice_fields(self):
        p = ClubProfile(
            profile_id="test",
            display_name="Test Club",
            voice_examples=["Great swim!", "Huge PB!"],
            voice_profile={"sentence_length_avg": 4.5, "emoji_rate_per_caption": 0.5},
        )
        d = p.to_dict()
        p2 = ClubProfile.from_dict(d)
        assert p2.voice_examples == ["Great swim!", "Huge PB!"]
        assert p2.voice_profile["sentence_length_avg"] == 4.5


# ---------------------------------------------------------------------------
# _voice_profile_instructions — system prompt injection
# ---------------------------------------------------------------------------

class TestVoiceProfileInstructions:
    def test_empty_profile_returns_empty(self):
        assert _voice_profile_instructions({}) == ""
        assert _voice_profile_instructions(None) == ""  # type: ignore[arg-type]

    def test_no_emoji_instruction_for_low_rate(self):
        vp = {"emoji_rate_per_caption": 0.0}
        instr = _voice_profile_instructions(vp)
        assert "no emoji" in instr.lower()

    def test_emoji_instruction_for_high_rate(self):
        vp = {"emoji_rate_per_caption": 3.0}
        instr = _voice_profile_instructions(vp)
        assert "emoji" in instr.lower()
        # Should not say "no emoji"
        assert "no emoji" not in instr.lower()

    def test_no_hashtag_instruction(self):
        vp = {"hashtag_count_avg": 0.0}
        instr = _voice_profile_instructions(vp)
        assert "hashtag" in instr.lower()
        assert "do not" in instr.lower() or "no" in instr.lower()

    def test_sentence_length_instruction(self):
        vp = {"sentence_length_avg": 8.0}
        instr = _voice_profile_instructions(vp)
        assert "8" in instr

    def test_forbidden_phrases_in_instructions(self):
        vp = {"forbidden_phrases": ["going forward", "unprecedented times"]}
        instr = _voice_profile_instructions(vp)
        assert "going forward" in instr
        assert "unprecedented times" in instr

    def test_opener_style_in_instructions(self):
        vp = {"characteristic_openers": ["Huge PB for", "What a race"]}
        instr = _voice_profile_instructions(vp)
        assert "Huge PB for" in instr

    def test_last_name_address(self):
        vp = {"preferred_swimmer_address": "last_name"}
        instr = _voice_profile_instructions(vp)
        assert "last name" in instr.lower() or "surname" in instr.lower()
