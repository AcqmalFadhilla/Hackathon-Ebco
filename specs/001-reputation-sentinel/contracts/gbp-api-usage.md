# Contract: Google Business Profile API Usage

Documents which external surface this feature depends on and how it's used — not a
re-specification of Google's API, just the boundary this project relies on.

## Read path (Ingestion Agent)

- Per connected `Branch.gbp_location_id`, list reviews posted/updated since
  `Branch.last_ingested_at` (or a bounded initial window on first connect — FR-017, no full
  historical backfill).
- Each review record MUST supply: rating, text, timestamp, reviewer display name, and
  whether an owner reply already exists (`existing_owner_reply` — Edge Cases).
- On rate-limit or transient error: retry with backoff (`tenacity`, Principle IV); on
  exhausted retries, fall back to the seed/sample dataset for that branch's ingestion cycle
  and mark `Branch.connection_status = "error"` rather than silently returning nothing.

## Write path (Publish step, post-approval only)

- Submits the manager-approved reply content against the specific `review_id`.
- After submission, MUST check the reply's publication/moderation state (pending / approved
  / rejected) before the system reports the review as `published` (FR-013). A `pending` or
  `rejected` state MUST be shown to the manager, not treated as a silent success.
- This write path is reachable ONLY from the Orchestrator's post-approval publish step
  (`contracts/agent-interfaces.md`) — no agent calls it directly (Principle I).

## Auth

- OAuth2 per branch; refresh/access tokens referenced via `Branch.oauth_credential_ref`,
  stored in Secret Manager, never in application config or logs (Security & Data Handling).

## Out of scope for this contract

- Posting business updates/posts, managing business hours, photos, or any Business Profile
  surface other than reading reviews and writing replies to them.
- Competitor location lookups (Places API) — tracked separately as the Geo Benchmark Layer
  roadmap item, explicitly out of scope for this feature (spec Assumptions).
