"""Environment-driven configuration. No secrets live here — only references/toggles."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    gcp_project: str
    gcp_region: str
    gemini_model: str
    firestore_database: str
    ingestion_window_days: int
    ingestion_interval_minutes: int
    urgent_severity_keywords: tuple[str, ...]
    use_seed_data: bool
    seed_data_path: str
    log_level: str
    max_review_edit_distance_sample: int
    simulate_publish_for_demo: bool


def load_settings() -> Settings:
    return Settings(
        gcp_project=os.environ.get("GCP_PROJECT", ""),
        gcp_region=os.environ.get("GCP_REGION", "asia-southeast2"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        firestore_database=os.environ.get("FIRESTORE_DATABASE", "(default)"),
        ingestion_window_days=int(os.environ.get("INGESTION_WINDOW_DAYS", "90")),
        ingestion_interval_minutes=int(os.environ.get("INGESTION_INTERVAL_MINUTES", "15")),
        urgent_severity_keywords=tuple(
            k.strip()
            for k in os.environ.get(
                "URGENT_SEVERITY_KEYWORDS",
                "keracunan,kebakaran,pelecehan,cedera,bahaya,discrimination,unsafe,injury,fire,harassment",
            ).split(",")
            if k.strip()
        ),
        use_seed_data=_bool_env("USE_SEED_DATA", default=True),
        seed_data_path=os.environ.get("SEED_DATA_PATH", "data/seed_reviews.json"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        max_review_edit_distance_sample=int(os.environ.get("EDIT_DISTANCE_SAMPLE_CHARS", "2000")),
        simulate_publish_for_demo=_bool_env("SIMULATE_PUBLISH_FOR_DEMO", default=False),
    )


SETTINGS = load_settings()
