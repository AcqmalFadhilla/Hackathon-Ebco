"""Google Business Profile API adapter — contracts/gbp-api-usage.md.

Read path: list reviews since a branch's last sync (bounded window, FR-017 — no full
historical backfill). Write path: publish an approved reply, then poll publication state
(FR-013) — reachable ONLY from the Orchestrator's post-approval step (Principle I), never
called directly by an agent.

OAuth credentials are never read from plaintext config — always via Secret Manager
(constitution Security & Data Handling), referenced by `Branch.oauth_credential_ref`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.logging import get_logger, redact_review_text
from src.config.settings import SETTINGS
from src.integrations import seed_data

logger = get_logger(__name__)

_RETRY = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=8),
    "reraise": True,
}


class GbpApiError(RuntimeError):
    """Raised after retries are exhausted. Callers MUST fall back (Principle IV), never crash
    the whole ingestion cycle for one branch's failure."""


@dataclass
class RawReview:
    review_id: str
    rating: int
    text: str
    reviewer_name: str
    posted_at: datetime
    language: str
    existing_owner_reply: bool


@dataclass
class PublishResult:
    publication_state: str  # "pending" | "approved" | "rejected"
    simulated: bool = False  # True only under SIMULATE_PUBLISH_FOR_DEMO — see publish_reply


def get_oauth_credential(oauth_credential_ref: str):
    """Fetches OAuth credentials from Secret Manager by reference — never plaintext
    (constitution Security & Data Handling). Returns None if unavailable (caller decides
    fallback)."""
    if not oauth_credential_ref or not SETTINGS.gcp_project:
        return None
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{SETTINGS.gcp_project}/secrets/{oauth_credential_ref}/versions/latest"
        response = client.access_secret_version(name=name)
        return response.payload.data.decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch OAuth credential '%s': %s", oauth_credential_ref, exc)
        return None


class GbpClient:
    def __init__(self) -> None:
        self._service_cache: dict[str, object] = {}

    def _get_service(self, oauth_credential_ref: str):
        """Lazily builds an authorized `googleapiclient` service for a branch's credentials."""
        if oauth_credential_ref in self._service_cache:
            return self._service_cache[oauth_credential_ref]

        token_json = get_oauth_credential(oauth_credential_ref)
        if not token_json:
            return None

        import json

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_info(json.loads(token_json))
        service = build("mybusiness", "v4", credentials=creds)
        self._service_cache[oauth_credential_ref] = service
        return service

    @retry(**_RETRY)
    def _list_reviews_page(self, service, gbp_location_id: str, page_token: str | None):
        request = (
            service.accounts()
            .locations()
            .reviews()
            .list(parent=gbp_location_id, pageToken=page_token)
        )
        return request.execute()

    def list_reviews_since(
        self,
        branch_id: str,
        gbp_location_id: str,
        oauth_credential_ref: str,
        since: datetime | None,
    ) -> list[RawReview]:
        """FR-002/FR-017: reviews since `since` (or a bounded default window on first sync).
        Falls back to seed data on any unrecoverable API error, per Principle IV."""
        window_start = since or (
            datetime.now(UTC) - timedelta(days=SETTINGS.ingestion_window_days)
        )

        service = self._get_service(oauth_credential_ref)
        if service is None:
            logger.info(
                "No live GBP credentials for branch %s — using seed data fallback", branch_id
            )
            return [
                RawReview(**r)
                for r in seed_data.load_seed_reviews(branch_id)
                if r["posted_at"] >= window_start
            ]

        try:
            reviews: list[RawReview] = []
            page_token = None
            while True:
                data = self._list_reviews_page(service, gbp_location_id, page_token)
                for r in data.get("reviews", []):
                    posted_at = datetime.fromisoformat(r["createTime"])
                    if posted_at < window_start:
                        continue
                    reviews.append(
                        RawReview(
                            review_id=r["reviewId"],
                            rating=_star_rating_to_int(r.get("starRating", "FIVE")),
                            text=r.get("comment", ""),
                            reviewer_name=r.get("reviewer", {}).get("displayName", "Anonymous"),
                            posted_at=posted_at,
                            language="other",
                            existing_owner_reply="reviewReply" in r,
                        )
                    )
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            return reviews
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "GBP list_reviews failed for branch %s after retries, falling back to seed "
                "data: %s",
                branch_id,
                exc,
            )
            return [
                RawReview(**r)
                for r in seed_data.load_seed_reviews(branch_id)
                if r["posted_at"] >= window_start
            ]

    @retry(**_RETRY)
    def _publish_reply(self, service, gbp_location_id: str, review_id: str, content: str):
        name = f"{gbp_location_id}/reviews/{review_id}/reply"
        request = service.accounts().locations().reviews().updateReply(
            name=name, body={"comment": content}
        )
        return request.execute()

    @retry(**_RETRY)
    def _get_reply_state(self, service, gbp_location_id: str, review_id: str) -> str:
        name = f"{gbp_location_id}/reviews/{review_id}"
        review = service.accounts().locations().reviews().get(name=name).execute()
        reply = review.get("reviewReply", {})
        return reply.get("replyReplyState", "pending").lower()

    def publish_reply(
        self,
        gbp_location_id: str,
        oauth_credential_ref: str,
        review_id: str,
        content: str,
    ) -> PublishResult:
        """FR-012/FR-013: publish an approved reply, then confirm publication state. ONLY
        callable from the Orchestrator's post-approval step — see orchestrator.py."""
        logger.info(
            "Publishing reply to review %s: %s", review_id, redact_review_text(content)
        )
        service = self._get_service(oauth_credential_ref)
        if service is None:
            if SETTINGS.simulate_publish_for_demo:
                # Demo-only path: real Google Business Profile review-reply API access
                # requires Google's manual approval (days-to-weeks, outside this project's
                # control) — SIMULATE_PUBLISH_FOR_DEMO lets the seed-data demo branches show
                # the real "published" UI state without ever touching a live API. This is
                # NEVER a substitute for the real publish call — it only activates when
                # there are no live credentials AND the flag is explicitly on.
                logger.warning(
                    "SIMULATED PUBLISH (SIMULATE_PUBLISH_FOR_DEMO=true, no live GBP "
                    "credentials) for review %s — no real API call made",
                    review_id,
                )
                return PublishResult(publication_state="approved", simulated=True)
            raise GbpApiError(
                f"No live GBP credentials for review {review_id}; cannot publish "
                "(seed-data branches are demo-only and don't support publish)."
            )
        try:
            self._publish_reply(service, gbp_location_id, review_id, content)
            state = self._get_reply_state(service, gbp_location_id, review_id)
            return PublishResult(publication_state=state)
        except Exception as exc:
            logger.error("GBP publish_reply failed after retries for %s: %s", review_id, exc)
            raise GbpApiError(str(exc)) from exc


def _star_rating_to_int(star: str) -> int:
    mapping = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
    return mapping.get(star.upper(), 3)


_client_singleton: GbpClient | None = None


def get_gbp_client() -> GbpClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = GbpClient()
    return _client_singleton
