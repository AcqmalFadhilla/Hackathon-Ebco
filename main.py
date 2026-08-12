"""Cloud Functions (2nd gen) entrypoint shim for the scheduled-ingestion job.

Cloud Functions' Python buildpack requires a root-level `main.py` exposing the
`--entry-point` function. The real implementation lives in
`src/jobs/scheduled_ingestion.py` (tasks.md T028) — this file only re-exports it so the
same source tree deploys both the Streamlit UI (Dockerfile) and this function.
"""

from src.jobs.scheduled_ingestion import main  # noqa: F401
