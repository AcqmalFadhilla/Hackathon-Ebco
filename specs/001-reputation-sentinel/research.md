# Phase 0 Research: Reputation Sentinel Ops

No `[NEEDS CLARIFICATION]` markers remained in the Technical Context — all decisions below
were made from constitution constraints, spec requirements, and the hackathon sandbox
environment (GCP project + Gen AI model access). Recorded here per Phase 0 for traceability.

## Agent Orchestration Framework

- **Decision**: Google Agent Development Kit (ADK) for the Ingestion/Analysis/Triage/Draft/
  Reporting agents and the Orchestrator.
- **Rationale**: Directly satisfies Principle II (Single-Responsibility Agent Architecture —
  ADK's agent/tool abstraction maps 1:1 to each agent's single responsibility); GCP-native,
  so it runs inside the provided hackathon sandbox without extra credentials; matches the
  pattern already proven by vault reference projects (Energy Agent AI, TradeSage AI).
- **Alternatives considered**: A hand-rolled orchestration loop (rejected — more code to
  write and test under a same-day deadline, no functional benefit over ADK); LangGraph
  (rejected — not GCP-native, adds a dependency with no corresponding requirement, would
  violate Principle VI).

## Language Model

- **Decision**: Gemini via Vertex AI (`google-genai` SDK) for sentiment classification, topic
  tagging, severity scoring, and draft-reply generation (FR-003, FR-004, FR-006, FR-009).
- **Rationale**: Provided directly by the hackathon's GCP sandbox Gen AI access; one model
  covers all four NLP sub-tasks via different prompts, avoiding extra model-hosting
  complexity.
- **Alternatives considered**: A separate classical ML sentiment classifier for FR-003
  (rejected — adds a training/data-prep step with no time budget for it, and Gemini already
  covers Indonesian + English per FR-005).

## UI Framework

- **Decision**: Streamlit (fixed by constitution Technology Constraints, tracing to FR-018).
- **Rationale**: Python-native (no second language next to the ADK/Gemini backend), fast to
  build a working manager UI (inbox, approve/reject actions, digest view) within the
  timebox, and deploys straightforwardly to Cloud Run as a single container.
- **Alternatives considered**: Not evaluated — this is a fixed project-wide constraint, not a
  per-feature choice (constitution Technology Constraints section).

## Storage

- **Decision**: Firestore for Branch, Review, Draft Reply, and Branch Health Score records.
- **Rationale**: Document shape matches the entities directly (no schema migration overhead
  under time pressure); native read-after-write consistency fits the approve→publish flow;
  GCP-native, fits inside the sandbox project.
- **Alternatives considered**: BigQuery (rejected for the operational/transactional path —
  it's an analytical warehouse, not built for single-document read/write per approval
  action; could be added later purely for the digest if scale grew, but 2-3 demo branches
  don't need it — would violate Principle V as premature optimization). Cloud SQL (rejected —
  relational schema adds migration overhead with no relational-integrity requirement here).

## Deployment Target

- **Decision**: Cloud Run, single container (Streamlit UI + ADK backend in one process).
- **Rationale**: Satisfies the EBCO submission requirement to show "aplikasi yang berjalan";
  GCP-native within the sandbox; a single container is the simplest deployable unit that
  still meets FR-018, per Principle V.
- **Alternatives considered**: Split frontend (Cloud Run) + backend (Cloud Functions)
  services (rejected — adds a network boundary and two deploy pipelines for no requirement
  that needs it, under a same-day deadline).

## Ingestion Scheduling

- **Decision**: Cloud Scheduler triggers the ingestion cycle every 15 minutes (in addition to
  the manual "sync now" button in the UI).
- **Rationale**: Added after `/speckit-analyze` found SC-001's 15-minute freshness promise had
  no automatic trigger — a manual-only button can't guarantee freshness if no one clicks it.
  GCP-native, fits the sandbox, no extra infrastructure to stand up.
- **Alternatives considered**: `APScheduler` running inside the app process (rejected — ties
  ingestion timing to the Streamlit process staying up/warm, which Cloud Run doesn't guarantee
  for a low-traffic app; Cloud Scheduler hitting an HTTP endpoint is more reliable on Cloud Run).

## Manager Authentication / Access Control

- **Decision (superseded — see Deployment Update below)**: Google Cloud Identity-Aware Proxy
  (IAP) in front of the Cloud Run service, restricted to an explicit allow-list of manager
  Google identities; the app reads the IAP-injected identity header to resolve the current
  `Manager` record (`google_identity_email`).
- **Rationale**: Added after `/speckit-analyze` found no requirement or task authenticated who
  could approve/publish in the UI — a gap directly undermining Principle I's brand-safety
  premise. IAP requires no in-app auth code (no login screens, no password/session handling to
  build same-day), is GCP-native, and satisfies FR-019/SC-007.
- **Alternatives considered**: `streamlit-authenticator` with app-managed passwords (rejected —
  more code to write, test, and secure under time pressure, for a hackathon audience that's
  already inside the team's GCP org); no auth at all (rejected outright — see finding C3 in the
  `/speckit-analyze` report, directly conflicts with Principle I's intent).

### Deployment Update (2026-08-12) — Option B adopted as the interim mechanism

At actual deploy time, full IAP was deferred: it requires an External HTTPS Load Balancer +
serverless NEG + managed SSL certificate in front of Cloud Run, which needs a domain and
~15-60 minutes of cert-provisioning lead time — not worth spending under the hackathon
deadline when a materially equivalent guarantee is one flag away.

- **What's actually deployed**: Cloud Run's own built-in IAM authentication
  (`--no-allow-unauthenticated`), which rejects every unauthenticated request at Google's
  front door before it ever reaches the container — a stronger perimeter guarantee than
  "the app checks a header," since a misconfigured app can't accidentally bypass it.
  `src/integrations/auth.py` was extended to resolve the caller's identity from the
  Cloud Run-validated `Authorization: Bearer <ID token>` header (decoding the JWT's `email`
  claim — Cloud Run's IAM check is the actual verification step; this is claim extraction,
  not re-verification) whenever the IAP header is absent. Managers reach the service via
  `gcloud run services proxy reputation-sentinel-ops --region=asia-southeast2`, which
  attaches their own ID token automatically — no code change needed on their end.
- **This still satisfies FR-019/SC-007 in full**: zero unauthenticated access is possible;
  every approve/publish action is attributable to a real, IAM-verified Google identity.
- **Gap vs. full IAP**: no browser-native SSO redirect (managers need the `gcloud` proxy
  command, not just a URL) and no centralized allow-list UI (managed via `run.invoker` IAM
  bindings instead). Tracked as a follow-up, not a blocker — see tasks.md T052.

### Correction (2026-08-12, same day) — Cloud Run strips `Authorization` before forwarding

The bearer-token extraction path above (`auth.extract_email_from_cloud_run_bearer`) never
actually fires in production: live testing showed Cloud Run's built-in IAM auth validates
the `Authorization` header and then **removes it** before the request reaches the
container — confirmed empirically (debug-logged header keys on a real request showed no
`Authorization` key at all). This is documented Cloud Run behavior for its own IAM auth
(distinct from IAP, which injects a *different*, verified identity header instead of
stripping the original one) — I had assumed the header would pass through; it doesn't.

**Adopted instead — manager selector gate ("Option C")**: `src/ui/app.py` now falls back to
a `st.selectbox` of registered managers when header-based resolution finds nothing. This is
reachable only by someone Cloud Run has already confirmed holds `roles/run.invoker` (the
real access boundary — verified: a request with no valid token is rejected before reaching
Python at all), so it's a self-declaration among an already-vetted set, not a broken
cryptographic check. It is a **weaker** attribution guarantee than headers would give (FR-014
still records *a* manager per approval, but not a per-request-proven one) — full IAP remains
the fix that closes this gap completely, still tracked as optional follow-up (T052 note).

## External API Resilience

- **Decision**: Wrap all Google Business Profile API and Gemini calls with `tenacity`
  retry/backoff; maintain a seed/sample review dataset as a fallback data source, toggled by
  configuration, so ingestion (and thus the whole demo) can proceed if the live API is
  slow/unavailable (Principle IV).
- **Rationale**: Directly required by constitution Principle IV; protects the one-shot Final
  Demo Day from an external outage or OAuth provisioning delay.
- **Alternatives considered**: No fallback / happy-path-only (rejected — explicitly
  disallowed by Principle IV for any feature exercised in the demo).
