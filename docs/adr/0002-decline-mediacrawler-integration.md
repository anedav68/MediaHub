# ADR 0002 — Decline integrating MediaCrawler (logged-in social-media crawler)

**Status:** Accepted — rejected · **Date:** 2026-06-02 · **Decided by:**
`llm-council` skill (5 advisors → anonymised peer review → chairman; unanimous
5/5).
**Decision record:** council transcript +
[report](../../autotest/reports/council/decline-mediacrawler-2026-06-02.md)
under `autotest/reports/council/decline-mediacrawler-2026-06-02.{md,html}`.

# 1. Context

We were asked where integrating
[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) would be helpful for
MediaHub — a full audit of the repo and where it could fit — and to run the
decision through the repo's governance (`llm-council` → ADR), as we did for
CloakBrowser, 9router, AgentMemory and J-Code.

**What MediaCrawler actually is (verified from its repo, 2026-06-02):** a Python +
Playwright social-media crawler that maintains **logged-in browser sessions** (via
Chrome DevTools Protocol) specifically to *avoid reverse-engineering platform
anti-bot defences*. It scrapes **7 Chinese platforms only** — Xiaohongshu (RED),
Douyin, Kuaishou, Bilibili, Weibo, Baidu Tieba, Zhihu — pulling posts, nested
comments, creator profiles and downloadable media, into CSV/JSON/Excel/SQLite/
MySQL. It supports **no Western platforms** (no Instagram, Facebook, Twitter/X,
global TikTok, YouTube, LinkedIn). It ships under a custom **"Non-Commercial
Learning License 1.1"**: content is "for learning/reference only," **commercial
use is prohibited**, and it "may not be used for large-scale crawling or activities
that disrupt platform operations." Not an OSI-approved licence.

**What MediaHub is:** a commercial, multi-tenant SaaS for UK/EU swimming clubs,
universities and societies. It turns structured sport results into ranked, branded,
ready-to-post content for **Instagram / Facebook / TikTok**, cares about EU/UK GDPR
(it already self-hosts fonts over the Munich CDN-Google-Fonts ruling), and its moat
is the intelligence layer — *explainable, auditable, source-grounded, human
approval before any publishing*. Its only browser use is **first-party**
server-side Playwright rendering its own HTML→PNG (plus Remotion video). It does
not scrape third parties.

**Where it would notionally "fit" — and why that slot is already filled.** The only
plausible insertion point is *learning a club's brand voice from its existing
social presence*. MediaHub already does this with
`brand/link_learners/` + `brand/link_handlers/{instagram,facebook,twitter,tiktok,linkedin,website}.py`:
an LLM-driven **polite** learner that reads a club's *public* profile via og:meta /
oembed / embed endpoints / a reader proxy, persists the strategy via
`brand/playbooks`, and stays GDPR-safe, ToS-respecting and auditable. The outbound
side (`publishing/buffer.py`, human-gated) handles posting. MediaCrawler targets
the wrong platforms with the wrong method for this need.

# 2. Decision

**Do not integrate, vendor, or list MediaCrawler — in any form, now or "for
later."** Not as a dependency, not as a vendored copy, not as an optional/dev
dependency, not as a documented workflow. MediaHub's social-ingestion path stays
the polite, public-read `brand/link_learners/` design; its outbound path stays the
human-gated publishing subsystem.

# 3. Reasoning (council verdict, unanimous 5/5)

- **License is a hard bar (revenue-attached).** A non-commercial licence cannot
  ship in a paid SaaS. This is the *same* load-bearing reason the repo rejected
  9router ("license/ToS exposure tied to revenue"). It also collides with the
  `DEPENDENCY_LICENSING.md` "truly free to self-host, licence-clear" register.
- **Platform mismatch is total, not partial.** Seven Chinese platforms; zero of
  MediaHub's customer platforms. You cannot carve a use case from a tool that
  serves none of your use cases. Getting value would mean re-basing the entire
  customer market onto Chinese platforms — a different company, not adjacent
  growth.
- **It contradicts the moat and the principles.** Logged-in session crawling built
  to *bypass anti-bot defences* is the inverse of "explainable, auditable, human
  approval, GDPR-clean." It is the CloakBrowser verdict again: *the legitimate path
  is proper ingestion (official exports, club uploads, public-and-polite reads),
  never evasion.*
- **The need is already met, better.** `brand/link_learners/` already learns club
  voice from public data without the legal, ToS or GDPR exposure. There is no gap
  to fill.
- **Multi-tenant security.** A CDP session manager holding live per-club cookies
  server-side across tenants is an IDOR / credential-leak surface MediaHub has no
  reason to take on.

# 4. The durable principle (so this can't recur platform-by-platform)

> **MediaHub ingests data it is *given* (uploads, official exports, partner feeds)
> or that is *public and politely readable* (og:meta / oembed / public pages). It
> never uses logged-in or anti-bot scraping — on any platform, Western or
> otherwise.**

A future "competitive benchmarking" or "trend" request is answered by that
principle, not re-litigated. The most GDPR-safe source of a club's voice is
*club-uploaded* exemplars (already modelled as the `exemplar_post` media-asset
type).

# 5. Consequences & follow-up

- **No code changes.** Routes, AI surfaces and the deterministic engine are
  untouched. This ADR + the council record are the only artifacts.
- **The decision is durable and auditable** — a documented "we evaluated and
  declined a logged-in social crawler," useful to risk-averse institutional buyers,
  alongside the CloakBrowser / 9router / AgentMemory / J-Code declines.
- **Enforcement follow-up (council blind-spot, carried over from the CloakBrowser
  ADR):** add a CI dependency-policy / SBOM check that blocks non-commercial-
  licensed and anti-detection / bot-evasion packages from entering the dependency
  graph, so a future "drop-in scraper" can't ride in unexamined. Tracked
  separately; not implemented by this ADR.
- **If genuine non-results social ingestion is ever needed**, extend the polite
  `brand/link_learners/` path or accept club-uploaded exemplars — never a logged-in
  crawler; and any Chinese-platform reach (not a current need) would require a
  commercially-licensed, ToS-compliant source.
