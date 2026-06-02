# Council transcript — Should MediaHub integrate MediaCrawler?

**Run:** 2026-06-02 (`20260602T233537Z`) · **Skill:** `llm-council` (5 advisors →
anonymised peer review → chairman) · **Outcome:** Unanimous decline (5/5).
**Decision record:** [`docs/adr/0002-decline-mediacrawler-integration.md`](../../../docs/adr/0002-decline-mediacrawler-integration.md).

---

## Original question

> Where would integrating <https://github.com/NanmiCoder/MediaCrawler> be helpful
> for my repo? Full audit of the repo and where it could fit.

## Framed question (given to all five advisors)

Should MediaHub integrate NanmiCoder/MediaCrawler, and if so where — or decline?

**What MediaCrawler is (verified from its repo, 2026-06-02):** a Python +
Playwright social-media crawler that maintains *logged-in browser sessions* (via
Chrome DevTools Protocol) to bypass anti-bot defences. It scrapes **7 Chinese
platforms only** — Xiaohongshu (RED), Douyin, Kuaishou, Bilibili, Weibo, Baidu
Tieba, Zhihu — extracting posts, nested comments, creator profiles, and
downloading media; stores to CSV/JSON/Excel/SQLite/MySQL. It supports **no
Western platforms** (no Instagram, Facebook, Twitter/X, global TikTok, YouTube,
LinkedIn). License: a custom **"Non-Commercial Learning License 1.1"** that
explicitly states it is for learning/reference only, **commercial use is
prohibited**, and it "may not be used for large-scale crawling or activities that
disrupt platform operations." Not OSI-approved.

**What MediaHub is:** a commercial, multi-tenant SaaS for UK/EU swimming clubs,
universities and societies. It turns structured sport results into ranked,
branded, ready-to-post content for Instagram/Facebook/TikTok. It cares about
EU/UK GDPR (it already self-hosts fonts over the Munich CDN-Google-Fonts ruling).
Its moat is the intelligence layer: explainable, auditable, source-grounded, with
**human approval before any publishing**. Its only current browser use is
*first-party* server-side Playwright rendering its own HTML→PNG, plus Remotion
video. It **already** has the subsystem MediaCrawler would slot into:
`brand/link_learners/` + `brand/link_handlers/{instagram,facebook,twitter,tiktok,linkedin}.py`
— an LLM-driven *polite* learner that reads a club's public profile via og:meta /
oembed / embed endpoints / jina.ai reader to learn the club's brand voice, plus a
human-gated `publishing/` subsystem. Precedent: the repo previously declined
analogous integrations after a council vote, each recorded as an ADR — CloakBrowser
(bot-evasion browser; "the legitimate path is proper ingestion, never evasion")
and 9router (gray-market LLM proxy; "license/ToS exposure tied to revenue" was
decisive).

**Anonymisation mapping (revealed):** A = Expansionist · B = Outsider ·
C = Contrarian · D = Executor · E = First Principles Thinker.

---

## Advisor responses

### The Contrarian (Response C)

This is a dead deal. Three kill shots. **(1) The license is an absolute bar.**
"Non-Commercial Learning License 1.1" does not merely restrict commercial use — it
explicitly prohibits it. MediaHub is a commercial SaaS charging customers money.
No legal grey zone, no carve-out, no "we're just referencing the code." The repo
already declined 9router because "license/ToS exposure tied to revenue was
decisive." Identical. Following the precedent is applying existing policy.
**(2) Platform mismatch is total, not partial.** MediaCrawler supports zero of
MediaHub's target platforms. Xiaohongshu is not Instagram; Douyin is not global
TikTok. You cannot carve a use case from a tool that serves none of your use
cases. **(3) `brand/link_learners/` already exists and is architecturally
superior.** MediaHub already has polite, meta-tag-and-oembed-based brand learning
— GDPR-safe, ToS-compliant, auditable: exactly what the moat requires. A logged-in
session crawler that "bypasses anti-bot defences" directly contradicts the
GDPR-cleanliness and auditability that justify the pricing premium. Decline. Write
the ADR. Move on.

### The First Principles Thinker (Response E)

"Should MediaHub integrate MediaCrawler?" is the wrong question. The right one:
*what problem does MediaHub actually have?* MediaHub's moat is structured data in →
intelligence layer → branded content out. The club provides results files;
MediaHub detects, ranks, captions; the human approves. MediaHub never needed to
*crawl* anything — crawling is the wrong input type entirely. What would
MediaCrawler add? Chinese platforms only (users post to Instagram/Facebook/TikTok).
Logged-in session scraping — the exact antithesis of MediaHub's GDPR-clean,
auditable, source-grounded promise. The "brand voice learning" problem — the only
plausible use — is already solved via `brand/link_learners/` using public og:meta,
oembed and jina.ai. The problem is solved; there is no gap. The real trap is
integration-for-integration's-sake: someone saw a crawler and pattern-matched it
to "MediaHub handles social content." It does not fit because MediaHub ingests
structured results; its social-platform interaction is *publishing*, not
*scraping*. Decline — not (only) for the license, but because it solves a problem
MediaHub does not have, via a mechanism that contradicts what MediaHub is.

### The Expansionist (Response A)

The bull case here is essentially zero, and I'll say that plainly because finding
upside is my job and finding none is itself a strong signal. MediaHub's customers
are UK/EU swimming clubs, universities, societies. MediaCrawler's entire surface
covers seven Chinese platforms. There is no product overlap — not "weak overlap,"
none. The expansion opportunity collapses immediately: MediaHub would have to pivot
its entire customer base to Chinese platforms to get any value, and that is a
different company, not adjacent growth. The one angle I genuinely looked for: could
MediaCrawler's session-persistence/CDP patterns inform MediaHub's own
`link_learners`? No — that architecture is deliberately polite (og:meta, oembed,
jina.ai); importing anti-bot evasion patterns even as reference pushes the design
the wrong way and undermines the auditability moat. The non-commercial license
forecloses any bull case: the moment it generates value commercially it is
prohibited. The only "upside" I can construct is a developer reading the code
out-of-repo for personal education — which needs no integration decision at all.
Decline. No carve-out. The CloakBrowser ADR ("the legitimate path is proper
ingestion, never evasion") already states the principle.

### The Outsider (Response B)

Looking at this fresh, knowing nothing about swimming clubs or SaaS. What is
MediaHub being asked to add? A tool that secretly logs into Chinese social
platforms as a fake user to scrape data those platforms explicitly don't want
scraped — and the tool's own license says "don't use this commercially."
MediaHub's pitch is "trust us, we're above-board, we require human approval, we're
GDPR-compliant" — the trustworthy one. Does secretly crawling Weibo by
impersonating a logged-in user make MediaHub more trustworthy? No — it makes them
the opposite thing. And: MediaHub serves UK/EU swim clubs. Who needs Xiaohongshu
data? Manchester clubs posting to Instagram and TikTok don't need Douyin scraped.
There is no customer here. The "narrow carve-out" makes no sense either — you can't
do a "narrow" version of logging into someone's account without permission. The
license says no commercial use; MediaHub is commercial; that's not a gray area,
that's just illegal use. From outside, this looks like "should we bolt a
shoplifting device onto our ethical product, even though our customers don't need
to shoplift anything?" Obviously no. Decline cleanly.

### The Executor (Response D)

Monday-morning integration path: it dead-ends before step 3. **Step 1:** install
MediaCrawler — immediately you hit the Non-Commercial license; MediaHub is a
commercial SaaS; conversation over legally. **Step 2 (ignore the license):**
Xiaohongshu/Douyin/Kuaishou/Bilibili/Weibo/Tieba/Zhihu vs UK clubs on
Instagram/Facebook/TikTok/X — zero platform overlap, no shared target, so there is
no integration path. **Step 3 (ignore both):** MediaCrawler runs logged-in browser
sessions via CDP to bypass anti-bot defences; MediaHub already does polite
og:meta/oembed reads. You'd swap a lightweight compliant reader for a heavy CDP
session manager that violates every Western platform's ToS, needing persistent
server-side cookies across multi-tenant runs — an IDOR and credential-leakage
nightmare. Decline, write an ADR, move on. If the real need is "learn brand voice
from a club's profile," `link_learners/` already does it risk-free. That's the
Monday morning: improve what's already there.

---

## Peer review (anonymised; reviewers saw A–E only)

**Review 1.** Strongest: **E** — reframes correctly; the issue isn't only
license/mismatch/compliance, it's that MediaCrawler solves a problem MediaHub
doesn't have (crawling is the wrong input paradigm; MediaHub ingests structured
results and publishes). Biggest blind spot: **C** — "applying existing policy, not
a council question" is circular; the council exists to pressure-test whether the
policy applies cleanly. Missed by all: **supply-chain risk** — even read-only,
session-scraping code in a GDPR-regulated SaaS codebase creates audit/regulatory
surface independent of whether it's called; a GDPR auditor or enterprise customer
reviewing the dependency tree flags it regardless of code paths.

**Review 2.** Strongest: **E** — category error, not just a policy violation; "no
gap exists" because `link_learners` already covers the one plausible use is the
most precise kill shot. Biggest blind spot: **A** — dismisses the
CDP/session-persistence angle too quickly without asking whether a *legitimate*
Western-platform crawler (different tool, compliant license) could ever be useful.
Missed by all: the *supply side* — MediaHub could learn brand voice from
*club-uploaded examples* (consensual, GDPR-safe), rendering the crawling question
permanently moot.

**Review 3.** Strongest: **B** — names the moral contradiction precisely (the
commercial differentiator is being the trustworthy/GDPR-clean option; secret
logged-in crawling is categorically antithetical) and correctly calls "narrow
carve-out" conceptually incoherent. Biggest blind spot: **C** — "existing policy,
not a council question" is circular; defaulting to "an ADR covers it" is how policy
calculus atrophies. Missed by all: **supply-chain / dependency-poisoning risk** —
what does MediaCrawler pull in transitively (Playwright with persistent
authenticated sessions, anti-detection libraries)? Even uncalled, bundling it puts
those in the production container.

**Review 4.** Strongest: **B** — leads with the product-level ethical
contradiction and disposes of the "carve-out" as *incoherent*, not merely
unappealing. Biggest blind spot: **E** — "MediaHub never needed to crawl" doesn't
survive a future customer asking for competitive benchmarking / trend-scraping;
declining is right but needs a durable principle. Missed by all: importing
MediaCrawler even as a dev/evaluation dependency brings session-persistence code
and transitive deps into the dependency graph — the ADR should explicitly prohibit
vendoring or listing it even as optional.

**Review 5.** Strongest: **B** — names the ethical contradiction with precision
("shoplifting device on an ethical product") and closes the carve-out escape hatch.
Biggest blind spot: **E** — argues MediaHub "never crawls," but `link_learners`
*does* read public posts politely; the load-bearing distinction is *polite public
read* vs *logged-in session scrape*, not crawl vs no-crawl. Missed by all:
contributor/supply-chain risk — having evasion patterns in the repo normalises
anti-detection code, creates audit liability if the repo is reviewed by a platform
or regulator, and sets a precedent the 9router ADR was partly designed to prevent.

---

## Chairman verdict

### Where the council agrees

Unanimous (5/5) decline, converged independently from all five lenses:

- **The license is disqualifying.** "Non-Commercial Learning License 1.1"
  explicitly prohibits commercial use; MediaHub is a paid SaaS. This maps 1:1 onto
  the repo's 9router decline ("license/ToS exposure tied to revenue").
- **Platform mismatch is total, not partial.** Seven Chinese platforms vs UK/EU
  clubs on Instagram/Facebook/TikTok/X — zero overlap. You cannot carve a use case
  from a tool that serves none of your use cases.
- **The one plausible use is already solved, better.** `brand/link_learners/`
  learns a club's brand voice via polite public reads (og:meta/oembed/jina.ai) —
  GDPR-safe, ToS-compliant, auditable. MediaCrawler's logged-in session crawling
  is the antithesis.
- **It contradicts the moat.** MediaHub sells explainable/auditable/human-approval/
  GDPR-clean. Logged-in impersonation crawling is "the legitimate path is proper
  ingestion, never evasion" (CloakBrowser ADR) all over again.

### Where the council clashes

Only on *why*, and on residual escape hatches — not on the verdict:

- **Category error vs compliance failure.** First Principles frames it as a
  category error (MediaHub ingests structured results and *publishes*; it doesn't
  scrape); the others lead with license/ToS/platform. Both are right and
  complementary. Peer review flagged that First Principles slightly overshoots by
  saying MediaHub "never crawls" — it *does* read public pages politely via
  `link_learners`; the load-bearing distinction is **polite public read vs
  logged-in session scrape**, not crawl vs no-crawl.
- **"Not even a council question."** The Contrarian's "this is just existing
  policy" was flagged twice as circular: the council exists precisely to test
  whether the 9router/CloakBrowser reasoning transfers cleanly. It does — but you
  confirm that by running it, which is what happened here.

### Blind spots the council caught (peer-review round)

- **Supply-chain / dependency hygiene (unanimous new point).** Even *vendoring or
  listing* MediaCrawler — never calling it, "for reference only" — drags
  session-persistence/anti-detection code and transitive deps into the dependency
  graph and the production container, creating audit/regulatory exposure and ToS
  entanglement *by association* during any GDPR or enterprise-procurement review.
  The decline must prohibit vendoring/listing it even as an optional/dev dependency,
  and is a candidate for the CI dependency-policy/SBOM guard the CloakBrowser ADR
  already proposed.
- **The decline needs a durable principle, not "no need today."** If a future
  customer asks for competitive benchmarking / trend scraping, the answer cannot be
  "we didn't need it in June 2026." Durable principle: **MediaHub ingests data it
  is *given*, or that is *public and politely readable*, and never uses logged-in /
  anti-bot scraping — independent of platform.**
- **The most GDPR-safe "learn our voice" supply is consensual.** Club-*uploaded*
  exemplars (past captions/images — already modelled as the `exemplar_post` asset
  type) moot the crawling question entirely.

### The recommendation

**Decline. Do not integrate, vendor, or list MediaCrawler — in any form, now or
"for later."** Record it as an ADR in the same series as CloakBrowser/9router so
the question can't quietly recur. If a genuine "learn the club's voice from social"
need grows beyond what `brand/link_learners/` covers, extend that
polite-public-read path or accept club-uploaded exemplars — never a logged-in /
anti-bot crawler. If MediaHub ever genuinely needed Chinese-platform reach (it
doesn't, for UK/EU clubs), that would require a *commercially-licensed,
ToS-compliant* data source, not MediaCrawler.

### The one thing to do first

Write `docs/adr/0002-decline-mediacrawler-integration.md` (this decision), and — as
the durable enforcement the council asked for — open a follow-up to add a CI
dependency-policy/SBOM check that blocks non-commercial-licensed and anti-detection
packages from entering the dependency graph (the same guard the CloakBrowser ADR
left as a follow-up).
