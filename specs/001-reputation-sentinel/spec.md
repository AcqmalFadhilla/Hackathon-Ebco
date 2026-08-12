# Feature Specification: Reputation Sentinel Ops

**Feature Branch**: `001-reputation-sentinel`

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "Reputation Sentinel Ops: sistem multi-agent (5 sub-agent + orchestrator) yang memantau dan menjaga reputasi bisnis multi-cabang lewat review Google Business Profile. Ingestion Agent, Analysis Agent, Triage Agent, Draft Agent, Reporting Agent, dikoordinasi Orchestrator dengan human-approval gate wajib sebelum publish. Out of scope MVP: Geo Benchmark/Competitive Intel Agent, notifikasi Slack/email, full historical backfill."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Multi-Branch Review Inbox (Priority: P1)

A business manager overseeing multiple branches wants to see all customer reviews from every connected branch in one place, already tagged with sentiment and complaint topic, instead of checking each branch's Google Business Profile separately.

**Why this priority**: This is the foundation every other capability builds on — without consolidated, tagged visibility there is nothing to triage, draft against, or report on. It is also independently useful: even alone, it saves managers from manually opening N separate dashboards.

**Independent Test**: Connect 2-3 demo branches, let reviews sync in, and verify the manager can view a single list of reviews across all branches, each showing sentiment (positive/neutral/negative) and topic tags — without generating or publishing any reply.

**Acceptance Scenarios**:

1. **Given** a manager has connected multiple branch locations, **When** a new review is posted on any connected branch's Google Business Profile, **Then** the review appears in the manager's unified inbox tagged with sentiment and topic within one ingestion cycle.
2. **Given** reviews exist across branches with mixed sentiment, **When** the manager filters the inbox by branch or by sentiment, **Then** only matching reviews are shown.

---

### User Story 2 - AI-Drafted Reply with Manager Approval (Priority: P2)

A manager wants a ready-to-send, personalized reply draft for each review so they can respond quickly, but must review and approve the exact wording before anything goes public under the business's name.

**Why this priority**: This is the core value proposition — turning passive review visibility into consistent, fast action — and is the headline capability judges/demo will evaluate. It directly targets the industry gap where most negative reviews go unanswered.

**Independent Test**: For a review in the unified inbox, verify a draft reply is generated automatically, the manager can edit/approve/reject it, and only an approved draft results in a reply being published back to the review, with publication status confirmed afterward.

**Acceptance Scenarios**:

1. **Given** a review has been ingested and analyzed, **When** the manager opens it, **Then** a personalized draft reply is already available for review.
2. **Given** a manager approves a draft reply as-is or after editing, **When** approval is submitted, **Then** the reply is published to the review and its publication status is confirmed and shown to the manager.
3. **Given** a manager rejects a draft reply, **When** rejection is submitted, **Then** no reply is published and the review is returned to the `drafted` state with a newly generated draft reply.
4. **Given** no manager has approved a draft, **When** any amount of time passes, **Then** the system never publishes that reply autonomously.

---

### User Story 3 - Urgent Review Escalation (Priority: P3)

A manager wants to be alerted immediately when a review signals a serious or urgent problem (e.g. safety, major service failure) so it doesn't sit unnoticed in a queue of routine reviews.

**Why this priority**: Severity-based escalation is what prevents the most damaging reviews from being treated the same as routine ones — it's a safety/trust differentiator, not just a convenience feature, and is the direct answer to the finding that 75% of negative reviews go unanswered.

**Independent Test**: Ingest a review with clearly urgent/severe content and verify it is flagged as urgent, visually separated from routine reviews, and triggers an alert to the branch's manager, independent of whether a draft reply has been approved yet.

**Acceptance Scenarios**:

1. **Given** a new review is analyzed, **When** its content indicates high severity (e.g. very negative sentiment plus a critical topic), **Then** it is marked "urgent" and shown separately from routine reviews.
2. **Given** a review is marked urgent, **When** the flag is set, **Then** the responsible branch manager receives an alert within a short, bounded time.
3. **Given** a review does not meet the urgency threshold, **When** it is analyzed, **Then** it is routed to the normal draft-and-approve flow without an alert.

---

### User Story 4 - Cross-Branch Review Health Digest (Priority: P4)

A manager overseeing many branches wants an on-demand summary ranking branches by overall review health, with the most common complaint topics per branch, to spot systemic problems without reading every individual review.

**Why this priority**: Valuable for oversight and for demonstrating production-grade reporting, but the business already gets its core value from Stories 1-3 without this; it's a polish/scale feature.

**Independent Test**: With reviews present across multiple branches, request a digest and verify it returns a ranked list of branches by health score along with each branch's top recurring complaint topics.

**Acceptance Scenarios**:

1. **Given** multiple branches have reviews with varying sentiment/severity, **When** the manager requests a digest, **Then** branches are ranked by a review health score from worst to best.
2. **Given** a branch has recurring complaint topics, **When** the digest is generated, **Then** those topics are listed for that branch alongside its ranking.

---

### Edge Cases

- What happens when a connected branch has zero reviews, or zero new reviews since the last sync?
- How does the system handle the Google Business Profile API being rate-limited or temporarily unavailable during ingestion?
- How does the system handle a review written in a language other than Indonesian or English?
- What happens when a review already has an existing owner reply (posted manually outside this system) before ingestion? (Resolved — see FR-020)
- What happens when a manager rejects a draft reply — does the system generate a revised draft, or leave the review pending indefinitely?
- What happens when a reply is approved by a manager but its publication is rejected or stuck pending by Google's moderation?
- What happens when two managers act on the same review's draft at the same time?
- What happens when a reviewer edits or deletes their review after a draft reply was already generated (but not yet approved)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a manager to connect one or more branch locations to their Google Business Profile for review monitoring.
- **FR-002**: System MUST retrieve customer reviews (rating, text, timestamp, reviewer name) for each connected branch.
- **FR-003**: System MUST classify each review's sentiment as positive, neutral, or negative.
- **FR-004**: System MUST tag each review with one or more recurring complaint/topic categories (e.g. service, cleanliness, price) when applicable.
- **FR-005**: System MUST correctly process reviews written in Indonesian or English.
- **FR-006**: System MUST assign a severity/urgency level to each review based on its content and sentiment.
- **FR-007**: System MUST flag reviews above a defined severity threshold as "urgent" and visually separate them from routine reviews.
- **FR-008**: System MUST alert the responsible branch manager when an urgent review is detected.
- **FR-009**: System MUST generate a draft reply for each review, personalized to the review's content and the business's tone of voice.
- **FR-010**: System MUST NOT publish any reply to a review without explicit manager approval.
- **FR-011**: Manager MUST be able to view, edit, approve, or reject a draft reply before it is published.
- **FR-012**: System MUST publish an approved reply to the corresponding review's public review page.
- **FR-013**: System MUST verify a reply's publication status after submission and inform the manager if publication failed or is still pending.
- **FR-014**: System MUST record who approved each published reply and when, for accountability.
- **FR-015**: System MUST generate an on-demand summary report ranking connected branches by a review health score.
- **FR-016**: System MUST include the most frequent complaint topics per branch in the summary report.
- **FR-017**: System MUST limit review ingestion to a configurable, recent time window per branch rather than full historical backfill.
- **FR-018**: System MUST provide a manager-facing web UI, deployed as a running application, through which a manager can view the unified review inbox, review/edit/approve/reject draft replies, see urgent-review alerts, and view the cross-branch health digest — satisfying the hackathon's requirement to demonstrate a running application, not just source code.
- **FR-019**: System MUST require a manager to be authenticated before viewing any review data or taking any approve/reject/publish action; unauthenticated visitors MUST NOT be able to perform these actions. Every approve/publish action MUST be attributable to the specific authenticated manager who performed it (feeds FR-014).
- **FR-020**: System MUST NOT generate or offer a draft reply for a review that already has an existing owner reply (posted manually outside this system); such reviews MUST still appear in the inbox, marked as already-answered, but MUST be excluded from the draft-and-approve flow.

### Key Entities *(include if feature involves data)*

- **Branch**: A physical business location connected to a Google Business Profile; has a name, address, connection status, and an assigned manager.
- **Review**: A customer-submitted rating and text tied to a branch; has sentiment, topic tags, severity level, and a status (new / analyzed / drafted / approved / published / rejected).
- **Draft Reply**: An AI-generated candidate response to a review; has content, status (pending / approved / rejected / published), the approving manager, and a timestamp.
- **Branch Health Score**: An aggregated metric per branch summarizing review sentiment and severity trends over a period, used for cross-branch ranking.
- **Manager**: A user responsible for one or more branches who reviews drafts, approves or rejects them, and receives urgent-review alerts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New reviews from any connected branch appear in the manager's unified, sentiment-tagged inbox within 15 minutes of being posted.
- **SC-002**: A manager can go from an unread review to a published reply in under 2 minutes using the draft-and-approve flow.
- **SC-003**: 100% of urgent-severity reviews trigger a manager alert within 5 minutes of detection.
- **SC-004**: Zero replies are ever published without a recorded manager approval (100% compliance with the approval gate).
- **SC-005**: A manager can generate a cross-branch health ranking report in under 30 seconds.
- **SC-006**: At least 80% of AI-drafted replies require no more than minor edits before a manager approves them.
- **SC-007**: Zero review actions (view, approve, reject, publish) are ever performed by an unauthenticated visitor (100% compliance with the authentication gate).

## Assumptions

- Target users (managers) already have an active, verified Google Business Profile listing for each branch they connect.
- Review language support is limited to Indonesian and English for this feature; other languages may still be ingested but sentiment/topic accuracy is not guaranteed.
- The "urgent" severity threshold uses a reasonable default heuristic (e.g. very negative sentiment combined with a critical topic such as safety or health); exact tuning of the threshold is configurable and not defined in this spec.
- One manager role is assigned per branch and is scoped to that branch's reviews; multi-manager approval workflows for a single branch are out of scope.
- Draft replies use a single default brand tone of voice for the business in this MVP; per-branch tone customization is a future enhancement.
- Urgent-review alerts are delivered via in-app/dashboard notification only; email, SMS, or chat-app (e.g. Slack) delivery is out of scope for this feature.
- Comparing a branch's reputation against nearby competitor businesses (location/competitive benchmarking) is explicitly out of scope for this feature and is tracked as a separate future feature.
- Review ingestion covers a recent, configurable time window (e.g. since last sync); importing a branch's complete historical review archive is out of scope.
- The specific web UI framework is not prescribed by this spec (kept technology-agnostic per Content Quality guidelines); it is fixed project-wide as a Technology Constraint in the project constitution (`.specify/memory/constitution.md`) and applied during `/speckit-plan`.
- The specific authentication mechanism satisfying FR-019 is not prescribed by this spec (kept technology-agnostic); it is a platform-level decision recorded in `plan.md`/`research.md`, not a per-user login system built into this feature.
- Branch onboarding (connecting a branch, per FR-001) is an in-app manager action for this MVP, not an out-of-band/ops-only setup step.
