# Council Governance — how decisions get made in MediaHub

> **In plain words.** Big or contested decisions in this repo are not made by a
> single voice (human or AI) on a hunch. They go through **the Council**: five
> advisors argue from clashing angles, peer-review each other anonymously, and a
> chairman writes a binding verdict. The verdict — not anyone's first instinct —
> is what we build. This file says *which* decisions must go through the council,
> *how* to run one, and *what* counts as a valid decision record.

The council is the methodology in [`autotest/skills/llm-council/SKILL.md`](../autotest/skills/llm-council/SKILL.md)
(Karpathy's LLM Council), already embedded in the autonomous tester as
[`autotest/council.py`](../autotest/council.py) where it adjudicates the semantic
sub-agents' findings. This document promotes it from "a tool that's there" to **the
repo's decision authority**.

---

## 1. What the council decides (and what it doesn't)

The council is for decisions where **being wrong is expensive** and where reasonable
people could disagree. Run it *before* the change, and let its verdict drive the work.

**Council-gated — you MUST convene the council before acting:**

- **Architecture & data model** — new package or major module, schema change, a new
  persisted shape under `DATA_DIR`, changing a public route's contract.
- **Removing or replacing a route or data structure** — the council decision comes
  *before* CLAUDE.md's 15-step breakage check, and is recorded alongside it.
- **Roadmap priority & sequencing** — "what do we build next", reordering phases,
  starting a new `docs/ROADMAP.md` work-item.
- **Competing approaches** — any time there are ≥2 credible ways to do something and
  the cost of the wrong pick is more than an afternoon's rework.
- **AI-surface boundary calls** — introducing a new judgement surface, or any proposal
  that touches the deterministic-engine boundary (parsers, detectors, ranker,
  colour-science). The council cannot *approve* Gemini-ifying the deterministic engine
  — that still needs explicit user sign-off — but it must be consulted on the framing.
- **Anything outward-facing or hard to reverse** — publishing, deployment-shape
  changes, external integrations, pricing/commercial surfaces.

**Not council-gated — just do it (the council explicitly warns against trivial use):**

- Typo/comment/docstring fixes, formatting, mechanical refactors with one obvious form.
- A bug with a single correct fix and no design choice.
- Implementing a step whose design the council *already* decided (cite that decision).
- Routine dependency bumps and test-only changes that assert existing behaviour.

> Rule of thumb from the skill: *"Don't council trivial questions. If the question has
> one right answer, just answer it."* Counciling a typo wastes the mechanism and dulls
> it for the decisions that matter.

---

## 2. How to convene the council

1. **Frame the question** neutrally, enriched with repo context (`CLAUDE.md`,
   `docs/ROADMAP.md`, `docs/KNOWN_ISSUES.md`, the files in scope). State the real
   options and what's at stake. Don't pre-bias toward your preferred answer.
2. **Five advisors, in parallel** — Contrarian, First-Principles, Expansionist,
   Outsider, Executor (see the SKILL). Each leans fully into its angle.
3. **Anonymise A–E and peer-review** — each advisor critiques all five blind, naming
   the strongest response, the biggest blind spot, and what everyone missed.
4. **Chairman synthesis** — agreements, clashes, blind spots, a *clear* recommendation
   (not "it depends"), and the one concrete first step.
5. **Record it** (§3) and **build the verdict.**

You can drive this interactively via the `llm-council` skill, or in-process via
`autotest/council.py` during a tester sweep. Both honour the no-API-key rule
(subscription/CLI token only) and self-skip cleanly when no provider is available.

---

## 3. The decision record (the binding artifact)

Every council-gated change produces a decision record at **two levels**:

1. **The durable, committed record — an ADR in [`docs/adr/`](adr/)** (e.g.
   `0002-council-as-decision-authority.md`). This is the canonical, version-controlled
   statement of *what was decided and why*, following the existing ADR convention
   (Status / Date / Deciders / Context / Decision / Consequences). **This is what the
   PR links.**
2. **The rich, ephemeral artifacts — under [`autotest/reports/council/`](../autotest/reports/council/)**
   (gitignored runtime output): the full transcript and the scannable HTML briefing.
   ```
   council-transcript-<YYYYMMDD-HHMMSS>.md   # framed question, 5 responses, peer reviews, verdict
   council-report-<YYYYMMDD-HHMMSS>.html     # scannable visual briefing
   ```
   Keep them for reference and for re-counciling the same ground later; they are not
   committed (they're regenerated output, not source of truth).

- The chairman's verdict is **binding for the change it governs.** If the build deviates
  from the verdict (e.g. hands-on investigation invalidates a premise — as happened on
  2026-05-31, when the prioritised IDOR turned out already fixed), the deviation and its
  reason are written *into the ADR*, not done silently.
- The **PR body must link the ADR** (the autotest loop already carries the council's
  reasoning into the PR body — see commit `aaab9da`). A council-gated PR with no linked
  decision record is incomplete.

---

## 4. Enforcement

Two levels. The repo ships with **advisory/process** on by default; **binding CI** is
opt-in because it requires an LLM credential in CI and adds per-PR cost (see below).

| Level | Mechanism | Default |
|---|---|---|
| **Advisory / process** | This document + the `CLAUDE.md` *Decision governance* rule. Agents and contributors run the council before council-gated work and link the decision record in the PR. | **On** |
| **Binding CI gate** | A CI job runs (or verifies the presence of) a council decision record for PRs that touch council-gated paths, and blocks merge without one. Requires a provider token available to CI and incurs a small per-PR LLM cost. | **Off** (opt-in) |

The advisory level is deliberately the default: a hard CI gate that calls an LLM on
every qualifying PR costs money and can block the trunk, which conflicts with the
"green trunk auto-deploys" model. Turn it on consciously, not by accident.

---

## 5. Why govern this way

- **Anti-sycophancy.** A single model (or a single engineer) rationalises whatever it
  already leans toward. Five clashing advisors plus anonymous peer review surface the
  blind spot before it ships — that is the whole point of the council.
- **Explainable & auditable.** Every council-gated decision leaves a transcript and a
  verdict in the repo. This matches MediaHub's standing rule that *every step should be
  explainable and auditable*.
- **It scales with the repo, not the person.** New contributors and autonomous agents
  inherit the same decision discipline by reading one file.
