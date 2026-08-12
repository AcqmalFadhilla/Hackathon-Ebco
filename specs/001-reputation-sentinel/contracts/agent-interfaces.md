# Contract: Orchestrator ↔ Agent Interfaces

Internal contracts between the Orchestrator and each of the 5 agents (Principle II —
each agent independently testable against its own input/output shape).

## Ingestion Agent

- **Input**: `{ branch_id }`
- **Output**: `{ reviews: Review[] }` — raw reviews pulled since `last_ingested_at`, `status = "new"`
- **Failure mode**: on GBP API error, returns `{ reviews: [], error: {...} }` after retry/backoff (Principle IV) — Orchestrator MUST NOT treat this as "zero new reviews" for reporting purposes; it MUST be surfaced as a sync error, distinct from a genuinely empty result.

## Analysis Agent

- **Input**: `{ review: Review }` (status `new`)
- **Output**: `{ review_id, sentiment, topics: string[] }`
- **Contract**: MUST run for both `id` and `en` language reviews (FR-005); MUST still return a best-effort result (not an error) for `other` languages, per spec Assumptions.

## Triage Agent

- **Input**: `{ review_id, sentiment, topics }`
- **Output**: `{ review_id, severity: "routine" | "urgent" }`
- **Contract**: Runs after Analysis Agent, before Draft Agent. `urgent` output MUST cause the Orchestrator to invoke the manager alert path (FR-008) independently of whether a draft has been generated yet (User Story 3, Acceptance Scenario 2).

## Draft Agent

- **Input**: `{ review_id, sentiment, topics, severity }`
- **Output**: `{ review_id, draft_content }`
- **Contract**: Output MUST NOT be sent to the GBP reply endpoint by this agent or the Orchestrator directly — it is only ever written as a `Draft Reply` with `status = "pending"` (Principle I). Re-invoked (new draft) whenever a manager rejects the current draft (Review state machine).
- **Precondition (FR-020)**: The Orchestrator MUST NOT invoke this agent for a review where `existing_owner_reply = true`; that review is marked already-answered and skips the draft-and-approve flow entirely.

## Reporting Agent

- **Input**: `{ branch_ids: string[], period }`
- **Output**: `{ rankings: BranchHealthScore[] }`
- **Contract**: Read-only over already-persisted Review/Branch data — MUST NOT trigger ingestion or analysis as a side effect (single responsibility, Principle II).

## Orchestrator → Publish step (not an agent — explicit gate)

- **Input**: `{ draft_id, approved_by, approved_content }` — only invoked after a UI-recorded manager approval action. `approved_by` MUST be the authenticated manager identity (FR-019, `Manager.google_identity_email`), never a client-supplied/free-text value.
- **Output**: `{ review_id, publication_state }` — MUST poll/check the reply's publication state (FR-013) before reporting `published` back to the UI; `pending` or `rejected` states MUST be surfaced to the manager, not silently retried as if approved again.
