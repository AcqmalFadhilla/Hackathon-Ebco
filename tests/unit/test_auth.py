"""Unit tests for FR-019 identity resolution — both the IAP path and the Cloud Run
IAM-auth fallback (Option B, adopted after T052's full IAP setup was deferred)."""

import base64
import json

import pytest

from src.integrations import auth


def _fake_jwt(payload: dict) -> str:
    header_b64 = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.fake-signature"


def test_extract_email_from_iap_header_strips_provider_prefix():
    assert auth.extract_email_from_iap_header("accounts.google.com:mgr@example.com") == "mgr@example.com"


def test_extract_email_from_iap_header_handles_missing_prefix():
    assert auth.extract_email_from_iap_header("mgr@example.com") == "mgr@example.com"


def test_extract_email_from_iap_header_none_when_absent():
    assert auth.extract_email_from_iap_header(None) is None


def test_extract_email_from_cloud_run_bearer_parses_email_claim():
    token = _fake_jwt({"email": "mgr@example.com", "aud": "some-service"})
    assert auth.extract_email_from_cloud_run_bearer(f"Bearer {token}") == "mgr@example.com"


def test_extract_email_from_cloud_run_bearer_rejects_non_bearer():
    assert auth.extract_email_from_cloud_run_bearer("Basic abc123") is None


def test_extract_email_from_cloud_run_bearer_rejects_malformed_token():
    assert auth.extract_email_from_cloud_run_bearer("Bearer not-a-jwt") is None


def test_extract_email_from_cloud_run_bearer_none_when_absent():
    assert auth.extract_email_from_cloud_run_bearer(None) is None


def test_resolve_authenticated_manager_prefers_iap_over_bearer(monkeypatch):
    from src.models.manager import Manager
    from src.storage.firestore_repo import InMemoryRepository

    repo = InMemoryRepository()
    manager = Manager(manager_id="m1", name="Test", google_identity_email="iap@example.com")
    repo.save_manager(manager)
    monkeypatch.setattr(auth, "get_repo", lambda: repo)

    token = _fake_jwt({"email": "bearer@example.com"})
    headers = {
        "X-Goog-Authenticated-User-Email": "accounts.google.com:iap@example.com",
        "Authorization": f"Bearer {token}",
    }

    resolved = auth.resolve_authenticated_manager(headers)

    assert resolved.manager_id == "m1"


def test_resolve_authenticated_manager_falls_back_to_bearer(monkeypatch):
    from src.models.manager import Manager
    from src.storage.firestore_repo import InMemoryRepository

    repo = InMemoryRepository()
    manager = Manager(manager_id="m2", name="Test", google_identity_email="bearer@example.com")
    repo.save_manager(manager)
    monkeypatch.setattr(auth, "get_repo", lambda: repo)

    token = _fake_jwt({"email": "bearer@example.com"})
    headers = {"authorization": f"Bearer {token}"}  # lowercase — case-insensitive lookup

    resolved = auth.resolve_authenticated_manager(headers)

    assert resolved.manager_id == "m2"


def test_resolve_authenticated_manager_raises_when_no_identity(monkeypatch):
    from src.storage.firestore_repo import InMemoryRepository

    monkeypatch.setattr(auth, "get_repo", lambda: InMemoryRepository())

    with pytest.raises(auth.UnauthenticatedError):
        auth.resolve_authenticated_manager({})


def test_resolve_authenticated_manager_raises_when_identity_not_registered(monkeypatch):
    from src.storage.firestore_repo import InMemoryRepository

    monkeypatch.setattr(auth, "get_repo", lambda: InMemoryRepository())
    token = _fake_jwt({"email": "unregistered@example.com"})

    with pytest.raises(auth.UnauthenticatedError):
        auth.resolve_authenticated_manager({"Authorization": f"Bearer {token}"})
