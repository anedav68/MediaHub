# Stage C — CSS Architecture: Thesis Plan

> Phase 1.6 Stage C of [`ROADMAP.md`](ROADMAP.md). Builds on Stage A
> (token foundation) and Stage B (colour-science package). No website
> regression — visible pixels stay polished, but the *origin* of the
> palette shifts from "hand-coded in a Python string" to "derived in
> the browser from a single seed". This is the architectural
> inflection point of Phase 1.6.

## 1. Context

Stage A introduced the three-tier DTCG vocabulary (~25 Material-3-
style semantic role tokens referencing ~50 hand-coded tier-1
primitives) inside `src/mediahub/web/theme_tokens.py` as the
`THEME_TOKENS_CSS` Python string. Stage A re-pointed every legacy
alias (`--bg`, `--ink`, `--lane`, `--medal`, `--accent`, `--panel`,
…) at a tier-2 token, and registered every animatable colour as a
typed CSS custom property via `@property`. Cascade order is
`THEME_TOKENS_CSS → BASE_CSS → RESPONSIVE_GUARDRAILS_CSS`.

Stage B built the entire colour-science pipeline as a Python
package (`src/mediahub/theming/`). Given a brand seed it derives a
full HCT-based palette: 5 brand-anchored tonal ramps × 13 tones, 4
status anchor ramps, and a complete MD3 role mapping for light and
dark schemes — plus APCA / WCAG / CIEDE2000 / Machado-CVD QA gates
and a constraint-satisfaction repair loop. The result is cached on
`ClubProfile.brand_kit.derived_palette` as a DTCG JSON dict. Nothing
yet consumes it.

Stage C is the architectural shift. It moves the cascade from
"~50 hand-coded hex values shipped in a Python string" to "1 seed
hex + 6 anchor colours shipped, and ~55 derived shades computed by
the browser at runtime". This is what the roadmap calls "minimise
hardcode" — the surface area where future palette updates need to
touch code drops by an order of magnitude. Stage D will then wire
the dynamic `derived_palette` from Stage B into the seed, completing
the loop.

Stage C is the most aesthetically risky stage of Phase 1.6: the
existing "Podium After Dark" palette has hand-tuned hex values
chosen by the designer for specific reasons (e.g. `--ink-muted`
sits at `#9A988A` precisely so it clears WCAG 5.69:1 on the
existing background). Derivation formulas will produce values that
are *close* but not byte-identical. The plan handles this by
keeping the hand-coded primitives as the explicit fallback (inside
`@supports not`), so every browser sees identical pixels until the
modern-CSS branch lands. Modern browsers then take the derived
values, and we monitor for pixel drift via diff-rendered HTML.

## 2. Architecture overview

Three new static CSS files under `src/mediahub/web/static/theme/`:

| File | Purpose | Size |
|---|---|---|
| `theme-base.css` | Tier-1 seed declarations + `@property` registrations + tier-2 role tokens + legacy aliases. Defaults that work in every browser. | ~5KB |
| `theme-derive.css` | `@supports (color: oklch(from red l c h))` block. Overrides tier-1 primitives with `oklch(from var(--mh-…-seed) …)` expressions and uses `color-mix(in oklch, …)` for tonal blends. ~55 derived shades. | ~4KB |
| `theme-fallback.css` | `@supports not (color: oklch(from red l c h))` block. Stage A's hand-coded values, identical to today's pixels. Catches Safari ≤ 16.3 and other engines without relative-colour syntax. | ~3KB |

Cascade order in the assembled stylesheet:

    theme-base.css → theme-fallback.css → theme-derive.css

Modern browsers parse all three; the derive block sits last and
wins. Safari ≤ 16.3 silently drops the derive block's unparseable
inner declarations but the `@supports not (…)` fallback fires —
identical pixels to today.

`src/mediahub/web/theme_tokens.py` becomes a thin loader: reads
the three files at import time, concatenates them in the correct
order, exposes `THEME_TOKENS_CSS` as the same Python string that
already gets prepended to `BASE_CSS` in `web.py`. Zero changes to
the inline-HTML delivery path for Stage C; the static assets are
prepared for Stage D's actual `<link rel="stylesheet">` switch.

## 3. C1 — File extraction

The current `theme_tokens.py` contains the full token vocabulary in
a 9KB raw Python string (`THEME_TOKENS_CSS`). C1 moves that string
into a real `.css` file on disk.

Steps:

1. Create `src/mediahub/web/static/theme/theme-base.css` containing
   the existing `:root` block (tier-1 primitives, tier-2 role
   tokens, legacy alias re-pointing) plus the `@property`
   registrations. The content is the same as today's
   `THEME_TOKENS_CSS`, verbatim.
2. Refactor `theme_tokens.py` to load that file at import time and
   expose `THEME_TOKENS_CSS` as the file's contents. Backward
   compatible — every callsite in the codebase keeps working
   because the symbol still exists and resolves to the same string.
3. Ensure the file path is robust: use
   `Path(__file__).parent / "static" / "theme" / "theme-base.css"`
   so the loader works whether the package is installed in
   editable mode or via wheel.

Once `theme-base.css` exists on disk, stylelint can lint it
properly (the CI workflow at
`.github/workflows/responsive-design.yml` already lints
`src/mediahub/graphic_renderer/layouts/*.css`; extending it to
include the theming directory is a one-line tweak to that
workflow, but is deferred to Stage J as part of the cutover).

C1 is mechanical. The audit phase will diff the on-disk file
against the original Python string and confirm zero content drift.

## 4. C2 — Runtime derivation

The substantive piece of Stage C. The goal: Python ships only the
seed values; the browser computes everything else at runtime.

### The seed model

Seven seed variables (cf. the roadmap's "seed + 5 anchors"):

```css
:root {
  --mh-brand-seed:    #D4FF3A;   /* lane yellow — the brand */
  --mh-tertiary-seed: #F4D58D;   /* medal gold — the second brand colour */
  --mh-neutral-seed:  #F5F2E8;   /* paper-cream — neutral tint anchor */
  --mh-error-seed:    #FF6B6B;   /* locked status anchor */
  --mh-success-seed:  #5EE39A;   /* locked status anchor */
  --mh-warning-seed:  #FFB454;   /* locked status anchor */
  --mh-info-seed:     #4DA3FF;   /* locked status anchor */
}
```

Each seed is `@property`-registered so it interpolates during
Stage E's cascade animation. Status seeds are LOCKED — they don't
move with the brand seed, per the cross-cultural-semantics rule
established in Stage B (Aslam 2006, WCAG 1.4.1).

### The derivation formula

For each non-zero non-extreme tone of each brand-ish ramp:

```css
--mh-prim-brand-<tone>:
  oklch(from var(--mh-brand-seed)
        <target_lightness>
        calc(c * <chroma_scale>)
        h);
```

`target_lightness` is per-tone — the Tailwind-style tone names
(50=lightest, 1000=darkest) map to OKLCH lightness anchors. The
mapping is calibrated against MediaHub's existing palette so
pixels for the lane-yellow seed land within ΔE2000 ≤ 5 of the
current values:

```
tone   target_L   chroma_scale
 50    0.99       0.10
100    0.97       0.40
200    0.94       0.65
300    0.92       0.85
400    (seed)     1.00      <— the seed itself
500    0.83       0.95
600    0.74       0.88
700    0.62       0.72
800    0.50       0.55
900    0.36       0.40
950    0.22       0.25
```

Pure white (`--mh-prim-*-0: #FFFFFF`) and pure black
(`--mh-prim-*-1000: #000000`) stay as anchors — they're identity
elements that don't need derivation.

The same formula shape applies to the tertiary ramp (with
`--mh-tertiary-seed`), the neutral ramp (with `--mh-neutral-seed`,
chroma capped at ~0.02 for true greys), and the four status ramps
(each with their own locked seed).

### `color-mix()` for tier-2 role tokens

Some tier-2 tokens are best expressed as mixes rather than tone
lookups. Examples:

```css
--mh-outline:
  color-mix(in oklch, var(--mh-on-surface) 14%, transparent);

--mh-outline-variant:
  color-mix(in oklch, var(--mh-on-surface) 6%, transparent);

--mh-outline-rule:
  color-mix(in oklch, var(--mh-on-surface) 10%, transparent);
```

The current hand-coded equivalents are
`rgba(245, 242, 232, 0.14)` etc. — alpha blends of the ink
colour onto transparent. `color-mix(in oklch, …)` is the modern
spelling, with the bonus that it picks up theme changes
automatically.

### Counting derived shades

Brand ramp: 11 derived tones (50…950) + 2 anchors (0, 1000) = 13
Tertiary ramp: 11 derived = 13
Neutral ramp: 14 derived = 16 (the existing palette has a 14-stop
neutral ramp because Podium After Dark has multiple dark surface
tiers)
4 status ramps × 1 tone each: 4 (Stage B's status palettes are
13-tone, but only tone-400 is used by tier-2 role tokens at
present; the rest can be derived lazily later)
Tier-2 outlines etc.: 3 via `color-mix`
**Total**: ~55 derived shades. Python ships ~7 seed hex values.
That's the "minimise hardcode" win.

## 5. C3 — Light/dark parity

Stage A's palette is dark-mode only ("Podium After Dark"). Stage C
adds light-mode support without abandoning the existing dark-mode
aesthetic.

### `color-scheme` and `prefers-color-scheme`

At the top of `theme-base.css`:

```css
:root {
  color-scheme: light dark;
}
```

This tells the browser's UA chrome (form controls, scrollbars,
text selection) to adapt. Without it, native widgets remain
stuck in light or dark regardless of the rest of our cascade.

### `light-dark()` for role tokens

Material 3's role tokens are scheme-aware. For Stage C, tier-2
tokens that differ between light and dark get rewritten using
`light-dark()`:

```css
--mh-surface: light-dark(
  var(--mh-prim-neutral-50),     /* light mode: paper-cream */
  var(--mh-prim-neutral-950)     /* dark mode: pit-wall black */
);
--mh-on-surface: light-dark(
  var(--mh-prim-neutral-950),    /* dark text on light surface */
  var(--mh-prim-neutral-50)      /* light text on dark surface */
);
```

The `prefers-color-scheme` media query is implicit — `light-dark()`
reads the document's `color-scheme` setting and picks the right
branch automatically.

### Backward-compatibility wrinkle

Stage A's tier-2 tokens are currently hard-coded to dark-mode
values (e.g. `--mh-surface: var(--mh-prim-neutral-950)`). Switching
them to `light-dark()` makes them respond to user preference.
**This is a behaviour change for users with `prefers-color-scheme:
light` set.**

For Stage C's "no visible regression" we keep dark mode as the
default (`color-scheme: dark` overrides the system preference, OR
the `light-dark()` calls are added but with both arguments
identical to today's dark values). I'll go with the latter for
Stage C — every `light-dark()` call in this stage ships
`(dark_value, dark_value)` so users see the same dark pixels they
see today.

Stage D or J will introduce real light-mode values once the
designer signs off on the palette. The architectural support is in
place from Stage C onward.

## 6. C4 — Safari ≤ 16.3 fallback

Relative colour syntax (`oklch(from red l c h)`) landed in Chrome
119 (Oct 2023), Firefox 128 (Jul 2024), Safari 16.4 (Mar 2023).
Safari 16.0–16.3 (a meaningful long tail of devices that don't
auto-update through paid carriers) and any niche embedded browser
without the parser will reject the modern declarations as invalid
and fall through to the previous declaration.

The fallback strategy:

```css
/* theme-fallback.css */
@supports not (color: oklch(from red l c h)) {
  :root {
    --mh-prim-brand-50:  #FAFFE6;   /* the hand-tuned Stage A values */
    --mh-prim-brand-100: #F1FFB8;
    /* … every primitive ramp tone … */
  }
}

/* theme-derive.css */
@supports (color: oklch(from red l c h)) {
  :root {
    --mh-prim-brand-50:  oklch(from var(--mh-brand-seed) 0.99 calc(c * 0.10) h);
    --mh-prim-brand-100: oklch(from var(--mh-brand-seed) 0.97 calc(c * 0.40) h);
    /* … */
  }
}
```

Both `@supports` blocks declare every variable, so the cascade is
fully specified for any browser. The fallback values are
byte-identical to today's hand-coded Stage A primitives.

Stage C uses `@supports not` rather than the alternative pattern
of "defaults + override-on-modern" because:

1. The user's roadmap brief specified `@supports not` explicitly.
2. It makes the fallback values an explicit, named branch that's
   easy to review and audit.
3. It groups the "modern" and "legacy" cascades into clearly-
   separated files, which makes the diff easier to read.

## 7. Pixel-parity strategy

Two compatibility tiers:

**Tier 1 — bytewise identical (fallback path)**: Safari ≤ 16.3 and
any other engine without relative-colour syntax. The values in
`theme-fallback.css` are bytewise copies of Stage A's hand-coded
ramp. ΔE2000 = 0 vs current pixels.

**Tier 2 — perceptually close (derived path)**: modern browsers.
Calibrated formulas land within ΔE2000 ≤ 5 of every Stage A tone
when fed the lane-yellow seed. ΔE2000 ≤ 5 is the Radix "clearly
perceptible step" threshold; below it, side-by-side comparison
shows a difference but the overall design feels identical.

The audit phase includes a pixel-parity check: for each of the ~25
hand-coded tones, compute the derived value with
`--mh-brand-seed = #D4FF3A` and assert ΔE2000 ≤ 5.

For the 10-subtask verify, I'll also render `/status` and
`/healthz/usage` and visually confirm no obvious shift. Without an
end-to-end browser harness in the test env, the verify is
algorithmic — confirm computed-style values resolve to the
expected derived hexes.

## 8. Flask integration

For Stage C, the inline-HTML delivery path is preserved. The Python
loader concatenates the three static files into `THEME_TOKENS_CSS`,
which `web.py` then prepends to `BASE_CSS` and inlines into the
`<style>` block of every rendered page. Zero change to the request
lifecycle.

Stage D will introduce a `<link rel="stylesheet" href="…">` for
the static assets and reduce the inline `<style>` block to just the
~7 seed values. That's the proper Stage E "smooth cascade animation
on Looks right" architecture. For Stage C, the disk files are
prepared but the network delivery is unchanged.

The static files live under `src/mediahub/web/static/theme/`. This
is Flask's default static-folder convention; when Stage D wires
the `<link>`, the files become accessible at `/static/theme/*.css`
automatically.

## 9. Test strategy

New tests in `tests/test_theme_static_files.py`:

1. The three files exist on disk and are readable.
2. Each file is non-empty and contains the expected `@supports`
   gate (or lack thereof for `theme-base.css`).
3. `theme_tokens.py` loads them at import time without error.
4. `THEME_TOKENS_CSS` (the existing module-level constant) is now
   the concatenation of the three files in the documented order.
5. The seven seed variables are declared in `theme-base.css`.
6. Every Stage A tier-1 primitive appears in `theme-fallback.css`
   with its byte-identical hex value (so the fallback path
   preserves pixels exactly).
7. The derive block contains at least 30 `oklch(from …)`
   expressions referencing one of the seven seed variables.
8. The light-dark() calls in `theme-base.css` use identical
   arguments on both sides (no behaviour change for Stage C).
9. `@property` registrations for every tier-2 role token (Stage A
   invariant) survive the file split.

Plus extension of `tests/test_theme_tokens.py` to assert the new
file-loading code path doesn't regress the existing 161 tests.

Plus a pixel-parity calculation test that compares each derived
tone (computed from `--mh-brand-seed = #D4FF3A` via the derive
formula, executed in Python via `coloraide`) against the Stage A
hand-coded value, asserting ΔE2000 ≤ 5.

## 10. Risk register

| Risk | Probability | Mitigation |
|---|---|---|
| Derivation formula produces visibly different pixels for lane yellow | Medium | Calibrate formulas against current palette; pixel-parity test asserts ΔE2000 ≤ 5 |
| Safari ≤ 16.3 users see broken styles | Low | `@supports not` block is explicit; fallback values byte-identical to Stage A |
| File-load path fails on Render deployment | Low | Use `pkg_resources.files()` or `Path(__file__).parent` — both work in editable + installed modes |
| Stylelint complains about modern syntax | Low | Stylelint's `function-no-unknown` rule already has `oklch`, `color-mix` allow-listed in `.stylelintrc.json` (per the existing config) |
| `@supports` semantics differ across engines | Very Low | Spec is stable; both `@supports (X)` and `@supports not (X)` are universal |
| Light-dark() introduces unintended light-mode rendering | Medium | Both arguments are identical for Stage C; Stage D introduces real light values |
| CSS variable interpolation gets re-broken by removing `@property` declarations | Low | All Stage A `@property` declarations preserved verbatim |
| The 7 seed values drift away from Stage A primitives between commits | Low | The Python loader concatenates from disk; any drift requires editing disk files, which the test suite catches |

## 11. Audit plan (10 subtasks)

After implementation:

1. The three CSS files exist at `src/mediahub/web/static/theme/`,
   non-empty, valid CSS.
2. `theme_tokens.py` loads them at import without `FileNotFoundError`
   or parse errors.
3. `THEME_TOKENS_CSS` (module constant) equals concat of the three
   files in documented order.
4. Every Stage A tier-1 primitive token from the original Python
   string appears verbatim in `theme-fallback.css`.
5. The seven seed variables (`--mh-brand-seed`, `--mh-tertiary-
   seed`, `--mh-neutral-seed`, `--mh-error-seed`, `--mh-success-
   seed`, `--mh-warning-seed`, `--mh-info-seed`) are declared
   exactly once each in `theme-base.css`.
6. The derive block (`@supports (color: oklch(from red l c h))`)
   contains at least one `oklch(from …)` expression per
   brand/tertiary/neutral tone.
7. Pixel-parity: for each Stage A tier-1 primitive, the derived
   value computed by `coloraide` from the lane-yellow seed lands
   within ΔE2000 ≤ 5 of the hand-coded value.
8. Stage A's 161 theme-tokens tests still pass.
9. Stage B's 182 theming tests still pass.
10. Full Flask app boots — `/status` returns HTTP 200 with the
    `<style>` block containing the assembled CSS.

## 12. Verify plan (10 subtasks)

1. The new files are visible to git (added, not gitignored).
2. The `web.py` cascade `THEME_TOKENS_CSS → BASE_CSS →
   RESPONSIVE_GUARDRAILS_CSS` is preserved bytewise (modulo the
   new content of `THEME_TOKENS_CSS`).
3. Rendered HTML of `/status` includes:
   - `--mh-brand-seed: #D4FF3A;`
   - At least one `oklch(from var(--mh-brand-seed)` substring
   - At least one `light-dark(` substring
   - At least one `color-mix(in oklch` substring
4. Rendered HTML of `/healthz/usage` likewise includes the seed
   declaration.
5. `theme_tokens.py` import time stays under 50ms (sanity for
   file-load overhead).
6. Both `@supports` branches (modern and fallback) are
   syntactically balanced (open braces == close braces).
7. The full Stage B `derive_theme` pipeline still works end-to-end.
8. The pre-existing 1,357-test suite passes (1,175 baseline + 182
   Stage B + new Stage C additions).
9. `coloraide` can parse every literal hex in the fallback block
   (smoke test against malformed entries).
10. `oklch(from var(--mh-brand-seed) 0.99 calc(c * 0.10) h)` resolves
    to a near-pure-pale-yellow when `--mh-brand-seed = #D4FF3A`
    (cross-check via Python-side OKLCH computation).

## 13. Out of scope (deferred to later stages)

- Wiring `derived_palette` from Stage B into the seed declarations
  in `theme-base.css` (Stage D's job).
- Switching from inline `<style>` delivery to `<link rel="stylesheet">`
  static delivery (also Stage D).
- The smooth cascade animation on "Looks right – start creating"
  (Stage E).
- Real light-mode visual design (deferred until a designer commits
  light-mode colour decisions; until then `light-dark()` calls
  ship identical arguments).
- Replacing Stage A's hand-coded primitives entirely (Stage J's
  cutover).

Stage C is the architectural inflection point. After it, every
later stage compounds on top: Stage D updates the seed dynamically
from the cached `derived_palette`, Stage E animates the seed
change via View Transitions, Stage F handles logos against the
new theme, Stage G shares the JSON across motion/email/static. The
foundation is the file-based, CSS-derived cascade Stage C
establishes.
