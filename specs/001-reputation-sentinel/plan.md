# Implementation Plan: Reputation Sentinel Ops

**Branch**: `001-reputation-sentinel` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-reputation-sentinel/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

A multi-agent (Ingestion, Analysis, Triage, Draft, Reporting + Orchestrator) system that pulls
Google Business Profile reviews across a manager's connected branches, tags them with
sentiment/topic/severity, drafts personalized replies, and lets a manager approve before
anything publishes — plus a cross-branch health digest. Technical approach: a single
Python monolith built on Google Agent Development Kit (ADK) for agent orchestration and
Gemini (via Vertex AI) for NLP tasks, fronted by a mandatory Streamlit UI (constitution
Technology Constraints), persisted in Firestore, deployed to Cloud Run inside the team's GCP
hackathon sandbox — chosen to fit the hackathon timebox (Principle V) as one deployable
service instead of a split frontend/backend.

## Technical Context

**Language/Version**: Python 3.11+ (single language across agents, orchestration, and UI —
matches ADK, Vertex AI SDK, and Streamlit, avoiding a second runtime under time pressure)

**Primary Dependencies**: Google Agent Development Kit (ADK) for the 5-agent + orchestrator
pipeline; `google-genai` / Vertex AI SDK for Gemini (sentiment, topic tagging, severity
scoring, draft generation); Streamlit (mandated by constitution Technology Constraints) for
the manager-facing UI; `google-api-python-client` + `google-auth-oauthlib` for the Google
Business Profile API (branch-connect OAuth consent, review read + reply write); `tenacity`
for retry/backoff on external API calls (constitution Principle IV); Cloud Scheduler to
trigger the ingestion cycle automatically (research.md — Ingestion Scheduling, closes the
`/speckit-analyze` C2 finding)

**Storage**: Firestore — chosen over BigQuery/Cloud SQL for this MVP because the workload is
low-volume, document-shaped (reviews, drafts, branch state), and needs fast read-after-write
for the approval flow, not analytical aggregation at scale

**Testing**: pytest for agent unit logic and Orchestrator sequencing; contract tests for the
Google Business Profile API adapter (request/response shape, retry behavior) using recorded
fixtures; manual quickstart walkthrough (`quickstart.md`) for end-to-end UI validation given
the hackathon timebox

**Target Platform**: Google Cloud Run, inside the team's dedicated GCP sandbox project
(per EBCO hackathon facilities) with access to the provided Gen AI model

**Project Type**: single deployable web application (Streamlit UI process + ADK agent
backend in one Python codebase/container) — not split frontend/backend, per Principle V

**Performance Goals**: ingestion cycle covers all connected demo branches (2-3) within the
15-minute freshness target (SC-001); digest generation completes in under 30 seconds (SC-005)
for the demo's review volume

**Constraints**: publish action MUST be blocked on recorded manager approval with no code
path around it (Principle I); every Google Business Profile / Gemini call MUST have
retry/backoff and a fallback (seed/sample data) path (Principle IV); UI MUST be Streamlit
(Technology Constraints); UI access MUST be restricted to authenticated, authorized managers
via Identity-Aware Proxy — no unauthenticated action may succeed (FR-019, research.md —
Manager Authentication / Access Control, closes the `/speckit-analyze` C3 finding)

**Scale/Scope**: 2-3 demo branches, one manager per branch, recent-window review ingestion
only (no historical backfill) — matches spec Assumptions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Section | Status | How this plan satisfies it |
|---|---|---|
| I. Human-in-the-Loop Non-Negotiable | PASS | Draft Agent output is never sent to the GBP reply endpoint directly; the Orchestrator only calls the publish step after an explicit `approve` action recorded against a manager in Firestore. No agent holds standing publish permission. |
| II. Single-Responsibility Agent Architecture | PASS (documented trade-off) | Ingestion, Analysis, Triage, Draft, Reporting are separate ADK agents/modules, each independently testable — but all run in one Cloud Run container, so they are not independently *deployable* at runtime as the principle's text literally requires. Trade-off justified and recorded in Complexity Tracking below, per `/speckit-analyze` finding X1. |
| III. Spec-Driven Development | PASS | This plan traces every Technical Context decision to a spec.md requirement (FR-001..FR-018); `/speckit-tasks` will trace tasks back to this plan. |
| IV. Production-Readiness by Default | PASS | All external calls (GBP API, Gemini) wrapped with `tenacity` retry/backoff; a seed-data fallback path lets ingestion/demo continue if the live API is slow/down. |
| V. Timebox-Aware Simplicity (YAGNI) | PASS | Single Python monolith, single datastore (Firestore), no Geo Benchmark / Slack-email / historical-backfill code paths — matches spec's explicit out-of-scope list. |
| VI. Purposeful Technology Diversity | PASS | Every technology maps to a requirement: ADK→multi-agent orchestration, Gemini→NLP (FR-003/004/006/009), Streamlit→FR-018, Firestore→state persistence, Cloud Run→"aplikasi yang berjalan" submission requirement. Nothing added purely for diversity score. |
| Security & Data Handling | PASS | OAuth tokens stored in Secret Manager, not in code/config files; review content logging kept at debug level only, no persistent verbose logs of reviewer PII; UI access gated by Identity-Aware Proxy (T019, T052) so no unauthenticated visitor reaches review data or actions, per the constitution's v1.2.0 amendment. |
| Technology Constraints (Streamlit) | PASS | UI is Streamlit as mandated; no alternative UI framework introduced. |

One documented trade-off (Principle II vs. single-container deployment) — see Complexity
Tracking below. No other violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-reputation-sentinel/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── agent-interfaces.md
│   └── gbp-api-usage.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

**Structure Decision**: Option 1 (single project), because the UI (Streamlit) and the agent
backend (ADK) run in one Python process/container per Principle V — there is no separate
"frontend" service calling a "backend" API across a network boundary in this MVP.

```text
src/
├── agents/
│   ├── ingestion_agent.py
│   ├── analysis_agent.py
│   ├── triage_agent.py
│   ├── draft_agent.py
│   ├── reporting_agent.py
│   └── orchestrator.py
├── integrations/
│   ├── gbp_client.py        # Google Business Profile API adapter (read + reply)
│   ├── gbp_oauth.py         # Branch-connect OAuth consent flow (FR-001)
│   ├── gemini_client.py     # Gemini/Vertex AI adapter (sentiment, topic, severity, draft)
│   └── seed_data.py         # Seed/sample review dataset fallback (Principle IV)
├── models/
│   ├── branch.py
│   ├── review.py
│   ├── draft_reply.py
│   ├── branch_health.py
│   └── manager.py
├── storage/
│   └── firestore_repo.py
├── ui/
│   └── app.py                # Streamlit entrypoint
└── config/
    ├── settings.py
    └── logging.py             # Error handling + review-content redaction (Security & Data Handling)

tests/
├── contract/
│   └── test_gbp_client_contract.py
├── integration/
│   └── test_orchestrator_pipeline.py
└── unit/
    ├── test_analysis_agent.py
    ├── test_triage_agent.py
    └── test_draft_agent.py
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle II says each agent is "independently deployable/replaceable"; this MVP runs all 5 agents + Orchestrator in one Cloud Run container instead. | Principle V (Timebox-Aware Simplicity) — a same-day hackathon deadline doesn't allow time to build and wire 6 separate deploy pipelines, inter-service auth, and network contracts between agents. | Splitting each agent into its own Cloud Run/Cloud Function service was rejected: it adds a network boundary and deployment pipeline per agent with no functional requirement driving it, and would still need to be re-merged conceptually for the Orchestrator to sequence calls with the reliability Principle IV requires. Agents remain independently *testable* (unit-level, per `contracts/agent-interfaces.md`) even though not independently *deployable* at runtime for this MVP; splitting deployment is a reasonable post-hackathon follow-up, not a same-day requirement. |
