"""brand/context.py — single canonical brand briefing for content tools.

Every generator on the site (captions, Turn-Into, weekend recap, athlete
spotlights, motion compositions, etc.) must speak in the organisation's
voice. Rather than each generator duplicating the logic for assembling
that voice from the various ClubProfile fields, they all call:

    brand_context_for_llm(profile) -> str

and prepend the returned string to their LLM system prompt. The returned
prose unifies four sources of brand truth:

  1. Identity fields (display_name, country, governing_body, sponsor)
  2. Captured brand DNA from website / social ingestion
     (brand_voice_summary, brand_phrases_to_use, brand_phrases_to_avoid,
      brand_keywords, brand_palette_extracted)
  3. Voice profile from past captions (sentence length, emoji rate,
     opener/closer style, preferred swimmer address)
  4. AI-interpreted brand guidelines document (voice_attributes,
     tone_dos, tone_donts, prohibited_words, preferred_terminology,
     hashtag_rules, sponsor_mention_rules, key_messages)

This is intentionally string-based, not a structured prompt object —
LLMs absorb natural-language guidance well, and a single function makes
it trivial to add to any new tool.
"""
from __future__ import annotations

from typing import Any


def _get(profile, name: str, default: Any = None) -> Any:
    if profile is None:
        return default
    if isinstance(profile, dict):
        return profile.get(name, default)
    return getattr(profile, name, default)


def _identity_prose(profile) -> str:
    name = (_get(profile, "display_name") or "").strip()
    if not name:
        return ""
    short = (_get(profile, "short_name") or "").strip()
    governing = (_get(profile, "governing_body") or "").strip()
    country = (_get(profile, "country") or "").strip()
    sponsor = (_get(profile, "sponsor_name") or "").strip()
    bits = [f"You are writing for **{name}**"]
    if short and short.lower() != name.lower():
        bits[-1] += f" (also known as {short})"
    if governing or country:
        loc = ", ".join(p for p in (governing, country) if p)
        bits[-1] += f" — affiliated with {loc}"
    bits[-1] += "."
    if sponsor:
        bits.append(f"Primary sponsor: {sponsor}.")
    return " ".join(bits)


def _dna_prose(profile) -> str:
    summary = (_get(profile, "brand_voice_summary") or "").strip()
    keywords = list(_get(profile, "brand_keywords") or [])[:10]
    use = list(_get(profile, "brand_phrases_to_use") or [])[:6]
    avoid = list(_get(profile, "brand_phrases_to_avoid") or [])[:6]
    bits: list[str] = []
    if summary:
        bits.append("About the organisation (from their website / social presence): "
                    + summary)
    if keywords:
        bits.append("Words and themes the organisation uses about itself: "
                    + ", ".join(keywords) + ".")
    if use:
        bits.append("Phrases that sound like them: "
                    + "; ".join(f'"{p}"' for p in use) + ".")
    if avoid:
        bits.append("Phrases that would feel off-brand — never use: "
                    + "; ".join(f'"{p}"' for p in avoid) + ".")
    return " ".join(bits)


def _voice_profile_prose(profile) -> str:
    vp = _get(profile, "voice_profile") or {}
    if not isinstance(vp, dict) or not vp:
        return ""
    bits: list[str] = ["Voice profile (learned from this club's actual past captions):"]
    avg = vp.get("sentence_length_avg")
    if avg:
        try:
            bits.append(f"Aim for sentences of about {int(round(float(avg)))} words on average.")
        except (TypeError, ValueError):
            pass
    er = vp.get("emoji_rate_per_caption")
    if er is not None:
        try:
            r = float(er)
            if r <= 0.1:
                bits.append("This club does NOT use emoji.")
            elif r < 1.0:
                bits.append("Use emoji sparingly — at most one per caption.")
            else:
                bits.append(f"This club typically uses around {r:.1f} emoji per caption.")
        except (TypeError, ValueError):
            pass
    ha = vp.get("hashtag_count_avg")
    if ha is not None:
        try:
            n = int(round(float(ha)))
            if n <= 0:
                bits.append("Do NOT use hashtags.")
            else:
                bits.append(f"Use about {n} hashtag{'s' if n != 1 else ''}.")
        except (TypeError, ValueError):
            pass
    addr = vp.get("preferred_swimmer_address")
    addr_map = {
        "first_name":   "Address swimmers by first name only.",
        "last_name":    "Use the swimmer's full name with surname.",
        "surname_only": "Use the swimmer's surname only (broadcast style).",
        "nickname":     "Address swimmers familiarly, nickname-style.",
    }
    if isinstance(addr, str) and addr in addr_map:
        bits.append(addr_map[addr])
    openers = vp.get("characteristic_openers") or []
    if openers:
        bits.append("Typical openers: " + ", ".join(f'"{o}"' for o in openers[:4]) + ".")
    closers = vp.get("characteristic_closers") or []
    if closers:
        bits.append("Typical closers: " + ", ".join(f'"{c}"' for c in closers[:4]) + ".")
    forbidden = vp.get("forbidden_phrases") or []
    if forbidden:
        bits.append("Phrases to avoid (learned): "
                    + ", ".join(f'"{p}"' for p in forbidden[:5]) + ".")
    common_hash = vp.get("common_hashtags") or []
    if common_hash:
        bits.append("Hashtags they commonly use: " + ", ".join(common_hash[:6]) + ".")
    return " ".join(bits) if len(bits) > 1 else ""


def _guidelines_prose(profile) -> str:
    g = _get(profile, "brand_guidelines") or {}
    if not isinstance(g, dict) or not g:
        return ""
    bits: list[str] = []
    summary = (g.get("summary") or "").strip()
    if summary:
        bits.append("Brand guidelines (from the organisation's uploaded style document): "
                    + summary)
    attrs = g.get("voice_attributes") or []
    if attrs:
        bits.append("Voice should feel: " + ", ".join(attrs) + ".")
    dos = g.get("tone_dos") or []
    if dos:
        bits.append("DO: " + " · ".join(dos) + ".")
    donts = g.get("tone_donts") or []
    if donts:
        bits.append("DO NOT: " + " · ".join(donts) + ".")
    prohibited = g.get("prohibited_words") or []
    if prohibited:
        bits.append("Prohibited words/phrases — never use these even in paraphrase: "
                    + ", ".join(f'"{w}"' for w in prohibited[:15]) + ".")
    pref = g.get("preferred_terminology") or {}
    if isinstance(pref, dict) and pref:
        pairs = ", ".join(f'"{k}" → "{v}"' for k, v in list(pref.items())[:10])
        bits.append("Replace the left term with the right term: " + pairs + ".")
    audience = (g.get("audience") or "").strip()
    if audience:
        bits.append("Audience: " + audience + ".")
    hashtag_rules = (g.get("hashtag_rules") or "").strip()
    if hashtag_rules:
        bits.append("Hashtag rules: " + hashtag_rules)
    sponsor_rules = (g.get("sponsor_mention_rules") or "").strip()
    if sponsor_rules:
        bits.append("Sponsor mention rules: " + sponsor_rules)
    key_msgs = g.get("key_messages") or []
    if key_msgs:
        bits.append("Recurring key messages to weave in where appropriate: "
                    + " · ".join(key_msgs[:5]) + ".")
    return " ".join(bits)


def brand_context_for_llm(profile) -> str:
    """Return a single coherent system-prompt block describing the
    organisation's brand identity, voice, captured DNA, and uploaded
    guidelines. Empty string when nothing is known.

    Every content generator should prepend this to its system prompt:

        system = brand_context_for_llm(profile) + "\\n\\n" + tool_system

    The returned text is plain prose — safe to drop into any LLM
    system message without further escaping.
    """
    if profile is None:
        return ""
    sections = [
        _identity_prose(profile),
        _dna_prose(profile),
        _voice_profile_prose(profile),
        _guidelines_prose(profile),
    ]
    sections = [s for s in sections if s]
    if not sections:
        return ""
    return "\n\n".join(sections)


__all__ = ["brand_context_for_llm"]
