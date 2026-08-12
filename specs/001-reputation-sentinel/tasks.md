---

description: "Task list template for feature implementation"
---

# Tasks: Reputation Sentinel Ops

**Input**: Design documents from `/specs/001-reputation-sentinel/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested as TDD in the spec, but plan.md's Testing strategy and Project Structure already commit to specific contract/unit/integration test files (Principle IV — Production-Readiness). Those are included below, scoped to the story that first needs them.

**Organization**: Tasks are grouped by user story (spec.md P1-P4) to enable independent implementation and testing of each story.

**Revision note (2026-08-11)**: Renumbered after `/speckit-analyze` found gaps (report findings X1, C1, C2, C3, A1, A2). Six tasks added: T019, T022, T028, T033, T039, T052 (marked "NEW" below). All later IDs shifted accordingly — this supersedes the pre-analysis numbering.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths follow `plan.md` → Project Structure (Option 1: single project, `src/`, `tests/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project structure per plan.md (`src/agents/`, `src/integrations/`, `src/models/`, `src/storage/`, `src/ui/`, `src/config/`, `tests/contract/`, `tests/integration/`, `tests/unit/`)
- [X] T002 Initialize Python 3.11+ project with dependencies (Google ADK, `google-genai`, `streamlit`, `google-api-python-client`, `google-auth-oauthlib`, `tenacity`, `google-cloud-firestore`, `google-cloud-secret-manager`, `pytest`) in `pyproject.toml`
- [X] T003 [P] Configure linting/formatting (ruff/black config) at repo root
- [X] T004 [P] Create `src/config/settings.py` loading GCP project/region, Firestore, Secret Manager, Cloud Scheduler, and Gemini model config from environment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure and shared agents that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Create Branch model in `src/models/branch.py` (data-model.md)
- [X] T006 [P] Create Review model (with status state machine fields, including `existing_owner_reply`) in `src/models/review.py` (data-model.md)
- [X] T007 [P] Create Draft Reply model (including `edit_distance` field) in `src/models/draft_reply.py` (data-model.md)
- [X] T008 [P] Create Branch Health Score model in `src/models/branch_health.py` (data-model.md)
- [X] T009 [P] Create Manager model (including `google_identity_email`) in `src/models/manager.py` (data-model.md)
- [X] T010 Implement Firestore repository layer (CRUD for Branch/Review/DraftReply/BranchHealthScore/Manager) in `src/storage/firestore_repo.py` (depends on T005-T009)
- [X] T011 [P] Implement Gemini client adapter with `tenacity` retry/backoff in `src/integrations/gemini_client.py` (research.md — Language Model, External API Resilience)
- [X] T012 [P] Implement Google Business Profile API client adapter — auth + review read scaffold — with `tenacity` retry/backoff in `src/integrations/gbp_client.py` (contracts/gbp-api-usage.md)
- [X] T013 Implement seed/sample review dataset fallback loader, toggled by config, in `src/integrations/seed_data.py` (research.md — External API Resilience, Principle IV)
- [X] T014 Implement Secret Manager-backed OAuth credential storage/retrieval for `Branch.oauth_credential_ref` in `src/integrations/gbp_client.py` (Security & Data Handling — never plaintext)
- [X] T015 Configure error handling/logging infrastructure with review-content log redaction in `src/config/logging.py` (Security & Data Handling)
- [X] T016 Scaffold ADK Orchestrator (agent registration, no business logic yet) in `src/agents/orchestrator.py` (Principle II)
- [X] T017 [P] Implement Triage Agent (severity scoring: routine/urgent, FR-006/FR-007) in `src/agents/triage_agent.py` — shared computation needed before both US2 (draft context) and US3 (escalation) can build on it
- [X] T018 [P] Unit test for Triage Agent severity scoring in `tests/unit/test_triage_agent.py`
- [X] T019 **(NEW)** [P] Implement authenticated-identity resolution — read the IAP-injected identity header and map it to a `Manager` record via `google_identity_email` — in `src/ui/app.py` (research.md — Manager Authentication / Access Control; FR-019; closes `/speckit-analyze` finding C3 in part)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Unified Multi-Branch Review Inbox (Priority: P1) 🎯 MVP

**Goal**: Manager sees all reviews from every connected branch in one place, tagged with sentiment and topic — no draft/publish involved yet.

**Independent Test**: Connect 2-3 demo branches, sync reviews (manually and via the scheduled trigger), verify a single cross-branch list appears with sentiment + topic tags, filterable by branch/sentiment.

### Tests for User Story 1

- [X] T020 [P] [US1] Contract test for GBP client review-read path in `tests/contract/test_gbp_client_contract.py`
- [X] T021 [P] [US1] Unit test for Analysis Agent sentiment/topic tagging (ID + EN) in `tests/unit/test_analysis_agent.py`

### Implementation for User Story 1

- [X] T022 **(NEW)** [US1] Implement the branch-connect flow — OAuth consent initiation, create the `Branch` record — in `src/integrations/gbp_oauth.py` and wire it into `src/ui/app.py` (FR-001; closes `/speckit-analyze` finding C1)
- [X] T023 [US1] Implement Ingestion Agent (pull reviews per branch since `last_ingested_at`, fall back to seed data on failure) in `src/agents/ingestion_agent.py` (depends on T022)
- [X] T024 [US1] Implement Analysis Agent (Gemini sentiment classification + topic tagging) in `src/agents/analysis_agent.py`
- [X] T025 [US1] Wire Orchestrator ingestion → analysis → triage pipeline per branch cycle in `src/agents/orchestrator.py` (depends on T016, T017, T023, T024)
- [X] T026 [US1] Implement unified inbox view (cross-branch list, sentiment/topic tags, filter by branch/sentiment) in `src/ui/app.py` (depends on T019 — only shown to an authenticated manager)
- [X] T027 [US1] Add manual "sync now" ingestion trigger to the UI in `src/ui/app.py`
- [X] T028 **(NEW)** [US1] Add scheduled ingestion trigger (Cloud Scheduler → Cloud Run endpoint, every 15 minutes) so SC-001's freshness target holds without a manual click (research.md — Ingestion Scheduling; closes `/speckit-analyze` finding C2)
- [X] T029 [US1] Add empty-state and GBP-error handling (zero new reviews vs. sync error, Edge Cases) in `src/agents/ingestion_agent.py`

**Checkpoint**: User Story 1 fully functional and independently testable/demoable — this is the deployable MVP slice.

---

## Phase 4: User Story 2 - AI-Drafted Reply with Manager Approval (Priority: P2)

**Goal**: Manager gets a personalized draft reply per review and must approve (or edit-then-approve, or reject) before anything publishes.

**Independent Test**: Open an inbox review, verify a draft exists, approve it and confirm it publishes with status feedback, attributed to your authenticated identity; reject a different draft and confirm nothing publishes and a new draft is generated; confirm an already-answered review never gets a draft at all.

### Tests for User Story 2

- [X] T030 [P] [US2] Unit test for Draft Agent personalized reply generation in `tests/unit/test_draft_agent.py`
- [X] T031 [US2] Contract test for GBP client reply-write + publication-state check, extending `tests/contract/test_gbp_client_contract.py` from T020 (same file — not parallel with T020)

### Implementation for User Story 2

- [X] T032 [US2] Implement Draft Agent (Gemini-generated personalized reply per brand voice) in `src/agents/draft_agent.py`
- [X] T033 **(NEW)** [US2] Skip Draft Agent invocation and mark the review as already-answered when `existing_owner_reply = true`, in `src/agents/orchestrator.py` (FR-020; contracts/agent-interfaces.md Draft Agent Precondition; closes `/speckit-analyze` finding A1)
- [X] T034 [US2] Implement Orchestrator approve/reject/publish step — publish only after a recorded manager approval, reject regenerates a new draft — in `src/agents/orchestrator.py` (Principle I; depends on T025, T032; `approved_by` MUST come from the authenticated identity resolved in T019, never free text)
- [X] T035 [US2] Implement GBP client reply-write + publication-state polling in `src/integrations/gbp_client.py` (contracts/gbp-api-usage.md; depends on T012)
- [X] T036 [US2] Implement review detail view — draft display, edit, approve, reject actions — in `src/ui/app.py`
- [X] T037 [US2] Implement publish-status feedback (published / pending / rejected) in `src/ui/app.py`
- [X] T038 [US2] Record approver identity (from T019's authenticated session, not manual entry) + timestamp on Draft Reply (FR-014 accountability) in `src/storage/firestore_repo.py`
- [X] T039 **(NEW)** [US2] Compute and store `edit_distance` between generated draft content and manager-approved final text at approval time, in `src/storage/firestore_repo.py` (SC-006 instrumentation; closes `/speckit-analyze` finding A2)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Urgent Review Escalation (Priority: P3)

**Goal**: Reviews with severe/urgent content are visually separated and trigger a manager alert, independent of draft/approval state.

**Independent Test**: Ingest a review with severe content, verify it's flagged "urgent", shown separately, and alerts the branch manager; ingest a routine negative review and verify no alert fires.

### Implementation for User Story 3

- [X] T040 [US3] Finalize Triage Agent wiring into the per-review Orchestrator pipeline so severity is set immediately after Analysis (depends on T017, T025)
- [X] T041 [US3] Implement urgent-review visual separation in the inbox UI in `src/ui/app.py`
- [X] T042 [US3] Implement in-app manager alert for newly-flagged urgent reviews in `src/ui/app.py` (Manager.alert_channel = in_app only, per Assumptions)
- [X] T043 [US3] [P] Integration test: urgent reviews alert + separate from routine, routine reviews flow to normal draft queue without alert, in `tests/integration/test_orchestrator_pipeline.py`

**Checkpoint**: User Stories 1, 2, AND 3 all independently functional.

---

## Phase 6: User Story 4 - Cross-Branch Review Health Digest (Priority: P4)

**Goal**: On-demand report ranking connected branches by review health score with top recurring complaint topics per branch.

**Independent Test**: With reviews across 2+ branches, request the digest and verify a ranked list with per-branch top topics returns in under 30 seconds.

### Implementation for User Story 4

- [X] T044 [P] [US4] Implement Reporting Agent (compute Branch Health Score + top topics per branch) in `src/agents/reporting_agent.py`
- [X] T045 [US4] Implement digest view (branch ranking + top topics, on-demand) in `src/ui/app.py`
- [X] T046 [US4] Implement Branch Health Score persistence/retrieval in `src/storage/firestore_repo.py`

**Checkpoint**: All 4 user stories independently functional — full MVP scope from spec.md complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T047 [P] Audit retry/backoff coverage across all external integrations in `src/integrations/` (Principle IV)
- [X] T048 Audit codebase for any path that could publish a reply without a recorded manager approval (Principle I — must find none, per quickstart.md Approval-gate check)
- [X] T049 Run full `quickstart.md` validation across all 4 user stories plus the resilience, approval-gate, and authentication checks
- [X] T050 [P] Audit review-content logging for redaction compliance in `src/config/logging.py` (Security & Data Handling)
- [X] T051 Prepare Cloud Run deployment (Dockerfile + deploy config) for the single Streamlit+ADK container (Technology Constraints, FR-018)
- [X] T052 **(NEW, revised 2026-08-12)** Restrict access to authorized managers only (FR-019/SC-007; depends on T051; closes the remainder of `/speckit-analyze` finding C3). Deployed as **Option B** instead of full IAP — `--no-allow-unauthenticated` on Cloud Run + per-manager `roles/run.invoker` IAM bindings + `src/integrations/auth.py` reading the Cloud Run-verified bearer token. See research.md § Deployment Update for the full rationale and the tradeoff vs. full IAP (tracked as optional future work, not required).
- [X] T053 [P] Write README/demo script for Final Demo Day

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories. Includes Triage Agent (T017-T018) and authenticated-identity resolution (T019) since both are shared prerequisites used across later stories.
- **User Stories (Phase 3-6)**: All depend on Foundational completion.
  - US1 (P1): No dependency on other stories — first deployable slice. Now includes branch-connect (T022) and scheduled ingestion (T028), both required for its own Independent Test/Success Criteria to actually hold.
  - US2 (P2): Builds on US1's Ingestion/Analysis pipeline, Orchestrator wiring (T025), and Foundational auth (T019); independently testable via its own review fixtures.
  - US3 (P3): Builds on Foundational Triage output (T017) and US1's Orchestrator wiring (T025); independently testable.
  - US4 (P4): Builds on persisted Review data from US1; independently testable, no dependency on US2/US3.
- **Polish (Phase 7)**: Depends on all four user stories being complete. Includes enabling IAP (T052) — do this last so earlier phases can be developed/tested without fighting the proxy locally.

### Parallel Opportunities

- All Setup [P] tasks (T003, T004) in parallel.
- Foundational model tasks T005-T009 in parallel; T011, T012 in parallel; T017-T018 in parallel with each other and with T019 (not with T016, which they build on).
- Once Foundational completes, US1, US2, US3, US4 implementation *tasks* still have real ordering (US2/US3/US4 build on US1's pipeline) — but if staffed, one person can start US1 UI (T026) while another starts US2's Draft Agent (T032) once T025 lands, etc.
- Within US1: T020, T021 in parallel (different files).
- Within US4: T044 in parallel with US1-US3 UI work (different file, only needs persisted Review data).

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together:
Task: "Contract test for GBP client review-read path in tests/contract/test_gbp_client_contract.py"
Task: "Unit test for Analysis Agent sentiment/topic tagging in tests/unit/test_analysis_agent.py"
```

## Parallel Example: Foundational Models

```bash
Task: "Create Branch model in src/models/branch.py"
Task: "Create Review model in src/models/review.py"
Task: "Create Draft Reply model in src/models/draft_reply.py"
Task: "Create Branch Health Score model in src/models/branch_health.py"
Task: "Create Manager model in src/models/manager.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (now includes real branch-connect + scheduled sync)
4. **STOP and VALIDATE**: run `quickstart.md`'s User Story 1 section independently
5. Deploy/demo if ready — this alone already beats the industry baseline (54% response rate) by giving managers unified visibility they don't have today

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add US1 → validate → deploy/demo (MVP)
3. Add US2 → validate → deploy/demo (headline "agentic" capability — draft + approve + publish)
4. Add US3 → validate → deploy/demo (safety/urgency differentiator)
5. Add US4 → validate → deploy/demo (reporting polish)
6. Phase 7 Polish (including enabling IAP as the last step) → Final Demo Day readiness

### Timebox Note (Principle V)

Given the hackathon's same-day submission deadline, if time runs out mid-sequence, stop after
the last **completed and validated** checkpoint (e.g., US1+US2) and demo that — a smaller
fully-working slice beats a larger half-working one, per the constitution. If T052 (IAP) is
the only Polish item left undone, do not skip it before any public demo URL is shared — an
unauthenticated public URL directly contradicts Principle I's premise (finding C3).

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps each task to its user story for traceability back to spec.md.
- T031 deliberately omits [P] — it extends the same contract test file T020 created.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently via `quickstart.md`.
- No task in any story implements a code path that bypasses the Principle I approval gate — T048 exists specifically to audit that this stays true.
- Six tasks (T019, T022, T028, T033, T039, T052) were added by the `/speckit-analyze` remediation pass on 2026-08-11; see spec.md FR-019/FR-020/SC-007 and plan.md Complexity Tracking for the requirements/decisions behind them.

## Implementation Status (2026-08-11, `/speckit-implement`)

52/53 tasks complete — all code, tests (23/23 passing, `pytest tests/`), lint (`ruff check`
clean), Dockerfile, and deploy script written. T052 (access control) left `[ ]` pending a
live Cloud Run service, which didn't exist in the dev environment yet.

## Deployment Log (2026-08-12) — 53/53 complete

Deployed to the team's real GCP sandbox (`ebco-aihack-acqmal`, account
`acqmal@ebconnect.com`):
- Firestore Native database created (`asia-southeast2`).
- Cloud Run service `reputation-sentinel-ops` live: `https://reputation-sentinel-ops-743183091025.asia-southeast2.run.app` (`--no-allow-unauthenticated`).
- Cloud Function `reputation-sentinel-scheduled-ingestion` (gen2) + Cloud Scheduler job
  `reputation-sentinel-ingestion` (`*/15 * * * *`) — verified via a live trigger returning
  `{"branches_processed": 0, "new_reviews": 0, "newly_urgent": [], "errors": []}` with zero
  Firestore/import errors.
- T052 closed via **Option B** (see research.md § Deployment Update), not full IAP.

**Bugs found and fixed during deploy** (not caught by local `pytest`, since they were
deployment-environment issues, not logic bugs):
1. `ModuleNotFoundError: No module named 'src'` on Streamlit startup — `streamlit run
   src/ui/app.py` puts `src/ui/` on `sys.path[0]`, not `/app`. Fixed with `ENV
   PYTHONPATH=/app` in `Dockerfile`. Verified fixed: zero errors on revision `-00002-ctz`
   vs. the traceback on `-00001-x7r`.
2. `.gcloudignore` originally excluded `Dockerfile`/`.dockerignore` (copied from
   `.dockerignore`'s own ignore list) — broke `gcloud builds submit`, which needs the
   Dockerfile present in the uploaded source. Fixed by removing those two lines.
3. Cloud Functions gen2 requires a root-level `main.py` re-exporting the entry point —
   added, re-exporting `src/jobs/scheduled_ingestion.main`.

All fixes are in the source tree (`Dockerfile`, `.gcloudignore`, `main.py`,
`src/integrations/auth.py`), not just applied live to the running service, so the next
`deploy/deploy.sh` run reproduces this working state from scratch.
