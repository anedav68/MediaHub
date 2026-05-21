# Generative Content Engine v2 — Roadmap & Build Prompts

**What this is.** An execution roadmap that turns the recommendations in
`docs/research/mediahub-generative-ai-thesis.md` and
`docs/research/generation-engine-competitor-evaluation.md` into ordered,
runnable build stages — *taking the advice in those documents as fact* — with an
implementation prompt and a verification prompt for every stage, and a separate
**parallel bucket** of work that can be run right now, simultaneously, in
different Claude sessions and merged to `main` in any order without conflicts.

**Date:** May 2026 · **Built against:** `main` after PR #137 (the trimmed
CLAUDE.md with the *gated removal process*) and PR #136 (the research docs).

**The problem being solved (from the thesis).** "Click generate" selects a tuple
from a bounded, hand-authored option space dominated by ~6 layout skeletons, with
an LLM constrained to *menu-pick* from fixed enums (`creative_brief/ai_director.py`)
and a renderer that repaints one DOM (`graphic_renderer/render.py`). The fix is to
replace the variation mechanism with: a **brand-token contract** → an **archetype
library + layout intelligence** (Tier A) → an **LLM design-spec director** (Tier B)
→ **generate-a-pool, rank, and compliance-check**, while keeping the deterministic
engine, the captions, Remotion, and the renderer substrate.

---

## 0. How to use this document

There are **two tracks**:

- **The Parallel Bucket (§2)** — additive, file-disjoint work that does **not**
  affect the build because each item ships *new, inert files* (or owns one
  isolated surface). These can be run **now**, each in its own Claude session,
  each on its own branch → PR to `main`. They are wired into the live pipeline
  later by the spine. **Run these first / concurrently.**
- **The Sequential Spine (§3)** — build-order-dependent work that modifies the
  shared files (`generator.py`, `ai_director.py`, `render.py`,
  `content_pack_visual/integration.py`, the `web.py` route) and *wires in* the
  parallel modules. These must be done in order, behind the `MEDIAHUB_GEN_V2`
  flag, and the removal stage follows CLAUDE.md's gated-removal process.

Each stage has a **Context** (what/why + files + thesis ref), an **Implementation
prompt** (paste into a fresh session), and a **Verification prompt** (paste into a
*separate* session to confirm it was done properly).

### Relationship to the in-flight Adaptive Theming Engine (ROADMAP 1.6)

Do **not** rebuild the brand-token system. ROADMAP §1.6 already delivers the
DTCG-format `derived_palette`, ~25 MD3 role tokens, and a single-source-of-truth
JSON consumed by web/motion/email/graphic (Stage G). The thesis's "Layer 1 — brand
token contract" is **mostly that work, extended** with three generation-specific
additions (logo lockups by theme/form, type pairing, a structured voice profile,
and *semantic role descriptions an LLM can read*). SEQ-0 below extends the theming
token object; it does not duplicate it. If 1.6 Stage G is not yet merged, SEQ-0
coordinates with it rather than forking it.

---

## 1. The shared prompt preamble (every prompt inherits this)

To keep each prompt short, every Implementation and Verification prompt below
**assumes this preamble**. Paste it at the top of the session if the model hasn't
read the repo yet:

> **Preamble — read before doing anything.** You are working in the MediaHub repo
> (`/home/user/MediaHub` or the session's checkout). Read `CLAUDE.md` in full, plus
> `docs/research/mediahub-generative-ai-thesis.md` (the plan) and the file(s) named
> in the task. Hard rules you must follow:
> - **Deterministic engine is off-limits to AI:** never Gemini-ify parsers
>   (`interpreter/`, `pb_discovery/`), detectors (`recognition*/`), the ranker
>   (`legacy/swim_content_v5/ranker_v3.py`), or colour-science (`theming/`,
>   CIEDE2000/APCA). You may *read* their outputs.
> - **Honest error, never a fake fallback:** if an AI provider is unavailable,
>   surface `ProviderNotConfigured`/`ClaudeUnavailableError` or fall back to a
>   *real deterministic* path — never a fabricated caption/graphic.
> - **Judgement goes through `media_ai.llm` / `ai_core.llm`** — never new hardcoded
>   heuristics for "which layout / which copy / which tone."
> - **Removing or replacing a route or data structure** requires CLAUDE.md's
>   *15-step breakage check before* + *15-step verification after* + a *dead-code
>   sweep*. Do not skip it.
> - **Tests:** run `python -m pytest tests/ -q` and add tests for new code; there
>   must be **no new failures** vs `main`, and you must not delete/skip/weaken a
>   test to go green.
> - **Branch & ship:** create a feature branch `claude/<short-name>`, commit with a
>   clear message, push, and **open a PR** (do not merge to `main` without the
>   user's approval — the user merges).
> - **Scope discipline:** touch only the files this task names. If you find you need
>   to modify a file the task says not to touch, stop and report instead.

---

## 2. The Parallel Bucket — run these now, concurrently, one session each

**Why these are safe to run simultaneously and merge in any order:** every item
below either creates **only new files** (inert — nothing imports them yet, so the
build is unaffected) or owns a **single isolated surface** that no other item and
no spine stage touches. The "Files you may touch" / "Files you must NOT touch"
lists guarantee no two parallel PRs edit the same file. Merge them to `main` in any
order; the spine (§3) wires them in afterward.

> **Conflict-safety contract (applies to every PAR item):** You may create/modify
> **only** the files listed under "Owns." You must **NOT** touch `web/web.py`,
> `creative_brief/generator.py`, `creative_brief/ai_director.py`,
> `graphic_renderer/render.py`, or `content_pack_visual/integration.py` (those are
> spine files). Your change must leave the existing build and tests green on its own.

### PAR-1 · Caption quality pack
**Owns:** `src/mediahub/web/ai_caption.py` (the only item that touches it) + new
`src/mediahub/web/caption_examples.py` + `tests/test_caption_quality.py`.
**Context:** Captions are already strong (thesis §5.6); this adds the verified
brand-voice recipe. Independent of the graphic surgery.

**Implementation prompt:**
> [Preamble.] Extend MediaHub's caption generation (`web/ai_caption.py`) with the
> brand-voice recipe from thesis §5.6, all inside the existing Gemini→Anthropic
> path. Add: (1) **few-shot injection** — accept up to 5 of the club's own past
> captions and inject them verbatim as examples in the system prompt (store/read
> them via a new `web/caption_examples.py` keyed by `profile_id`, persisted under
> `DATA_DIR`); (2) **generate-many-then-dedupe** — generate 4–6 candidates and
> return them ranked, dropping any whose n-gram/embedding similarity to a recent
> caption or to each other is above a threshold; (3) **per-platform variants** —
> given one approved caption, produce feed / story / X / LinkedIn variants with
> per-platform length+tone constraints; (4) an explicit **AI-tell ban-list**
> ("delve", "elevate", "in the world of", reflexive "!"); (5) an **approval-loop**
> hook: a function that appends an edited+approved caption to the club's
> few-shot example store. Keep the existing function signatures working
> (additive params with defaults). Add `tests/test_caption_quality.py` covering
> dedupe, ban-list filtering, and few-shot injection (mock the LLM). Do NOT touch
> any spine file. Branch `claude/gen-par-1-captions`, test, open a PR.

**Verification prompt:**
> [Preamble.] Verify PAR-1 (caption quality pack) was done properly. Confirm:
> only `web/ai_caption.py`, `web/caption_examples.py`, and the new test were
> changed (no spine files); the existing caption route still works with the new
> defaults; few-shot examples are injected and capped at 5; dedupe actually drops
> near-duplicates; the ban-list filters the listed phrases; the approval-loop
> appends to the store; captions still raise an honest error (no fabricated
> fallback) when no provider is configured. Run the full suite — no new failures.
> Report a pass/fail checklist.

### PAR-2 · Auto-fit text helper (standalone, inert)
**Owns:** new `src/mediahub/graphic_renderer/autofit.py` + `tests/test_autofit.py`.
**Context:** Bannerbear's verified core feature (eval §6.1). A pure function that
computes the font-size (px) that fits a string into a given box at a given
font/weight, so long names/events never break a layout. Inert until SEQ-1 calls it.

**Implementation prompt:**
> [Preamble.] Create `graphic_renderer/autofit.py`: a pure, deterministic helper
> `fit_font_px(text, box_w, box_h, *, font_family, weight, min_px, max_px,
> line_height) -> int` that returns the largest integer px size at which `text`
> fits within `box_w × box_h` (binary search; approximate advance-width via a
> char-width table or Pillow `ImageFont.getbbox` if a font file is available, else
> a metric heuristic — but keep it deterministic and documented). Add helpers for
> multi-line wrapping. No network, no LLM (this is layout maths, not judgement).
> Add `tests/test_autofit.py` with golden cases (short vs very long swimmer names,
> narrow vs wide boxes). Create ONLY these two files. Branch
> `claude/gen-par-2-autofit`, test, open a PR.

**Verification prompt:**
> [Preamble.] Verify PAR-2: only `graphic_renderer/autofit.py` and its test were
> added; `fit_font_px` is deterministic (same inputs → same output), monotonic
> (a longer string never returns a larger size for the same box), respects
> min/max bounds, and has no LLM/network calls. Run the suite — no new failures.

### PAR-3 · Saliency-aware crop helper (standalone, inert)
**Owns:** new `src/mediahub/graphic_renderer/saliency.py` + `tests/test_saliency.py`.
**Context:** Subject-aware crops (eval §6.1, thesis §5.3.1) so one archetype looks
correct and different with every photo. Deterministic maths (consistent with the
colour-science rule). Inert until SEQ-1 calls it.

**Implementation prompt:**
> [Preamble.] Create `graphic_renderer/saliency.py`: deterministic helpers that,
> given an image path, return candidate crop rectangles for a set of target aspect
> ratios (e.g. `9:16`, `1:1`, `4:5`) using a saliency/energy heuristic (e.g.
> gradient-magnitude / edge density via Pillow+numpy, or reuse the existing cutout
> alpha if present to bias toward the subject). Expose
> `crops_for(image_path, ratios) -> dict[ratio, (x,y,w,h)]` and a
> `best_crop(image_path, ratio)`. No LLM, no network. Add `tests/test_saliency.py`
> with a couple of synthetic images (subject in different corners) asserting the
> crop tracks the subject and stays within bounds. Create ONLY these two files.
> Branch `claude/gen-par-3-saliency`, test, open a PR.

**Verification prompt:**
> [Preamble.] Verify PAR-3: only the saliency module + test were added; crops are
> deterministic, stay within image bounds, match the requested aspect ratios, and
> track the subject on the synthetic fixtures; no LLM/network. Suite green.

### PAR-4 · Design-spec schema + validator (the Tier B contract, inert)
**Owns:** new `src/mediahub/creative_brief/design_spec.py` + `tests/test_design_spec.py`.
**Context:** The structured JSON contract the LLM art-director will emit (thesis
§5.4). Defining it as a standalone schema + normaliser now lets SEQ-2 just call it.
Inert until the director uses it.

**Implementation prompt:**
> [Preamble.] Create `creative_brief/design_spec.py` defining the `DesignSpec`
> dataclass and a strict `normalise(raw: dict, *, archetypes: list[str],
> token_roles: list[str]) -> DesignSpec` that coerces a (possibly hallucinated)
> LLM JSON object into a valid spec — every field constrained to a known enum or a
> token *role* name, with safe defaults on any out-of-vocabulary value (so a bad
> LLM response can never produce an illegal/illegible card). Fields per thesis
> §5.4: `archetype`, `colour_roles` (ground/surface/headline/accent → role names),
> `focal_element`, `crop_intent`, `hero_stat`, `secondary_stats`, `headline_hook`,
> `accent_treatment`, `logo_lockup`, `mood`, `motion_intent`, `rationale`. Provide
> the JSON-schema dict for schema-constrained decoding. No live LLM call here — this
> is the contract + validator only. Add `tests/test_design_spec.py` (valid spec
> round-trips; hallucinated/garbage values normalise to defaults; enums enforced).
> Create ONLY these two files. Branch `claude/gen-par-4-design-spec`, test, PR.

**Verification prompt:**
> [Preamble.] Verify PAR-4: only the design_spec module + test were added; an
> out-of-vocabulary value for every field normalises to a safe default; the schema
> dict matches the dataclass; no card-illegal spec can be produced. Suite green.

### PAR-5 · Variant metrics module (success-metric instrumentation, inert)
**Owns:** new `src/mediahub/quality/variant_metrics.py` + `tests/test_variant_metrics.py`.
**Context:** Thesis §8C success metrics — archetype diversity and perceptual
distance across a candidate pool. Standalone scoring lib; inert until SEQ-2 wires it.

**Implementation prompt:**
> [Preamble.] Create a new `quality/` package with `variant_metrics.py`:
> deterministic functions `archetype_diversity(specs) -> float` (distinct
> archetypes / candidates) and `perceptual_spread(png_paths) -> float` (mean
> pairwise distance using a cheap perceptual hash or downscaled-LAB histogram
> distance — no heavy ML). Add `caption_repetition(captions) -> float` (max n-gram
> overlap). These power the §8C targets. No LLM/network. Add
> `tests/test_variant_metrics.py`. Create ONLY the new package files + test.
> Branch `claude/gen-par-5-metrics`, test, PR.

**Verification prompt:**
> [Preamble.] Verify PAR-5: only the new `quality/` module + test were added;
> metrics are deterministic and bounded; diversity rises with distinct archetypes;
> spread rises with visually different PNGs. Suite green.

### PAR-6 · Brand bootstrap extractor (draft from a URL, inert)
**Owns:** new `src/mediahub/brand/bootstrap_extract.py` + `tests/test_bootstrap_extract.py`.
**Context:** "Paste your club URL → draft brand kit" onboarding (thesis §5.3),
modelled on Brandfetch's schema. A pure extractor that returns a **draft**
DesignTokens dict (for human confirmation — never auto-trusted). It may *read* the
existing `brand/link_handlers/` but must not modify them or add a route (wiring is
SEQ work). Inert until onboarding calls it.

**Implementation prompt:**
> [Preamble.] Create `brand/bootstrap_extract.py`: `extract_brand_draft(url) ->
> dict` returning a *draft* token set (palette candidates with semantic guesses,
> logo URLs by inferred form, font guesses) shaped like the DesignTokens contract,
> reusing existing `brand/link_handlers/` for fetching where possible (read-only
> import). Mark every field `"confirmed": false`. No route, no web.py edit, no
> auto-apply. Honest about uncertainty (small-club extraction is unreliable — return
> confidence flags, never silently guess). Add `tests/test_bootstrap_extract.py`
> (mock the fetch; assert draft shape + all `confirmed:false`). Create ONLY these
> two files. Branch `claude/gen-par-6-brand-bootstrap`, test, PR.

**Verification prompt:**
> [Preamble.] Verify PAR-6: only the extractor + test were added; no route/web.py
> change; output is a draft (all `confirmed:false`), shaped like DesignTokens; the
> existing `link_handlers` were imported, not modified. Suite green.

### PAR-7 · Archetype templates (the fan-out item — one session per archetype)
**Owns (per session):** ONE new file `src/mediahub/graphic_renderer/layouts/v2/<name>.html`
(+ optional `<name>.notes.md`). Run this prompt N times in N sessions, once per
archetype name — each writes a *different* file, so they never conflict.
**Context:** The structural variety the 6 families lack (thesis §5.3.1). Author
each against the **slot convention** below so SEQ-1 can wire them uniformly.

**Slot convention (author against this exactly):** use `{{PLACEHOLDER}}` string
substitution (not Jinja), and reference brand colours **only** via CSS custom
properties (`var(--mh-primary)`, `var(--mh-on-primary)`, `var(--mh-surface)`,
`var(--mh-on-surface)`, `var(--mh-accent)`, `var(--mh-outline)`) — never hardcode a
hex. Available text placeholders: `{{ATHLETE_FULL_NAME}}`, `{{ATHLETE_FIRST_NAME}}`,
`{{ATHLETE_SURNAME_DISPLAY}}`, `{{EVENT_NAME}}`, `{{RESULT_VALUE}}`,
`{{ACHIEVEMENT_LABEL}}`, `{{MEET_NAME}}`, `{{CLUB_FULL}}`, `{{HERO_STAT}}`,
`{{LOGO_BLOCK}}`, `{{ATHLETE_IMG_BLOCK}}`, `{{ACCENT_DECORATION}}`,
`{{SPONSOR_BLOCK}}`. Canvas is `{{WIDTH}}×{{HEIGHT}}`. Include `{{BASE_CSS}}` at the
top. The archetype must read *structurally distinct* from `individual_hero` /
`big_number_hero` at a glance.

**Suggested archetype names (assign one per session):** `split_diagonal_hero`,
`full_bleed_photo_lower_third`, `editorial_numbers_grid`, `centered_medal_spotlight`,
`magazine_cover`, `ticker_strip`, `stat_stack_sidebar`, `triptych_progression`,
`quote_led_recap`, `big_number_dominant`, `duo_athlete_split`, `minimal_type_poster`.

**Implementation prompt (template — fill in `<NAME>`):**
> [Preamble.] Author ONE new graphic archetype `graphic_renderer/layouts/v2/<NAME>.html`
> following the slot convention in `docs/generation_engine_roadmap.md` §PAR-7
> exactly (CSS-variable colours only, the listed `{{PLACEHOLDERS}}`, `{{BASE_CSS}}`
> at top). It must be a *structurally distinct* portrait layout (1080×1350 and
> 1080×1920 must both read well) — a genuinely different composition from the
> existing families, not a reskin. Self-contained HTML/CSS; no JS, no network, no
> hex literals. Add a one-paragraph `<NAME>.notes.md` describing the composition and
> when the director should pick it. Create ONLY those file(s) under `layouts/v2/`.
> Do not touch `render.py` or any other file. Branch `claude/gen-par-7-<NAME>`,
> commit, open a PR. (You cannot fully render-test it until SEQ-1 wires `layouts/v2`;
> instead, validate the HTML is well-formed and every placeholder/variable matches
> the convention.)

**Verification prompt:**
> [Preamble.] Verify a PAR-7 archetype: exactly one new `layouts/v2/<NAME>.html`
> (+ notes) was added; it uses ONLY CSS-variable colours (grep for `#` hex literals
> → none in colour positions); every placeholder is on the §PAR-7 allow-list;
> `{{BASE_CSS}}` is present; the layout is structurally distinct from the existing
> families; no other file changed. Suite green (these files are inert, so the suite
> is unaffected — confirm that too).

### PAR-8 · Documentation + ADR (pure docs, inert)
**Owns:** new `docs/GENERATION.md` + `docs/adr/0001-generation-engine-v2.md`.
**Context:** Single canonical doc for the new engine + an architecture-decision
record. Pure docs; conflicts with nothing.

**Implementation prompt:**
> [Preamble.] Author `docs/GENERATION.md` documenting the v2 generation
> architecture from thesis §5 (the token contract, archetype library, design-spec
> director, pool/rank/compliance, captions, video), the `layouts/v2` slot
> convention (copy it from this roadmap §PAR-7), and the `MEDIAHUB_GEN_V2` flag.
> Also author `docs/adr/0001-generation-engine-v2.md` recording the decision to
> replace the enum-permutation/menu-picker engine with the design-spec director
> (context, decision, alternatives rejected per thesis §4A, consequences). Docs
> only. Branch `claude/gen-par-8-docs`, open a PR.

**Verification prompt:**
> [Preamble.] Verify PAR-8: only the two docs were added; `GENERATION.md` matches
> thesis §5 and the §PAR-7 slot convention; the ADR records context/decision/
> alternatives/consequences. No code changed.

---

## 3. The Sequential Spine — build in order, behind `MEDIAHUB_GEN_V2`

These stages modify the shared spine files and wire in the parallel modules. They
**cannot** run concurrently with each other (they touch the same files); run them
in order, each as its own PR, after the parallel bucket is merged. Everything that
changes live behaviour is gated by the `MEDIAHUB_GEN_V2` feature flag until SEQ-3's
cutover, so production never regresses.

### SEQ-0 · DesignTokens contract + feature-flag scaffolding
**Depends on:** ROADMAP §1.6 Stage G (DTCG `derived_palette` JSON) if merged; else
coordinate. **Touches:** `brand/kit.py`, a new `config`/flag read, `theming/` (read).
**Thesis ref:** §5.3.

**Implementation prompt:**
> [Preamble.] Extend the brand token object (`brand/kit.py` / the theming
> `derived_palette`) into the generation **DesignTokens contract** from thesis §5.3,
> *additively* — keep the existing flat `primary_colour`/`secondary_colour`/
> `accent_colour` as derived aliases so nothing breaks. Add: semantic colour
> **roles** with `brightness` + `when_to_use` text (reuse the existing APCA/ΔE2000
> numbers from `theming/`), **logo lockups** typed by `form`
> (icon/horizontal/stacked/mono) and `theme` (light/dark) — extend
> `theming/logo_chip.py` to *select* the lockup for a given background — a typed
> `type` pairing, and a structured `voice` profile (examples, banned phrases, emoji
> policy) that the caption store (PAR-1) can populate. Add a `MEDIAHUB_GEN_V2`
> feature flag read (env, default off) and a single helper
> `resolve_design_tokens(profile_id) -> dict` that returns the full contract with
> the semantic role descriptions an LLM can consume. No behaviour change yet (flag
> off). This is additive — the gated-removal process is NOT needed here. Add tests
> for `resolve_design_tokens`. Branch `claude/gen-seq-0-tokens`, test, PR.

**Verification prompt:**
> [Preamble.] Verify SEQ-0: the old flat BrandKit fields still resolve (back-compat
> alias); `resolve_design_tokens` returns roles with `brightness`+`when_to_use`,
> logo lockups by form/theme, type pairing, and a voice profile; `logo_chip` selects
> a lockup per background; the `MEDIAHUB_GEN_V2` flag exists and defaults off; old
> persisted profiles still load. Suite green (no new failures); the change is purely
> additive (no removals).

### SEQ-1 · Tier A — archetype library + layout intelligence (the immediate fix)
**Depends on:** SEQ-0, PAR-2 (autofit), PAR-3 (saliency), PAR-7 (archetypes),
optionally PAR-6. **Touches:** `graphic_renderer/render.py`,
`creative_brief/generator.py`, `legacy/swim_content_v5/ranker_v3.py` (read-only
addition). **Thesis ref:** §5.3.1. **This stage alone is expected to fix "samey."**

**Implementation prompt:**
> [Preamble.] Implement Tier A (thesis §5.3.1), gated behind `MEDIAHUB_GEN_V2`.
> (1) Teach `graphic_renderer/render.py` to load archetypes from
> `graphic_renderer/layouts/v2/*.html` (the PAR-7 files) using the documented slot
> convention, resolving colours from the DesignTokens roles (SEQ-0) as CSS
> variables. (2) Wire in `autofit.fit_font_px` (PAR-2) for headline/name/event
> slots so long strings never overflow. (3) Wire in `saliency.best_crop` (PAR-3) so
> the athlete photo is cropped per the archetype's `crop_intent`. (4) In
> `creative_brief/generator.py`, add a **deterministic archetype-picker** (seeded by
> the existing `auto_variation_seed_for`, stable per card, different across cards)
> that selects among the v2 archetypes — this is the no-AI fallback floor. (5)
> Expose, *read-only*, the ranker's ranked **emphasis angles** (lead with time / PB
> delta / placing / relay split) so the brief can vary the hero stat — do NOT change
> the ranker's scoring. With the flag ON, a content pack should use ≥6 distinct
> archetypes. Add tests asserting archetype diversity across a pack and that autofit
> prevents overflow. Branch `claude/gen-seq-1-tier-a`, test, PR.

**Verification prompt:**
> [Preamble.] Verify SEQ-1: with `MEDIAHUB_GEN_V2=1`, rendering a pack uses ≥6
> distinct v2 archetypes; with the flag OFF, behaviour is unchanged (old engine).
> Long swimmer names/events no longer overflow (autofit); photo crops track the
> subject (saliency); the ranker's *scoring is byte-identical* to before (only a
> read-only emphasis-angle accessor was added — confirm no PB/ranking regression per
> CLAUDE.md engine rule). Walk upload→process→review with the flag on; cards render,
> captions/confidence intact. Suite green. Report the archetype-diversity number.

### SEQ-2 · Tier B — design-spec director + pool, rank, compliance
**Depends on:** SEQ-1, PAR-4 (design_spec), PAR-5 (variant_metrics). **Touches:**
`creative_brief/ai_director.py`, `content_pack_visual/integration.py`,
`web/web.py` (the create-graphic route response). **Thesis ref:** §5.4–5.5.

**Implementation prompt:**
> [Preamble.] Implement Tier B (thesis §5.4–5.5), gated behind `MEDIAHUB_GEN_V2`.
> (1) Rewrite `ai_director.ai_creative_direction` to emit a **DesignSpec** (use
> `creative_brief/design_spec.py` from PAR-4) under JSON-schema-constrained decoding
> via `ai_core` — the LLM now chooses archetype, colour-role assignment, focal
> element, hero stat (from the ranker's emphasis list), generated hook, crop intent,
> accent, logo lockup, mood, and a `rationale` (which feeds the existing "why this
> design" explainability). Keep the SEQ-1 deterministic archetype-picker as the
> fallback floor when no provider is configured (honest error / real floor — never a
> fabricated card). (2) In `content_pack_visual/integration.py`, emit **N candidate
> specs** (default 5), render the pool (cheap — Playwright), run a **deterministic
> brand-compliance check** (APCA/ΔE2000 contrast, correct logo lockup for the
> background, sponsor-safe zones) that attaches an explainable score to each, score
> diversity with `quality/variant_metrics.py` (PAR-5), rank with the existing ranker,
> and return a **ranked shortlist**. (3) Extend the create-graphic route response in
> `web/web.py` to return the shortlist + per-candidate compliance score (additive
> JSON; keep the old single-visual fields populated from the top candidate so
> existing callers keep working). This stage *replaces* the menu-picker prompt — but
> the old `random_variation_profile`/enum path stays in place as the flag-off route
> until SEQ-3, so this is still additive at the route level. Add tests for spec
> emission (mock LLM), normalisation of a bad LLM response to a legal card, and the
> compliance score. Branch `claude/gen-seq-2-tier-b`, test, PR.

**Verification prompt:**
> [Preamble.] Verify SEQ-2: with the flag on, the director emits a schema-valid
> DesignSpec; a deliberately malformed LLM response still yields a legal, legible
> card (PAR-4 normalisation); the pipeline returns a ranked shortlist of ≥4
> structurally distinct candidates each with a compliance score; the top candidate
> populates the legacy single-visual response fields (old callers unaffected); with
> no provider configured it falls back to the deterministic archetype floor (no
> fabricated output). Flag OFF = old behaviour. Suite green. Confirm no spine file
> outside the three named was touched.

### SEQ-3 · Cutover + gated removal of the dead engine (the "full removal")
**Depends on:** SEQ-2 proven (A/B beats the old engine in review + suite green).
**Touches (removals):** `creative_brief/generator.py`,
`creative_brief/ai_director.py`. **Thesis ref:** §5.1, §7 cutover. **This is a
route/data-structure-adjacent removal — follow CLAUDE.md's gated process exactly.**

**Implementation prompt:**
> [Preamble.] Cut over to v2 and remove the dead variation engine — this is a
> deliberate replacement, so you MUST run CLAUDE.md's **15-step breakage check
> (Section A) before** touching anything, write the breakage list, then remove and
> run the **15-step verification (Section B) after**, then the **dead-code sweep
> (Section C)**. Steps: (1) flip `MEDIAHUB_GEN_V2` default to ON. (2) Remove the
> now-dead enum-permutation path: `random_variation_profile`, `_legacy_axes_from_seed`,
> `_PHRASE_TABLES`/`_phrase_for_seed`, and the closed-vocabulary menu-picker
> `_system_prompt` in `ai_director.py`; demote `BACKGROUND_STYLES`/`ACCENT_STYLES`/
> `TYPOGRAPHY_PAIRS`/`COMPOSITIONS`/`PHOTO_TREATMENTS` to renderer-internal building
> blocks only if still needed, else remove. (3) Keep the deterministic archetype
> floor. (4) Migrate or tolerate old persisted briefs/`variation_signature` fields
> (decide explicitly per breakage step 13). Do NOT remove the route or the
> `CreativeBrief` dataclass (extend, don't delete — production depends on them).
> Provide the completed A-list, B-list, and dead-code sweep in the PR description.
> Branch `claude/gen-seq-3-cutover`, run the full suite (no new failures, no
> weakened tests), PR.

**Verification prompt:**
> [Preamble.] Independently re-run CLAUDE.md Section B (15-step safe-removal
> verification) against SEQ-3: zero stray refs to the removed symbols (whole-repo
> grep); imports resolve; full suite green with no deleted/skipped/weakened tests;
> the create-graphic route + templates still work; old persisted runs still load (or
> are migrated); engine accuracy (PB detection, ranking) byte-identical; no new
> debug/IDOR exposure, no `ANTHROPIC_API_KEY` leak; diff contains only intended
> edits; dead-code sweep actually happened (no orphaned helpers, `_unused` vars, or
> "removed" placeholder comments). Report the checklist with pass/fail per step.

### SEQ-4 · Video — data-driven scene structure (+ optional Tier C)
**Depends on:** SEQ-1/2 (the richer brief). **Touches:** `visual/motion.py`,
`remotion/src/compositions/`, optionally `visual/ai_background.py`. **Thesis ref:**
§5.7.

**Implementation prompt:**
> [Preamble.] Enrich video (thesis §5.7). (1) The richer brief (archetype, hero
> stat, tokens) already flows into `visual/motion.py` props — extend the Remotion
> compositions in `remotion/src/compositions/` to honour the archetype/emphasis so
> the reel's *look* matches the still. (2) Add **data-driven scene structure**: a
> multi-PB weekend produces a structurally different reel (variable
> `durationInFrames`/scene count derived from the number of ranked moments) than a
> single medal — the thing template tools can't do and Remotion can. (3) **Optional,
> behind its own flag** (`MEDIAHUB_GEN_BG`, default off): activate the dormant
> `visual/ai_background.py` hook (already imported at `render.py`) via a
> commercial-safe API (Bria/Recraft) for **backgrounds only**, composited under the
> deterministic text, with the existing contrast guardrails — never the data layer.
> Keep cache-by-content-hash behaviour. Add tests for variable scene count. Branch
> `claude/gen-seq-4-video`, test, PR.

**Verification prompt:**
> [Preamble.] Verify SEQ-4: reel scene count varies with the number of ranked
> moments; the reel look matches the still archetype; cache-by-hash still works;
> the optional generative-background path is OFF by default and, when on, only
> affects the background (data text stays deterministic and legible). Suite green.

---

## 4. Dependency graph & sequencing

```
RUN NOW, CONCURRENTLY (each its own session → PR to main, any merge order):
  PAR-1 captions      PAR-2 autofit     PAR-3 saliency    PAR-4 design-spec
  PAR-5 metrics       PAR-6 bootstrap   PAR-7 archetypes×N PAR-8 docs
        (all additive/inert or single-surface — no shared-file conflicts)
                              │
                              ▼
THEN, IN ORDER (each its own PR; gated by MEDIAHUB_GEN_V2):
  SEQ-0 tokens ─▶ SEQ-1 Tier A ─▶ SEQ-2 Tier B ─▶ SEQ-3 cutover+removal ─▶ SEQ-4 video
  (SEQ-0 also coordinates with ROADMAP §1.6 Stage G if not yet merged)
```

**Wiring map (which spine stage consumes which parallel module):**

| Parallel module | Wired in by | Until then it is |
|---|---|---|
| PAR-2 autofit, PAR-3 saliency, PAR-7 archetypes | SEQ-1 | inert new files |
| PAR-4 design-spec, PAR-5 metrics | SEQ-2 | inert new files |
| PAR-6 brand bootstrap | SEQ-0 onboarding (or later) | inert new file |
| PAR-1 captions | already live (own surface) | shipped independently |
| PAR-8 docs | n/a | docs |

**The fastest path to fixing "samey":** PAR-2 + PAR-3 + PAR-7 (in parallel now) →
SEQ-0 → SEQ-1. That delivers Tier A — deterministic, brand-safe, ~$0 marginal cost
— which the thesis expects to resolve the complaint on its own, before any
LLM-director work (SEQ-2).

---

## 5. Acceptance criteria (from thesis §8C)

The overhaul is "done" when, with `MEDIAHUB_GEN_V2` on:

1. **Structural distinctiveness:** a 10-card pack uses ≥6 distinct archetypes; a
   5-candidate pool for one card spans ≥4 archetypes (today ~1–2). Measured by
   `quality/variant_metrics.py` (PAR-5).
2. **On-brand fidelity:** the deterministic compliance check passes ≥99% of shipped
   candidates; off-brand candidates are caught before a human sees them.
3. **Caption non-repetition:** consecutive captions for a card are below the overlap
   threshold; zero ban-list phrases ship.
4. **Human-acceptance rate** (approved without manual redesign) rises vs the old
   engine in the review-UI A/B.
5. **Cost & latency:** marginal API cost/pack < ~$0.50 (Tier A+B); cold render
   within today's 30–90s; cache-hit behaviour preserved.
6. **No moat regression:** rendered data accuracy stays 100% (deterministic), and
   every card keeps its "why this card / why this design" explanation.
7. **Suite green** throughout (no new failures, no weakened tests), and SEQ-3's
   gated-removal checklists are completed and recorded.

---

*Derived from `docs/research/mediahub-generative-ai-thesis.md` and
`docs/research/generation-engine-competitor-evaluation.md`, against `main` after
PR #137. Run the Parallel Bucket (§2) now in separate sessions; then walk the
Sequential Spine (§3) in order.*

