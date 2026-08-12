"""Authenticated-identity resolution — FR-019, closes `/speckit-analyze` finding C3.

Two supported mechanisms, checked in order:

1. **Identity-Aware Proxy** (`X-Goog-Authenticated-User-Email`, format
   `accounts.google.com:user@example.com`) — the full production mechanism, not yet enabled
   (tasks.md T052 is still open pending the Load Balancer + managed cert setup).
2. **Cloud Run's built-in IAM auth** (`Authorization: Bearer <ID token>`) — the interim
   mechanism actually enforcing FR-019 right now. The service is deployed
   `--no-allow-unauthenticated`, so Cloud Run's front door already cryptographically
   verifies the bearer token and rejects the request before it ever reaches this code if the
   caller isn't an authorized `roles/run.invoker`. Decoding the JWT payload here is therefore
   claim *extraction*, not re-verification — the trust boundary is Cloud Run's IAM check,
   not this function. Managers reach the service via
   `gcloud run services proxy reputation-sentinel-ops --region=... `, which attaches their
   own ID token to every request automatically.

Either way, the UI MUST refuse to show review data or accept any approve/reject/publish
action if resolution fails (constitution Security & Data Handling) — never proceed with a
default/anonymous identity.
"""

from __future__ import annotations

import base64
import json

from src.config.logging import get_logger
from src.models.manager import Manager
from src.storage.firestore_repo import get_repo

logger = get_logger(__name__)

IAP_EMAIL_HEADER = "X-Goog-Authenticated-User-Email"
AUTHORIZATION_HEADER = "Authorization"


class UnauthenticatedError(RuntimeError):
    """Raised when no verified identity is present. Callers MUST deny access, never proceed
    with a default/anonymous identity."""


def _get_header_ci(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup — Streamlit/Cloud Run header casing isn't guaranteed."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def extract_email_from_iap_header(header_value: str | None) -> str | None:
    if not header_value:
        return None
    # IAP format: "accounts.google.com:user@example.com"
    if ":" in header_value:
        return header_value.split(":", 1)[1].strip() or None
    return header_value.strip() or None


def extract_email_from_cloud_run_bearer(header_value: str | None) -> str | None:
    """Extracts the `email` claim from a Cloud Run-validated `Authorization: Bearer <JWT>`
    header. No signature re-verification here — see module docstring for the trust
    boundary. Returns None on anything malformed rather than raising, so callers uniformly
    fall through to UnauthenticatedError."""
    if not header_value or not header_value.startswith("Bearer "):
        return None
    token = header_value[len("Bearer "):].strip()
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload_b64 = parts[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        email = payload.get("email")
        return str(email).strip() if email else None
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        logger.warning("Could not parse caller identity from bearer token: %s", exc)
        return None


def resolve_authenticated_manager(headers: dict[str, str]) -> Manager:
    """Raises UnauthenticatedError if no verified manager identity is found. Never returns a
    placeholder/anonymous Manager — FR-019 requires every action be attributable."""
    email = extract_email_from_iap_header(
        _get_header_ci(headers, IAP_EMAIL_HEADER)
    ) or extract_email_from_cloud_run_bearer(_get_header_ci(headers, AUTHORIZATION_HEADER))

    if not email:
        raise UnauthenticatedError("No authenticated identity present on this request")

    manager = get_repo().get_manager_by_email(email)
    if manager is None:
        logger.warning(
            "Authenticated identity %s has no Manager record — access denied", email
        )
        raise UnauthenticatedError(
            f"{email} is authenticated but not registered as a manager for this app"
        )
    return manager
