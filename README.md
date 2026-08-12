# Reputation Sentinel Ops

Multi-agent system that monitors Google Business Profile reviews across a business's
connected branches, tags them with sentiment/topic/severity, drafts personalized replies,
and requires explicit manager approval before anything publishes.

Built for EBCO AI Hackathon 2026 (Kategori B — AI Agent, tema Google Business Profile
Insights). Full design docs: `specs/001-reputation-sentinel/` (spec, plan, data model,
contracts, tasks, architecture diagrams) and `.specify/memory/constitution.md`.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

export USE_SEED_DATA=true        # no live GCP/GBP credentials needed for a local demo
export LOCAL_DEV_MODE=true        # bypasses IAP locally — NEVER set this once deployed
export DEV_MANAGER_EMAIL=you@example.com

streamlit run src/ui/app.py
```

On first run, go to **Connect Branch → Demo / Seed Data**, connect `branch-demo-1` and
`branch-demo-2` (seeded from `data/seed_reviews.json`), then **Sync now** on the Inbox page.

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
```

## Demo script (Final Demo Day)

1. **Inbox (US1)** — Connect Branch → seed-data connect both demo branches → Inbox → Sync
   now. Point out: reviews from both branches in one list, sentiment + topic tags auto-set,
   filter by branch/sentiment.
2. **Urgent escalation (US3)** — Point out the 🚨 banner and the review with the safety
   keyword (`seed-b1-r3`, "benda asing berbahaya") flagged urgent and shown separately from
   routine reviews.
3. **Already-answered skip (FR-020)** — Open `seed-b1-r4` (has `existing_owner_reply: true`
   in the seed data) — show it's marked "Already answered" with no draft/approve action,
   proving the system never double-replies.
4. **Draft → approve → publish (US2, the headline capability)** — Open a routine review,
   show the AI-drafted reply, edit it live, click **Approve & publish**. Narrate: this is
   the human-in-the-loop gate (Principle I) — nothing publishes without this exact click,
   and `tests/integration/test_orchestrator_pipeline.py::test_approve_draft_requires_authenticated_approver_email`
   proves that gate is enforced in code, not just the UI.
5. **Reject → regenerate** — On another review, click **Reject** and show a fresh draft
   appears immediately.
6. **Digest (US4)** — Go to Digest, generate a 30-day report, show branches ranked by
   health score with top complaint topics.
7. **Close on production-readiness** — mention: retry/backoff on every external call
   (`tenacity`), seed-data fallback if the GBP API is down, IAP-gated access (`T052`),
   Cloud Scheduler-driven 15-minute auto-sync (not just the manual button), and the full
   Spec-Driven Development trail in `specs/001-reputation-sentinel/` (spec → plan → tasks →
   `/speckit-analyze` remediation → implementation) for the SDD bonus.

## Architecture

See [`specs/001-reputation-sentinel/architecture.md`](specs/001-reputation-sentinel/architecture.md)
for the full system diagram, data model, review lifecycle state machine, and per-story
sequence diagrams (all in Mermaid).

## Deployment

**Live** on `ebco-aihack-acqmal` (asia-southeast2): Cloud Run service
`reputation-sentinel-ops`, Cloud Scheduler-triggered ingestion function (every 15 min),
Firestore Native database. Deployed via [`deploy/deploy.sh`](deploy/deploy.sh).

Access is restricted to authorized managers only (FR-019/SC-007) — **Option B**: Cloud
Run's own `--no-allow-unauthenticated` IAM auth, not full IAP (see
[`research.md`](specs/001-reputation-sentinel/research.md) § Deployment Update for why).
To open the app:

```bash
gcloud run services add-iam-policy-binding reputation-sentinel-ops \
  --project=ebco-aihack-acqmal --region=asia-southeast2 \
  --member="user:YOUR_EMAIL_HERE" --role="roles/run.invoker"
# then register a Manager doc in Firestore with google_identity_email=YOUR_EMAIL_HERE

gcloud run services proxy reputation-sentinel-ops \
  --project=ebco-aihack-acqmal --region=asia-southeast2
# open http://127.0.0.1:8080
```

## Project status

All 53 tasks in [`specs/001-reputation-sentinel/tasks.md`](specs/001-reputation-sentinel/tasks.md)
complete and deployed. 23/23 automated tests passing (`pytest tests/`), `ruff check` clean.
Deployment log with the 3 environment bugs found and fixed (module path, `.gcloudignore`,
Cloud Functions entrypoint) is in `tasks.md` § Deployment Log.
