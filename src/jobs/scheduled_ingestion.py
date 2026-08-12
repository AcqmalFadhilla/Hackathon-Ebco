"""Scheduled ingestion entrypoint — closes `/speckit-analyze` finding C2 (SC-001).

Deployed as its own minimal HTTP-triggered service (Cloud Functions Framework / Cloud Run),
separate from the Streamlit UI process. Cloud Scheduler calls this every
`SETTINGS.ingestion_interval_minutes` (default 15) — see research.md § Ingestion Scheduling
and tasks.md T028.

This deliberately does NOT go through the Streamlit process: Streamlit's execution model
(script re-run per browser session) is not a reliable target for a server-side cron trigger,
so ingestion is triggered here and reads/writes the same Firestore-backed Repository the UI
uses — the two processes never need to talk to each other directly.

Local run: `python -m src.jobs.scheduled_ingestion`
Deployed: exposed via `functions_framework` as an HTTP entrypoint (`main`), see Dockerfile /
deploy notes in README.md.
"""

from __future__ import annotations

import json

from src.agents.orchestrator import Orchestrator
from src.config.logging import get_logger
from src.storage.firestore_repo import get_repo

logger = get_logger(__name__)


def run_scheduled_ingestion() -> dict:
    repo = get_repo()
    branches = repo.list_branches()
    orchestrator = Orchestrator(repo)
    report = orchestrator.run_ingestion_cycle(branches)

    total_new = sum(len(r.reviews) for r in report.ingestion_results)
    errors = [
        {"branch_id": r.branch_id, "error": r.sync_error}
        for r in report.ingestion_results
        if r.sync_error
    ]
    result = {
        "branches_processed": len(branches),
        "new_reviews": total_new,
        "newly_urgent": report.newly_urgent_review_ids,
        "errors": errors,
    }
    logger.info("Scheduled ingestion cycle complete: %s", json.dumps(result))
    return result


def main(request=None):
    """HTTP entrypoint for Cloud Scheduler (functions_framework.http-compatible signature)."""
    result = run_scheduled_ingestion()
    return json.dumps(result), 200, {"Content-Type": "application/json"}


if __name__ == "__main__":
    print(json.dumps(run_scheduled_ingestion(), indent=2))
