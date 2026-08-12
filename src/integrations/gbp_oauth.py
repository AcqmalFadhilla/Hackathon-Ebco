"""Branch-connect OAuth consent flow — FR-001.

Closes `/speckit-analyze` finding C1: FR-001 requires an in-app manager action to connect a
branch, not an out-of-band ops setup step. This module initiates the OAuth consent redirect,
completes the token exchange, stores the resulting token in Secret Manager, and creates the
`Branch` record.
"""

from __future__ import annotations

import uuid

from src.config.logging import get_logger
from src.config.settings import SETTINGS
from src.models.branch import Branch, ConnectionStatus
from src.storage.firestore_repo import get_repo

logger = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/business.manage"]


def build_consent_url(manager_id: str, redirect_uri: str) -> str:
    """Step 1: returns the Google OAuth consent URL for the manager to open."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(),
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=manager_id,
    )
    return auth_url


def complete_connection(
    manager_id: str,
    redirect_uri: str,
    authorization_response_url: str,
    branch_name: str,
    branch_address: str,
    gbp_location_id: str,
) -> Branch:
    """Step 2: exchanges the OAuth code for tokens, stores them in Secret Manager, and
    creates the Branch record (connection_status='connected')."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(),
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(authorization_response=authorization_response_url)
    credential_ref = f"branch-oauth-{uuid.uuid4().hex[:12]}"
    _store_credential_in_secret_manager(credential_ref, flow.credentials.to_json())

    branch = Branch(
        branch_id=f"branch-{uuid.uuid4().hex[:12]}",
        name=branch_name,
        address=branch_address,
        gbp_location_id=gbp_location_id,
        manager_id=manager_id,
        oauth_credential_ref=credential_ref,
        connection_status=ConnectionStatus.CONNECTED,
    )
    get_repo().save_branch(branch)
    logger.info("Connected branch %s (%s) for manager %s", branch.branch_id, branch_name, manager_id)
    return branch


def connect_branch_with_seed_data(
    manager_id: str, branch_name: str, branch_address: str, seed_branch_id: str
) -> Branch:
    """Demo-friendly path: registers a branch backed by the seed dataset instead of live
    OAuth, when the real GBP consent flow isn't ready yet (Principle IV — the demo must run).
    """
    branch = Branch(
        branch_id=seed_branch_id,
        name=branch_name,
        address=branch_address,
        gbp_location_id=f"seed:{seed_branch_id}",
        manager_id=manager_id,
        oauth_credential_ref="",
        connection_status=ConnectionStatus.CONNECTED,
    )
    get_repo().save_branch(branch)
    logger.info("Connected seed-data branch %s for manager %s", seed_branch_id, manager_id)
    return branch


def _store_credential_in_secret_manager(credential_ref: str, token_json: str) -> None:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{SETTINGS.gcp_project}"
    secret = client.create_secret(
        request={
            "parent": parent,
            "secret_id": credential_ref,
            "secret": {"replication": {"automatic": {}}},
        }
    )
    client.add_secret_version(
        request={"parent": secret.name, "payload": {"data": token_json.encode("utf-8")}}
    )


def _client_config() -> dict:
    import os

    return {
        "web": {
            "client_id": os.environ.get("GBP_OAUTH_CLIENT_ID", ""),
            "client_secret": os.environ.get("GBP_OAUTH_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
