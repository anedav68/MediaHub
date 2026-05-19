# Stage G — Single Source of Truth for Motion + Email + Static: Plan

> Phase 1.6 Stage G of [`ROADMAP.md`](ROADMAP.md). After Stage F the
> *web* chrome is fully theme-aware. Stage G closes the loop for the
> three OTHER places brand colours flow: Remotion motion videos,
> outbound email HTML, and Playwright-rendered static graphics. By
> the end of Stage G all four surfaces draw from a single on-disk
> DTCG JSON — zero drift, zero divergent re-implementations.

## 1. Context

Stage B produces a `DerivedTheme` from any brand seed: nine tonal
ramps × 13 tones, ~30 Material 3 role tokens for light/dark, a
quality report, and a decision trace. Stage B caches this on
`ClubProfile.brand_kit.derived_palette` as a dict. Stage E
persists the cache when the user clicks "Looks right — start
creating".

Today four surfaces draw brand colours from FOUR DIFFERENT
sources:

| Surface | Source | Format |
|---|---|---|
| Web | `THEME_TOKENS_CSS` + inline `<style id="mh-theme-seed">` | CSS custom properties (Stage A–F) |
| Motion (Remotion) | `BrandKit.primary_colour`/`.secondary_colour`/`.accent_colour` via `motion._brand_to_dict()` | `inputProps` JSON to `render.js` |
| Email (newsletter) | `profile.brand_primary` via `_safe_hex()` | Hex literals inlined into `style=""` attributes |
| Static graphics (Playwright) | `brief.palette["primary"/"secondary"/"accent"]` | Hex literals inlined into HTML templates |

Each consumer normalises differently. A club with brand red
`#A30D2D` whose Stage B HCT derivation produced `primary` =
`#A02C42` (light scheme tone 40) sees `#A30D2D` in the motion
video, `#A30D2D` in the email header, `#A30D2D` in the static
graphics, and `#A02C42` in the web chrome. **Four surfaces, four
slightly-different values, no Stage A/B/C invariants enforced.**

Stage G fixes this by making the on-disk DTCG palette the canonical
source. The web cascade already consumes it via Stage E. The other
three surfaces start consuming it here.

## 2. Architecture overview

Five concrete changes:

| Change | Where | What |
|---|---|---|
| Theme store | New `src/mediahub/theming/theme_store.py` | Read/write the DTCG JSON at `DATA_DIR/themes/<profile_id>.json` |
| BrandKit hook | `src/mediahub/brand/kit.py` | When `ensure_derived_palette()` writes, mirror to disk via theme store |
| Motion adapter | `src/mediahub/visual/motion.py` | When given a `profile_id`, prefer the theme-store palette; map MD3 roles → `primary/secondary/accent` for the Remotion compositions |
| Email adapter | `src/mediahub/brand/newsletter_renderer.py` | Read `profile_id` from profile; pull the theme-store palette; use MD3 roles for header band + footer text |
| Static adapter | `src/mediahub/graphic_renderer/render.py` | Accept an optional `theme_json` parameter; when present, override `brief.palette` with the theme-store values |

The data flow becomes:

```
                    ┌────────────────────────────┐
                    │  ClubProfile.brand_kit     │
                    │  ensure_derived_palette()  │
                    └──────────────┬─────────────┘
                                   │ mirrors to disk
                                   ▼
                ┌──────────────────────────────────┐
                │  DATA_DIR/themes/<profile>.json  │
                │  ─── ThemeJSON (DTCG format) ─── │
                └─┬───────┬───────────┬────────────┘
                  │       │           │
       reads ◄────┘       │           └────► reads
       (web cascade)      │                  (static graphics)
                          ▼
                  ┌────────────┐
                  │ motion +   │
                  │ email      │
                  │ read       │
                  └────────────┘
```

Every surface ends up resolving the same hex for the same role,
because they all read the same JSON. The "zero drift" promise.

## 3. G1 — DTCG JSON at `DATA_DIR/themes/<profile_id>.json`

The DTCG-format JSON already exists as the `ThemeJSON` TypedDict
in `src/mediahub/theming/__init__.py`. Stage G introduces the
on-disk projection.

### File layout

```
DATA_DIR/
├── club_profiles/
│   └── <profile_id>.json     # the whole ClubProfile
└── themes/                     # NEW (Stage G)
    └── <profile_id>.json     # just the DerivedTheme.to_json()
```

The `themes/` directory is a *view* of `ClubProfile.brand_kit.
derived_palette`: same content, separate file. Two reasons:

1. **Read isolation.** Motion + email + static renderers shouldn't
   have to load the full ClubProfile (which carries voice
   signals, captured DNA, AI operating profile, etc.) just to
   pluck the palette. The standalone file is ~6KB; loading a
   ClubProfile costs many times that.
2. **Cache friendliness.** Stage J (the cutover stage) is the
   future point where this JSON gets served as a static
   `theme-<sha>.json` via Flask's `send_from_directory` with
   `Cache-Control: immutable`. Per-profile JSON files live at
   stable URLs.

### The theme store API

```python
# src/mediahub/theming/theme_store.py

def themes_dir() -> Path:
    """DATA_DIR/themes/, created on demand."""

def theme_path(profile_id: str) -> Path:
    """Path for a profile's theme JSON. Validates profile_id is a
    filesystem-safe slug (defence against path traversal)."""

def write_theme(profile_id: str, theme_json: dict) -> Path:
    """Write the DTCG JSON to disk atomically (tmp + rename) so a
    crashed writer never leaves a half-written file. Returns the
    absolute path."""

def read_theme(profile_id: str) -> Optional[dict]:
    """Read a profile's theme JSON. Returns None when the file
    doesn't exist or is malformed — never raises. Cached via
    lru_cache keyed by (path, mtime) for sub-millisecond reads."""

def delete_theme(profile_id: str) -> bool:
    """Remove a profile's theme file (called when a profile is
    deleted). Idempotent."""
```

Profile-id sanitisation: `re.fullmatch(r"[a-z0-9\-_]{1,80}", pid)`
— stricter than ClubProfile's own regex so we never get
`../../etc/passwd` shenanigans even if the profile-id check
upstream is bypassed.

Atomic write: `tempfile.NamedTemporaryFile(dir=themes_dir())` +
`Path.replace()`. The temporary file shares the destination
directory so `replace()` is atomic on every common POSIX
filesystem.

### The BrandKit hook

`BrandKit.ensure_derived_palette()` already computes and caches
the palette on the instance. Stage G adds the disk mirror:

```python
def ensure_derived_palette(self, *, force=False, source=None) -> dict:
    if self.derived_palette is not None and not force:
        return self.derived_palette
    from mediahub.theming import derive_theme
    from mediahub.theming.theme_store import write_theme  # NEW
    seed_source = source or self.logo_svg or self.safe_primary()
    theme = derive_theme(seed_source)
    self.derived_palette = theme.to_json()
    # Stage G: mirror to the per-profile theme store on disk.
    try:
        write_theme(self.profile_id, self.derived_palette)
    except Exception:
        # Disk failure must not block save; the in-memory palette
        # is still valid.
        pass
    return self.derived_palette
```

The mirror is best-effort. If disk write fails (out-of-quota,
read-only mount), the in-memory palette is still authoritative
for THIS request; consumers fall back to the legacy
`primary_colour` fields.

## 4. G2 — Motion (Remotion) reads from theme store

`visual/motion.py:_brand_to_dict()` currently builds the
Remotion props from the BrandKit's flat fields:

```python
return {
    "primary":   src.get("primary_colour") or "#0A2540",
    "secondary": src.get("secondary_colour") or "#000000",
    "accent":    src.get("accent_colour") or "#FFFFFF",
    ...
}
```

Stage G change: if a `profile_id` is reachable on the brand kit
input, prefer the theme-store JSON. Map MD3 role tokens onto
Remotion's `primary/secondary/accent` shape:

```python
def _brand_to_dict(brand_kit, *, profile_id: Optional[str] = None):
    """Stage G: prefer the theme-store palette over BrandKit's flat fields."""
    src = ...  # existing normalisation
    pid = profile_id or src.get("profile_id")
    theme_json = None
    if pid:
        try:
            from mediahub.theming.theme_store import read_theme
            theme_json = read_theme(pid)
        except Exception:
            theme_json = None
    if theme_json:
        roles = (theme_json.get("roles") or {}).get("dark") or {}
        return {
            "primary":   roles.get("primary")           or src.get("primary_colour")   or "#0A2540",
            "secondary": roles.get("secondary_container") or src.get("secondary_colour") or "#000000",
            "accent":    roles.get("tertiary")          or src.get("accent_colour")    or "#FFFFFF",
            ...,
            "themeSource": "theme-store",
        }
    # Legacy path — unchanged.
    return {...}
```

Mapping rationale: Stage B's `primary` is the brand seed at MD3
tone 80 in dark schemes (light) / tone 40 in light schemes
(dark). Remotion compositions historically use the raw brand hex
for fills, so the *dark scheme* primary (which is the lighter,
more saturated brand tone) reads better against video-grade
backgrounds. The `secondary_container` is the muted variant used
for surfaces. `tertiary` is the medal-gold accent.

The Remotion compositions don't change — they consume the same
`{primary, secondary, accent, …}` shape they consumed before.
This means **zero changes to JavaScript / Remotion code**; the
mapping happens once in Python.

## 5. G3 — Email (newsletter) reads from theme store

`brand/newsletter_renderer.py:render_email_html()` currently reads
`profile.brand_primary` directly. Stage G adds a theme-store
lookup:

```python
def render_email_html(artefact, *, profile=None, meet_summary=None):
    ...
    brand_primary = _resolve_email_primary(profile)
    ...

def _resolve_email_primary(profile) -> str:
    """Stage G: prefer the theme-store palette's PRIMARY role; fall
    back to the legacy brand_primary field, then to the Stage A
    default."""
    pid = _get(profile, "profile_id")
    if pid:
        try:
            from mediahub.theming.theme_store import read_theme
            tj = read_theme(pid)
            if tj:
                # Email is viewed on light backgrounds (white email
                # body) so use the LIGHT scheme's primary role —
                # darker, higher-contrast against the white email
                # background.
                light = (tj.get("roles") or {}).get("light") or {}
                primary = light.get("primary")
                if isinstance(primary, str) and primary.startswith("#"):
                    return _safe_hex(primary, "#0A2540")
        except Exception:
            pass
    return _safe_hex(_get(profile, "brand_primary"), "#0A2540")
```

The email header band uses `LIGHT.primary` because:
1. Emails are viewed against a white body (`#f3f4f6` in the
   current template).
2. MD3's light scheme `primary` is dark and saturated (tone 40)
   — high contrast against white.
3. Using `DARK.primary` here would produce a washed-out pastel
   header band.

"Premailer-style inlining" — `render_email_html()` already
inlines hex values directly into `style="background: #..."`
attributes, which is what Premailer (the npm/python tool) does
for full CSS files. Stage G doesn't introduce a Premailer
runtime dependency; the existing inline-style render already
produces email-safe output. Stage G just ensures the inlined
hex comes from the theme store.

## 6. G4 — Static graphics (Playwright) reads from theme store

`graphic_renderer/render.py:_common_replacements()` currently
reads from `brief.palette`:

```python
palette = brief.palette or {}
primary = palette.get("primary", "#0A2540")
secondary = palette.get("secondary", "#000000")
accent = palette.get("accent", "#FFFFFF")
```

Stage G adds an optional `theme_json` parameter to `render_brief()`
and `_common_replacements()`. When provided, the theme JSON's
roles override the brief's palette:

```python
def _common_replacements(brief, width, height, brand_kit, *,
                         athlete_data_uri, logo_block, result_chip,
                         sponsor_block,
                         theme_json: Optional[dict] = None):
    palette = brief.palette or {}
    if theme_json:
        # Stage G: theme-store roles override the brief's palette
        # so static graphics drop into the cascade.
        light = (theme_json.get("roles") or {}).get("light") or {}
        palette = {
            "primary":   light.get("primary")              or palette.get("primary",   "#0A2540"),
            "secondary": light.get("secondary_container")  or palette.get("secondary", "#000000"),
            "accent":    light.get("tertiary")             or palette.get("accent",    "#FFFFFF"),
        }
    primary = palette.get("primary", "#0A2540")
    ...
```

The static graphic renderer outputs PNGs at 1080×1080 / 1080×1350
for social posting. Audience is the social feed (light or dark
mode depending on the user's device), but most posts get viewed
on social platforms with light backgrounds. Same reasoning as
email: use the **light** scheme primary for high contrast.

`render_brief()` resolves the theme JSON from the profile_id
embedded in the brand_kit (when available) and passes it down.
The CreativeBrief flow doesn't change shape; this is a
zero-touch behaviour upgrade.

## 7. The role-mapping convention

Four consumers, three role mappings. Documented once in
`theme_store.py` and referenced by each consumer:

| Surface | Scheme | `primary` ← | `secondary` ← | `accent` ← |
|---|---|---|---|---|
| Web (cascade) | both (light-dark()) | `--mh-primary` (tier-2) | `--mh-secondary` | `--mh-tertiary` |
| Motion (video) | dark | `roles.dark.primary` | `roles.dark.secondary_container` | `roles.dark.tertiary` |
| Email | light | `roles.light.primary` | (header text white; not used) | (not used) |
| Static graphics | light | `roles.light.primary` | `roles.light.secondary_container` | `roles.light.tertiary` |

Web uses both schemes via `light-dark()` (Stage C). Motion uses
dark because video-grade outputs need higher saturation. Email
and static use light because they're viewed against white
backgrounds.

This convention is encoded in `theme_store.py` as three helper
functions:

```python
def palette_for_motion(theme_json: dict) -> dict: ...
def palette_for_email(theme_json: dict) -> dict: ...
def palette_for_static(theme_json: dict) -> dict: ...
```

Each returns `{primary, secondary, accent, full_roles}` so callers
can either consume the canonical 3-key shape or drill into the
full role table.

## 8. Backwards compatibility

Stage G is purely additive. Three flavours of backward
compatibility:

### Profiles without a theme on disk

The theme store's `read_theme()` returns `None` for profiles
that haven't been finalised via Stage E. Every consumer falls
back to the legacy path (BrandKit's flat fields). No regression.

### BrandKit instances without a `profile_id`

The motion / email / static helpers only consult the theme store
when a `profile_id` is reachable. Standalone BrandKit usage
(tests, one-off renders) keeps working through the legacy path.

### Concurrent profile updates

`write_theme()` is atomic via tmp+rename. A reader will see
either the old file or the new file, never a half-written one.
The lru_cache on reads is keyed by `(path, mtime)` so a fresh
write invalidates cached reads on the next call.

### Deleted profiles

`delete_theme()` is idempotent. The profile-deletion route in
`web.py` already deletes the profile JSON; Stage G appends a
single `delete_theme(profile_id)` call after that for cleanup.

## 9. Test strategy

Five new test files / sections:

### `tests/theming/test_theme_store.py` — the store API

- `themes_dir()` creates the directory on demand.
- `theme_path()` rejects path-traversal attempts
  (`"../etc/passwd"`, `"a/b"`, `"name with spaces"`).
- `write_theme()` is atomic (no half-written file on crash).
- `read_theme()` returns None for missing / malformed files.
- `read_theme()` is cached by mtime — modifying the file then
  reading produces fresh data.
- `delete_theme()` is idempotent.
- `palette_for_motion/email/static` produce the documented
  `{primary, secondary, accent}` shape.

### `tests/theming/test_brand_kit_disk_mirror.py` — the hook

- After `ensure_derived_palette()` returns, the theme file
  exists on disk at the expected path.
- The on-disk JSON equals the in-memory `derived_palette` dict.
- `force=True` re-writes the file.
- Disk-write failure (mock OSError) doesn't break
  `ensure_derived_palette()`.

### `tests/test_motion_theme_store.py` — G2

- `_brand_to_dict()` prefers theme-store values when `profile_id`
  resolves to a real theme.
- Falls back to legacy `primary_colour` when theme-store is
  empty.
- The output dict's keys match the Remotion compositions'
  expected shape.

### `tests/test_newsletter_theme_store.py` — G3

- `render_email_html()` for a profile WITH a theme-store entry
  uses `roles.light.primary` in the header band.
- Falls back to `profile.brand_primary` when theme-store is
  empty.
- Falls back to `#0A2540` when neither source is present.

### `tests/test_graphic_renderer_theme_store.py` — G4

- `_common_replacements()` with `theme_json=<…>` produces
  output with the theme-store primary.
- Without `theme_json`, behaviour is unchanged.

## 10. Risk register

| Risk | Probability | Mitigation |
|---|---|---|
| Disk-write failure breaks `ensure_derived_palette` | Low | try/except wraps the write; in-memory palette stays authoritative |
| Path-traversal via crafted profile_id | Low | strict regex on profile_id, plus `Path.resolve()` confirmation |
| Reader returns stale data | Low | lru_cache keyed by (path, mtime); fresh writes invalidate |
| Atomic-write race on Windows | Low | tmp+rename is POSIX-atomic; on Windows Python's `Path.replace()` is a documented equivalent |
| Schema drift between in-memory and on-disk | Medium | Both use `DerivedTheme.to_json()`; a single TypedDict definition |
| Empty / malformed theme JSON | Low | `read_theme()` swallows JSON errors, returns None |
| Concurrent reads/writes during a finalise spike | Low | Atomicity covers concurrent writes; readers may see old or new data, never partial |
| Test fixtures hit production paths | None | `DATA_DIR` is monkey-patched per test |
| Backwards-compat: existing profiles without a theme file | None | Every consumer has a legacy fallback path |
| Motion / email / static using different scheme | Intentional | Documented convention in theme_store.py |

## 11. Audit plan (10 subtasks)

1. `mediahub.theming.theme_store` imports cleanly.
2. `themes_dir()` creates `DATA_DIR/themes/` on demand.
3. `theme_path()` rejects path-traversal attempts.
4. `write_theme()` produces an atomic file write.
5. `read_theme()` returns None for missing files (no exception).
6. `BrandKit.ensure_derived_palette()` mirrors to disk.
7. Disk write failure doesn't break the in-memory return value.
8. `_brand_to_dict()` prefers theme-store values when available.
9. `render_email_html()` prefers theme-store light.primary.
10. Stage F's 40 tests still pass.

## 12. Verify plan (10 subtasks)

1. App boots; `/status` returns HTTP 200.
2. POST `/api/organisation/finalise` writes `DATA_DIR/themes/
   <pid>.json` end-to-end.
3. The on-disk JSON has all required ThemeJSON keys.
4. `read_theme(profile_id)` returns the same dict as the
   in-memory `derived_palette`.
5. Motion `_brand_to_dict()` integration: profile with theme on
   disk returns the dark-scheme primary.
6. Newsletter `render_email_html()` for a finalised profile uses
   the light-scheme primary in the header band.
7. Graphic renderer's `_common_replacements()` accepts
   `theme_json` without crashing.
8. With NO theme on disk, every consumer falls back to legacy
   path (no regression for unfinalised profiles).
9. Full pytest suite passes (Stage A–F + new G tests).
10. Three role-mapping helpers (motion/email/static) produce
    documented output shape.

## 13. Out of scope (deferred)

- Switching the web cascade to consume `DATA_DIR/themes/<pid>.json`
  via static-asset URLs (Stage J cutover).
- Pre-warming the theme store at deploy time for all existing
  profiles (one-time migration script — Stage J).
- Multi-tenant subdomain routing that picks the theme file by
  `request.host` (Phase 3 work).
- Caching the read with Cache-Control / ETag headers — only
  matters once theme files are served, which is Stage J.

After Stage G, the four content surfaces draw brand colours from
one place. The "zero drift" promise becomes verifiable: a single
test can read the disk JSON, render motion / email / static, and
assert every output carries the SAME primary hex. Stage H's "Why
does my theme look like this?" panel and Stage J's full cutover
both build on this foundation.
