"""
brand/voice_imitation.py — Analyse past social posts → structured voice profile.

Public API
----------
analyse_examples(examples: list[str]) -> dict
    Compute deterministic stats (sentence length, emoji/hashtag counts) plus
    LLM-extracted qualitative patterns (openers, closers, forbidden phrases).
    Returns a dict suitable for ClubProfile.voice_profile.

_redact_pii(texts: list[str]) -> list[str]
    Strip obvious name-like tokens (Title Case pairs) before any storage.

Voice profile dict schema
-------------------------
{
    "sentence_length_avg": float,
    "sentence_length_p90": float,
    "emoji_rate_per_caption": float,
    "hashtag_count_avg": float,
    "characteristic_openers": list[str],     # first-line openers
    "characteristic_closers": list[str],     # last-line closers
    "forbidden_phrases": list[str],          # via LLM or empty
    "preferred_swimmer_address": str,        # first_name|last_name|surname_only|nickname
    "capitalisation_style": str,             # sentence|title|all_caps_emphasis
    "common_hashtags": list[str],
}
"""
from __future__ import annotations

import re
import statistics
from typing import Optional

# ---------------------------------------------------------------------------
# PII redaction — strip Title Case word pairs that look like personal names.
# This runs on the raw examples BEFORE any analysis so names don't leak into
# the saved voice_profile dict.
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"\b[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}\b")


def _redact_pii(texts: list[str]) -> list[str]:
    """Replace 'First Last' name-like patterns with '[NAME]'."""
    return [_NAME_RE.sub("[NAME]", t) for t in texts]


# ---------------------------------------------------------------------------
# Deterministic stat helpers — no LLM required.
# ---------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    r"["
    r"\U0001F300-\U0001FAFF"
    r"\U00002702-\U000027B0"
    r"\U000024C2-\U0001F251"
    r"\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF"
    r"\U00002500-\U00002BEF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FAFF"
    r"]",
    flags=re.UNICODE,
)
_HASHTAG_RE = re.compile(r"#\w+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _sentence_lengths(text: str) -> list[int]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        sentences = [text]
    return [len(s.split()) for s in sentences if s.split()]


def _compute_stats(texts: list[str]) -> dict:
    all_lengths: list[int] = []
    emoji_counts: list[int] = []
    hashtag_counts: list[int] = []
    openers: list[str] = []
    closers: list[str] = []

    for t in texts:
        # Sentence lengths
        all_lengths.extend(_sentence_lengths(t))

        # Emoji and hashtag counts per caption
        emoji_counts.append(len(_EMOJI_RE.findall(t)))
        hashtag_counts.append(len(_HASHTAG_RE.findall(t)))

        # Openers: first non-empty line, first 6 words
        lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
        if lines:
            words = lines[0].split()
            opener = " ".join(words[:6]).rstrip(".!?,;")
            if opener:
                openers.append(opener)

        # Closers: last non-hashtag, non-empty line
        for line in reversed(lines):
            if not re.fullmatch(r"#\w+(\s+#\w+)*", line):
                if len(line.split()) <= 12:
                    closers.append(line)
                break

    avg_len = round(statistics.mean(all_lengths), 2) if all_lengths else 0.0
    p90_len = round(
        sorted(all_lengths)[int(len(all_lengths) * 0.9)] if all_lengths else 0.0, 2
    )
    emoji_rate = round(statistics.mean(emoji_counts), 2) if emoji_counts else 0.0
    hashtag_avg = round(statistics.mean(hashtag_counts), 2) if hashtag_counts else 0.0

    # Deduplicate openers/closers — keep up to 6 distinct ones
    def _dedup(items: list[str], n: int) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.lower()[:40]
            if key not in seen:
                seen.add(key)
                out.append(item)
                if len(out) >= n:
                    break
        return out

    return {
        "sentence_length_avg": avg_len,
        "sentence_length_p90": p90_len,
        "emoji_rate_per_caption": emoji_rate,
        "hashtag_count_avg": hashtag_avg,
        "characteristic_openers": _dedup(openers, 6),
        "characteristic_closers": _dedup(closers, 4),
    }


def _capitalisation_style(texts: list[str]) -> str:
    all_caps = 0
    title_caps = 0
    total = 0
    for t in texts:
        for w in t.split():
            clean = re.sub(r"[^A-Za-z]", "", w)
            if not clean:
                continue
            total += 1
            if clean.isupper() and len(clean) > 1:
                all_caps += 1
            elif clean[0].isupper() and not clean.isupper():
                title_caps += 1
    if total == 0:
        return "sentence"
    if all_caps / total > 0.08:
        return "all_caps_emphasis"
    if title_caps / total > 0.35:
        return "title"
    return "sentence"


def _common_hashtags(texts: list[str], top_n: int = 8) -> list[str]:
    from collections import Counter
    counter: Counter = Counter()
    for t in texts:
        for tag in _HASHTAG_RE.findall(t):
            counter[tag.lower()] += 1
    return [tag for tag, _ in counter.most_common(top_n)]


def _preferred_swimmer_address(texts: list[str]) -> str:
    """Heuristic: infer preferred name style from name-pattern frequency."""
    full_name_re = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")
    initial_re = re.compile(r"\b[A-Z]\. [A-Z][a-z]+\b")
    full_count = sum(len(full_name_re.findall(t)) for t in texts)
    initial_count = sum(len(initial_re.findall(t)) for t in texts)
    if initial_count > full_count and initial_count > 0:
        return "last_name"
    if full_count > 2:
        return "first_name"
    return "first_name"


# ---------------------------------------------------------------------------
# LLM enrichment (qualitative patterns) — optional; safe to skip.
# ---------------------------------------------------------------------------

def _llm_enrich(texts: list[str]) -> dict:
    """Ask the LLM for forbidden_phrases and opening phrase archetypes."""
    try:
        from mediahub.media_ai.llm import generate_json
    except ImportError:
        return {}

    sample = "\n---\n".join(texts[:12])
    prompt = (
        "You are analysing social media captions to extract style patterns.\n\n"
        "Here are example captions:\n\n"
        f"{sample}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '- "forbidden_phrases": list of 3-6 phrases or patterns this brand NEVER uses '
        "(based on what is conspicuously absent or tonally wrong — be specific).\n"
        '- "opening_archetypes": list of 3-5 short templates that capture how these captions '
        'typically open (e.g. "Huge congratulations to [NAME]", "What a weekend for [TEAM]").\n\n'
        "Respond with only the JSON object."
    )
    try:
        result = generate_json(prompt, max_tokens=400)
        if not isinstance(result, dict):
            return {}
        return {
            "forbidden_phrases": [str(p) for p in result.get("forbidden_phrases", [])[:6]],
            "opening_archetypes": [str(p) for p in result.get("opening_archetypes", [])[:5]],
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_examples(examples: list[str]) -> dict:
    """
    Analyse 5-20 past social-media captions and produce a structured voice profile.

    Always returns a non-empty dict (graceful degradation if LLM unavailable).
    Does NOT store raw example texts — computed fields only.
    """
    clean = [e.strip() for e in examples if e and e.strip()]
    if not clean:
        return {}

    # Redact PII before any processing
    redacted = _redact_pii(clean)

    stats = _compute_stats(redacted)
    cap_style = _capitalisation_style(redacted)
    hashtags = _common_hashtags(redacted)
    address = _preferred_swimmer_address(clean)  # use pre-redaction for heuristic

    # LLM enrichment (best-effort; falls back to empty if unavailable)
    llm_data = _llm_enrich(redacted)

    profile: dict = {
        **stats,
        "capitalisation_style": cap_style,
        "common_hashtags": hashtags,
        "preferred_swimmer_address": address,
        "forbidden_phrases": llm_data.get("forbidden_phrases", []),
        "opening_archetypes": llm_data.get("opening_archetypes", []),
    }
    return profile


__all__ = ["analyse_examples", "_redact_pii"]
