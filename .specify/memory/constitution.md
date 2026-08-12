<!--
Sync Impact Report
- Version change: 1.1.0 → 1.2.0
- Modified principles: none (all 6 Core Principles unchanged)
- Added sections: none new; Security & Data Handling materially expanded with an
  authentication/access-control paragraph (manager identity MUST be verified before any
  review data or approve/reject/publish action is exposed)
- Removed sections: none
- Reason: /speckit-analyze on feature 001-reputation-sentinel found (finding C3) that no
  requirement, plan, or task authenticated who could act as "the manager" in the UI —
  a gap undermining Principle I's brand-safety premise. Remediated together with spec.md
  FR-019/SC-007 and new tasks T019/T052.
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — Constraints slot already generic, no edit needed
  - ✅ .specify/templates/spec-template.md — no constitution-specific references, no edit needed
  - ✅ .specify/templates/tasks-template.md — no constitution-specific references, no edit needed
  - ✅ .specify/templates/checklist-template.md — no constitution-specific references, no edit needed
  - ✅ specs/001-reputation-sentinel/spec.md — FR-019, SC-007 added; plan.md Technical Context
    and Constraints updated; tasks.md T019/T052 added
- Follow-up TODOs: none

Prior report (1.1.0):
- Version change: 1.0.0 → 1.1.0
- Modified principles: none (all 6 Core Principles unchanged)
- Added sections: Technology Constraints (new — mandates Streamlit web UI for deployability,
  requested directly ahead of /speckit-plan for feature 001-reputation-sentinel)
- Removed sections: none

Prior report (1.0.0, initial ratification):
- Version change: none (template, unratified) → 1.0.0
- Modified principles: none (initial ratification, all 6 principles newly defined)
  - I. Human-in-the-Loop Non-Negotiable (new)
  - II. Single-Responsibility Agent Architecture (new)
  - III. Spec-Driven Development (new)
  - IV. Production-Readiness by Default (new)
  - V. Timebox-Aware Simplicity (YAGNI) (new)
  - VI. Purposeful Technology Diversity (new)
- Added sections: Security & Data Handling; Development Workflow; Governance
-->

# Reputation Sentinel Ops Constitution

## Core Principles

### I. Human-in-the-Loop Non-Negotiable

Every externally-visible, public-facing action (publishing a reply to a customer review, or
any other write that becomes visible outside the system) MUST be explicitly approved by a
human manager before it happens. No agent may autonomously publish, post, or otherwise act
on the business's public presence. This is a brand-safety rule, not a convenience default —
it MUST NOT be relaxed, bypassed, or overridden by any other principle, optimization, or
time pressure, including hackathon deadlines. If a feature cannot be built with this gate
intact within the available time, the feature is cut, not the gate.

**Rationale**: An autonomous, wrongly-worded, or context-blind public reply on a customer
review is a reputational risk the system exists to prevent, not create.

### II. Single-Responsibility Agent Architecture

Each agent (Ingestion, Analysis, Triage, Draft, Reporting) owns exactly one clear
responsibility, is independently testable, and is independently deployable/replaceable
without requiring changes to the other agents. The Orchestrator is the only component
responsible for sequencing and coordinating agents. Combining two agents' responsibilities
into one for the sake of a shortcut is a violation, even under time pressure — it MUST be
resolved by simplifying scope (Principle V), not by merging agent responsibilities.

**Rationale**: Separable agents can be built, tested, demoed, and scored independently, and
map directly to the "integrasi komponen agent yang tangguh" judging criterion.

### III. Spec-Driven Development

No implementation work begins without an approved spec. Every feature MUST pass through
`specify → plan → tasks` before any code is written, and every task MUST trace back to a
requirement in the approved spec. Code that does not trace to a spec requirement is out of
scope until the spec is updated first.

**Rationale**: Keeps scope explicit and auditable, and is itself the practice being scored
under the hackathon's Specification Driven Development bonus.

### IV. Production-Readiness by Default

Every integration with an external API (Google Business Profile API, Gemini, or any other
third-party service) MUST implement error handling and retry/backoff, and MUST have a
fallback path (e.g., seed/sample data) so a demo does not fail outright when an external
service is slow or unavailable. Happy-path-only code is NOT acceptable for any feature that
will be exercised during the demo.

**Rationale**: Directly targets the Production Readiness judging criterion and protects the
one shot the team gets at Final Demo Day.

### V. Timebox-Aware Simplicity (YAGNI)

Given the hackathon's fixed, tight deadline, MVP scope MUST stay exactly as narrow as agreed
in the feature's Build Scope. Features explicitly marked out-of-scope (e.g., the Geo
Benchmark Layer, Slack/email notifications, full historical review backfill) MUST NOT be
implemented "along the way" without first updating the spec. Adding scope silently during
implementation is a constitution violation, not initiative.

**Rationale**: Scope creep under a hard deadline is the most common way hackathon
submissions end up half-finished instead of demo-ready.

### VI. Purposeful Technology Diversity

Every technology choice (Google ADK, Gemini, GCP services, etc.) MUST have a clear
functional justification tied to a requirement. Adding a technology solely to inflate the
"Keragaman Teknologi" score, with no functional justification, is NOT acceptable.

**Rationale**: Technology breadth should be a side effect of solving the problem well, not a
goal pursued for its own sake — genuine diversity reads as more credible to judges than
padding.

## Security & Data Handling

Google Business Profile OAuth credentials for each branch MUST be stored securely (e.g., a
secrets manager or encrypted store) and MUST NOT be hardcoded or committed in plaintext
anywhere in the repository. Customer review data (reviewer name, review text) MUST be
treated as sensitive: it MUST NOT be logged beyond what is strictly necessary for debugging,
and debug logs containing review content MUST NOT be retained longer than needed to resolve
the issue they were captured for.

The manager-facing UI MUST NOT expose any review data or approve/reject/publish action to an
unauthenticated visitor. Every action that results in a Principle I approval MUST be
attributable to a specific, authenticated manager identity — never a free-text or
client-supplied approver value. An unauthenticated public deployment is treated as a
violation of this section, not an acceptable MVP shortcut, because it undermines Principle
I's entire premise (a human gate only means something if the human is verified).

## Technology Constraints

The manager-facing UI (Principle-driven requirement: FR-018 in the feature spec) MUST be
built with **Streamlit**. This is a fixed, project-wide technology constraint, not a
per-feature choice — it MUST be honored by every `/speckit-plan` Technical Context for this
project. Rationale: the agent stack (Google ADK, Gemini) is already Python-native, so
Streamlit avoids a second language/runtime for the UI; it renders a working, deployable app
(Cloud Run-compatible) fast enough to fit the hackathon timebox (Principle V) while still
satisfying the submission requirement to demonstrate a running application. Any deviation
from Streamlit for this UI MUST be recorded as a Complexity Tracking entry in the plan with
an explicit justification, per Governance below.

## Development Workflow

Feature work follows the Spec Kit lifecycle: `/speckit-specify` → (optional
`/speckit-clarify`) → `/speckit-plan` → `/speckit-tasks` → (optional `/speckit-analyze`) →
`/speckit-implement`. The `/speckit-plan` Constitution Check gate MUST explicitly verify the
plan against all six Core Principles above before Phase 0 research begins, and MUST be
re-checked after Phase 1 design. Any plan that cannot satisfy a principle as-is MUST record
the conflict in that plan's Complexity Tracking table rather than silently deviating.

## Governance

This constitution supersedes any ad-hoc decision made during planning or implementation. Any
trade-off that conflicts with a Core Principle MUST be explicitly documented — including the
principle affected, why the trade-off is being made, and what simpler alternative was
rejected and why — before implementation proceeds; undocumented deviation from a principle
is not permitted regardless of time pressure.

Amendments to this constitution require: (1) the change written into this file, (2) the
version bumped per semantic versioning (MAJOR for incompatible principle removal/redefinition,
MINOR for a new principle or materially expanded guidance, PATCH for wording/clarification
only), and (3) the Sync Impact Report at the top of this file updated to describe the change.
All plans and task lists produced after an amendment MUST be checked against the amended
version, not a cached earlier reading.

**Version**: 1.2.0 | **Ratified**: 2026-08-11 | **Last Amended**: 2026-08-11
