"""Contract tests for the GBP client adapter — contracts/gbp-api-usage.md.

tasks.md T020 (read path) + T031 (publish + publication-state path). No live GBP
credentials are used — these tests exercise the seed-data fallback contract (read) and the
error contract (publish without credentials), which is exactly what the app relies on when
running without live OAuth (Principle IV).
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.integrations.gbp_client import GbpApiError, GbpClient


def test_list_reviews_since_falls_back_to_seed_data_without_credentials():
    client = GbpClient()

    reviews = client.list_reviews_since(
        branch_id="branch-demo-1",
        gbp_location_id="seed:branch-demo-1",
        oauth_credential_ref="",  # no credentials -> seed-data fallback contract
        since=None,
    )

    assert reviews, "seed dataset for branch-demo-1 must be non-empty"
    assert all(r.review_id.startswith("seed-b1-") for r in reviews)


def test_list_reviews_since_respects_window_start():
    client = GbpClient()
    future_cutoff = datetime.now(UTC) + timedelta(days=1)

    reviews = client.list_reviews_since(
        branch_id="branch-demo-1",
        gbp_location_id="seed:branch-demo-1",
        oauth_credential_ref="",
        since=future_cutoff,  # nothing should be "since the future"
    )

    assert reviews == []


def test_list_reviews_since_unknown_branch_returns_empty_not_error():
    client = GbpClient()

    reviews = client.list_reviews_since(
        branch_id="branch-does-not-exist",
        gbp_location_id="seed:branch-does-not-exist",
        oauth_credential_ref="",
        since=None,
    )

    assert reviews == []


def test_publish_reply_without_credentials_raises_gbp_api_error():
    """Publish-path contract (T031): with no live credentials, publish MUST fail loudly
    (GbpApiError), never silently pretend success — the Orchestrator relies on this to
    surface publish failures to the manager (FR-013)."""
    client = GbpClient()

    with pytest.raises(GbpApiError):
        client.publish_reply(
            gbp_location_id="seed:branch-demo-1",
            oauth_credential_ref="",
            review_id="seed-b1-r1",
            content="Terima kasih atas review Anda!",
        )


def test_publish_reply_simulated_when_demo_flag_enabled(monkeypatch):
    """SIMULATE_PUBLISH_FOR_DEMO lets seed branches show a real 'published' UI state
    without a live GBP connection — demo-only, must be clearly flagged as simulated."""
    import dataclasses

    from src.integrations import gbp_client as gbp_client_module

    demo_settings = dataclasses.replace(gbp_client_module.SETTINGS, simulate_publish_for_demo=True)
    monkeypatch.setattr(gbp_client_module, "SETTINGS", demo_settings)
    client = GbpClient()

    result = client.publish_reply(
        gbp_location_id="seed:branch-demo-1",
        oauth_credential_ref="",
        review_id="seed-b1-r1",
        content="Terima kasih atas review Anda!",
    )

    assert result.publication_state == "approved"
    assert result.simulated is True


def test_publish_reply_not_simulated_by_default():
    """Default (SIMULATE_PUBLISH_FOR_DEMO unset) must still raise — the demo flag is opt-in
    only, never silently on."""
    from src.config.settings import SETTINGS

    assert SETTINGS.simulate_publish_for_demo is False
    client = GbpClient()

    with pytest.raises(GbpApiError):
        client.publish_reply(
            gbp_location_id="seed:branch-demo-1",
            oauth_credential_ref="",
            review_id="seed-b1-r1",
            content="Terima kasih atas review Anda!",
        )
