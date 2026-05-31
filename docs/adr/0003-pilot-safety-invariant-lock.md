# 3. Build the pilot-safety invariant lock before the next feature

- **Status:** Accepted — implemented in this change.
- **Date:** 2026-05-31
- **Deciders:** the Council (chairman verdict), under the authority established in
  [`0002-council-as-decision-authority.md`](0002-council-as-decision-authority.md).
- **Council artifacts (ephemeral, gitignored):**
  `autotest/reports/council/council-transcript-20260531-020731.md` and
  `council-report-20260531-020731.html`.

## The question put to the Council

What is the single highest-leverage thing to build NEXT to most increase the odds
clubs actually *pay* for MediaHub — and the concrete first shippable unit? Options:
(a) Generative Content Engine v2 (fix the "samey graphic" complaint); (b) pilot with
one real club; (c) athletics sport expansion; (d) athlete-facing `/athlete/<slug>`
share links; (e) harden known issues (IDOR / no isolation / caption truncation / PDF
gibberish).

## The verdict

- **Agreement (3 of 5 advisors, independently):** the product has zero real-world
  signal — 678 green tests, but no club has ever used it. "Samey graphics" is an
  *internal* complaint, not a validated reason a sale dies. The genuine precondition
  before any pilot or athlete-facing surface is **safe handling of minors' competition
  data.**
- **Clash:** the Executor wanted to fix the output first (ship one new archetype); the
  Expansionist wanted the athlete-share-link demand loop. Anonymous peer review
  decisively flagged both as the biggest blind spots (D ×3, A ×2): each ships minors'
  PB data onto a surface *before* the safety floor is proven. Four of five reviewers
  rated the First-Principles response strongest; the fifth rated the Contrarian
  strongest — and both reach the same conclusion.
- **Blind spots peer review caught:** willingness-to-pay is undefined (everyone
  optimised for "they post," not "they pay"); minors'-data handling is a
  safeguarding/consent question, not merely an IDOR fix.

**Recommendation:** build the pilot-safety floor for minors' data — and lock it so it
can't regress.

## Deviation from the verdict's premise (recorded, not silent)

The verdict assumed an *open* cross-tenant IDOR ("anyone with a run id can read its
cards", per the then-current `KNOWN_ISSUES.md`). Hands-on investigation during the
build showed that premise is **false**: cross-organisation access is already enforced
by `_can_access_run` at all 37 run-route call sites and regression-tested in
`tests/test_cross_tenant_access.py`. Shipping "signed run IDs" now would duplicate
existing protection.

The concrete unit was therefore refined (per the governance rule that deviations are
written into the record): instead of re-implementing protection that exists, **lock
the existing guarantee as an invariant** so a future route cannot silently reintroduce
the leak.

## What was built

- `tests/test_run_route_isolation_invariant.py` — introspects the live `app.url_map`,
  finds **every** route taking a `run_id`, hits each from a foreign organisation's
  session, and asserts none leaks the owner's data. It fails loudly if a new run route
  appears that the invariant can't reach (forcing the maintainer to confirm the new
  route is guarded), and guards against silently covering nothing (`>= 20` routes
  swept). A positive control confirms the owner is not locked out.
- `docs/KNOWN_ISSUES.md` — corrected the stale "anyone with a run id can read its
  cards" entry to describe the true residual: run-ids are 48-bit random rather than
  HMAC-signed (a *defence-in-depth* gap), and owner-less legacy runs stay readable by
  design. The cross-tenant hole itself is closed.

## Consequences

- The cross-tenant isolation guarantee for minors' competition data is now an enforced
  invariant across all current and future run routes — the safety precondition for a
  real-club pilot is met and protected from regression.
- **Follow-ups the Council surfaced, not addressed here:** (1) signed/HMAC run tokens
  as defence-in-depth against in-org guessing; (2) a willingness-to-pay experiment
  design for the pilot; (3) explicit minors'-data consent/safeguarding handling. These
  are recorded for a future decision, not silently dropped.
