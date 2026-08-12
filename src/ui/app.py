"""Streamlit entrypoint — the single manager-facing UI (FR-018).

Every page requires a manager identity (FR-019), resolved in this order:

1. **Header-based** (`src/integrations/auth.py`) — IAP's injected header, if IAP is ever
   enabled (T052 follow-up). Cryptographically verified.
2. **Manager selector gate (Option C)** — fallback used in the actual 2026-08-12 deploy.
   Discovered live: Cloud Run's built-in `--no-allow-unauthenticated` IAM auth validates the
   caller's bearer token at the infra layer but STRIPS the `Authorization` header before
   forwarding the request to the container — so header-based resolution never succeeds on
   plain Cloud Run auth, only behind a real IAP-fronting Load Balancer. Since the outer gate
   (`roles/run.invoker`) already restricts who can reach this app at all, this fallback lets
   an already-invoker-authorized person pick which registered Manager they are from a closed
   list. This is a WEAKER attribution guarantee than #1 (self-declared, not per-request
   cryptographic proof) — see research.md § Deployment Update for the full writeup.
3. **`LOCAL_DEV_MODE`** — local/dev-only bypass, off by default, never used in the deployed
   environment.
"""

from __future__ import annotations

import os

import streamlit as st

from src.agents.orchestrator import ApprovalRequiredError, Orchestrator
from src.config.logging import get_logger
from src.integrations import auth, gbp_oauth
from src.models.branch import Branch
from src.models.manager import Manager
from src.models.review import Review, ReviewStatus, Severity
from src.storage.firestore_repo import get_repo

logger = get_logger(__name__)

st.set_page_config(page_title="Reputation Sentinel Ops", page_icon="\U0001F6E1️", layout="wide")


# ---------------------------------------------------------------------------------------
# Auth (FR-019 / SC-007) — closes /speckit-analyze finding C3
# ---------------------------------------------------------------------------------------

def _get_headers() -> dict:
    try:
        return dict(st.context.headers)
    except Exception:  # noqa: BLE001 — older Streamlit / local run without request context
        return {}


def _resolve_manager_from_headers() -> Manager | None:
    headers = _get_headers()
    try:
        return auth.resolve_authenticated_manager(headers)
    except auth.UnauthenticatedError:
        return None


def _resolve_manager_local_dev() -> Manager | None:
    if os.environ.get("LOCAL_DEV_MODE", "").lower() != "true":
        return None
    dev_email = os.environ.get("DEV_MANAGER_EMAIL")
    if not dev_email:
        return None
    repo = get_repo()
    mgr = repo.get_manager_by_email(dev_email)
    if mgr is None:
        mgr = Manager(manager_id="dev-manager", name="Dev Manager", google_identity_email=dev_email)
        repo.save_manager(mgr)
    st.warning(
        "⚠️ LOCAL_DEV_MODE active — bypassing auth using DEV_MANAGER_EMAIL. This flag "
        "MUST NOT be set in the deployed environment."
    )
    return mgr


def _render_manager_selector_gate() -> Manager | None:
    """Option C fallback (see module docstring). Reachable only by someone who already has
    `roles/run.invoker` on this Cloud Run service — the real access boundary — so this is a
    self-declaration among an already-vetted set, not the identity check itself."""
    repo = get_repo()

    if "selected_manager_id" in st.session_state:
        mgr = repo.get_manager(st.session_state["selected_manager_id"])
        if mgr is not None:
            return mgr

    managers = repo.list_managers()
    st.error(
        "\U0001F512 No header-verified identity found (expected on plain Cloud Run IAM "
        "auth — see module docstring). You reached this page, so Cloud Run already "
        "confirmed you hold `roles/run.invoker`; select which registered manager you are "
        "to continue."
    )
    if not managers:
        st.info(
            "No managers registered yet. Register one via the Firestore `managers` "
            "collection (google_identity_email required) before continuing."
        )
        return None

    options = {f"{m.name} <{m.google_identity_email}>": m.manager_id for m in managers}
    choice = st.selectbox("I am:", list(options.keys()))
    if st.button("Continue"):
        st.session_state["selected_manager_id"] = options[choice]
        logger.info("Manager selector gate: session bound to manager_id=%s", options[choice])
        st.rerun()
    return None


manager = (
    _resolve_manager_from_headers()
    or _resolve_manager_local_dev()
    or _render_manager_selector_gate()
)
if manager is None:
    st.stop()

repo = get_repo()
orchestrator = Orchestrator(repo)


# ---------------------------------------------------------------------------------------
# Navigation + urgent alert banner (US3 / T041-T042)
# ---------------------------------------------------------------------------------------

st.sidebar.title("\U0001F6E1️ Reputation Sentinel Ops")
st.sidebar.caption(f"Signed in as **{manager.google_identity_email}**")
page = st.sidebar.radio("Navigate", ["Inbox", "Connect Branch", "Digest"])

branches: list[Branch] = repo.list_branches(manager_id=manager.manager_id)

_all_open_reviews: list[Review] = [
    r for b in branches for r in repo.list_reviews(branch_id=b.branch_id)
    if r.status != ReviewStatus.PUBLISHED
]
urgent_reviews = [r for r in _all_open_reviews if r.severity == Severity.URGENT]
if urgent_reviews:
    st.error(
        f"\U0001F6A8 {len(urgent_reviews)} urgent review(s) need attention — see them "
        "flagged below in the Inbox."
    )


# ---------------------------------------------------------------------------------------
# Connect Branch (US1 / T022 — FR-001)
# ---------------------------------------------------------------------------------------

def render_connect_branch() -> None:
    st.header("Connect a Branch")
    st.caption(
        "Real Google Business Profile OAuth, or a seed-data demo branch if live access "
        "isn't ready yet (Principle IV fallback)."
    )

    tab_real, tab_seed = st.tabs(["Connect via Google (OAuth)", "Demo / Seed Data"])

    with tab_real:
        with st.form("connect_oauth_form"):
            name = st.text_input("Branch name")
            address = st.text_input("Address")
            location_id = st.text_input("Google Business Profile Location ID")
            redirect_uri = st.text_input(
                "OAuth redirect URI", value=os.environ.get("OAUTH_REDIRECT_URI", "")
            )
            submitted = st.form_submit_button("Get consent URL")
        if submitted and name and location_id and redirect_uri:
            try:
                url = gbp_oauth.build_consent_url(manager.manager_id, redirect_uri)
                st.success("Open this URL to grant access, then paste the redirected URL below.")
                st.code(url)
                st.session_state["pending_branch"] = {
                    "name": name,
                    "address": address,
                    "location_id": location_id,
                    "redirect_uri": redirect_uri,
                }
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not start OAuth flow: {exc}")

        if "pending_branch" in st.session_state:
            response_url = st.text_input("Paste the redirected URL here after granting access")
            if st.button("Complete connection") and response_url:
                pending = st.session_state["pending_branch"]
                try:
                    branch = gbp_oauth.complete_connection(
                        manager_id=manager.manager_id,
                        redirect_uri=pending["redirect_uri"],
                        authorization_response_url=response_url,
                        branch_name=pending["name"],
                        branch_address=pending["address"],
                        gbp_location_id=pending["location_id"],
                    )
                    del st.session_state["pending_branch"]
                    st.success(f"Connected {branch.name}.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not complete connection: {exc}")

    with tab_seed:
        with st.form("connect_seed_form"):
            seed_branch_id = st.selectbox("Seed branch", ["branch-demo-1", "branch-demo-2"])
            seed_name = st.text_input("Display name", value=seed_branch_id.replace("-", " ").title())
            seed_address = st.text_input("Address (demo)", value="Jl. Contoh No. 1, Jakarta")
            seed_submitted = st.form_submit_button("Connect demo branch")
        if seed_submitted:
            branch = gbp_oauth.connect_branch_with_seed_data(
                manager_id=manager.manager_id,
                branch_name=seed_name,
                branch_address=seed_address,
                seed_branch_id=seed_branch_id,
            )
            st.success(f"Connected demo branch {branch.name}.")
            st.rerun()

    if branches:
        st.subheader("Connected branches")
        for b in branches:
            st.write(f"- **{b.name}** ({b.connection_status.value}) — last sync: "
                      f"{b.last_ingested_at or 'never'}")


# ---------------------------------------------------------------------------------------
# Inbox (US1 / T026 + US2 draft/approve/reject / T032-T038 + US3 urgent / T041-T042)
# ---------------------------------------------------------------------------------------

def render_inbox() -> None:
    st.header("Unified Review Inbox")

    if not branches:
        st.info("No branches connected yet. Go to **Connect Branch** first.")
        return

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        if st.button("\U0001F504 Sync now", help="Manual ingestion trigger (T027)"):
            with st.spinner("Syncing reviews..."):
                cycle = orchestrator.run_ingestion_cycle(branches)
            total_new = sum(len(r.reviews) for r in cycle.ingestion_results)
            errors = [r for r in cycle.ingestion_results if r.sync_error]
            if errors:
                for r in errors:
                    st.warning(f"Sync error for {r.branch_id}: {r.sync_error}")
            st.success(f"Synced. {total_new} new review(s) ingested.")
            st.rerun()
    with col2:
        branch_filter = st.selectbox(
            "Branch", ["All"] + [b.name for b in branches], key="branch_filter"
        )
    with col3:
        sentiment_filter = st.selectbox(
            "Sentiment", ["All", "positive", "neutral", "negative"], key="sentiment_filter"
        )

    filtered_branches = branches if branch_filter == "All" else [
        b for b in branches if b.name == branch_filter
    ]
    reviews: list[Review] = []
    for b in filtered_branches:
        reviews.extend(repo.list_reviews(branch_id=b.branch_id))
    if sentiment_filter != "All":
        reviews = [r for r in reviews if r.sentiment and r.sentiment.value == sentiment_filter]

    if not reviews:
        st.info("No reviews match this filter yet.")
        return

    branch_by_id = {b.branch_id: b for b in branches}
    urgent_first = sorted(
        reviews, key=lambda r: (r.severity != Severity.URGENT, r.posted_at), reverse=False
    )

    for review in urgent_first:
        _render_review_row(review, branch_by_id.get(review.branch_id))


def _render_review_row(review: Review, branch: Branch | None) -> None:
    badges = []
    if review.severity == Severity.URGENT:
        badges.append("\U0001F6A8 URGENT")
    if review.status == ReviewStatus.ALREADY_ANSWERED:
        badges.append("✅ Already answered (skipped, FR-020)")
    elif review.status == ReviewStatus.PUBLISHED:
        badges.append("✅ Published")
    badge_str = " · ".join(badges)

    title = f"{'★' * review.rating}{'☆' * (5 - review.rating)}  {review.reviewer_name}  " \
            f"({branch.name if branch else review.branch_id})"
    if badge_str:
        title += f"  —  {badge_str}"

    with st.expander(title):
        st.write(review.text)
        meta = f"Sentiment: `{review.sentiment.value if review.sentiment else '—'}` · " \
               f"Topics: `{', '.join(review.topics) or '—'}` · " \
               f"Severity: `{review.severity.value if review.severity else '—'}` · " \
               f"Posted: {review.posted_at}"
        st.caption(meta)

        if review.status in {ReviewStatus.ALREADY_ANSWERED, ReviewStatus.PUBLISHED}:
            return  # nothing actionable — draft-and-approve flow doesn't apply (FR-020)

        draft = repo.get_active_draft(review.review_id)
        if draft is None:
            st.caption("No draft yet.")
            return

        edited = st.text_area("Draft reply", value=draft.content, key=f"draft-{draft.draft_id}")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ Approve & publish", key=f"approve-{draft.draft_id}"):
                try:
                    outcome = orchestrator.approve_draft(
                        draft.draft_id, manager.google_identity_email, edited_content=edited
                    )
                    if outcome.error:
                        st.warning(f"Approved, but publish failed: {outcome.error}")
                    elif outcome.simulated:
                        st.success(
                            f"Publication state: {outcome.publication_state.value} "
                            "🎭 (simulated — demo branch, no live GBP connection)"
                        )
                    else:
                        st.success(f"Publication state: {outcome.publication_state.value}")
                    st.rerun()
                except ApprovalRequiredError as exc:
                    st.error(f"Could not approve: {exc}")
        with col_b:
            if st.button("❌ Reject (regenerate)", key=f"reject-{draft.draft_id}"):
                orchestrator.reject_draft(draft.draft_id)
                st.info("Rejected. A new draft has been generated.")
                st.rerun()


# ---------------------------------------------------------------------------------------
# Digest (US4 / T045)
# ---------------------------------------------------------------------------------------

def render_digest() -> None:
    st.header("Cross-Branch Review Health Digest")
    if not branches:
        st.info("No branches connected yet.")
        return

    period = st.slider("Period (days)", min_value=7, max_value=90, value=30)
    if st.button("Generate digest"):
        with st.spinner("Computing branch health scores..."):
            digest = orchestrator.request_digest([b.branch_id for b in branches], period_days=period)
        branch_by_id = {b.branch_id: b for b in branches}
        for rank, score in enumerate(digest.rankings, start=1):
            name = branch_by_id.get(score.branch_id).name if score.branch_id in branch_by_id else score.branch_id
            st.metric(f"#{rank} {name}", f"{score.score}/100", f"{score.urgent_count} urgent")
            st.caption(f"Top topics: {', '.join(score.top_topics) or '—'}")


# ---------------------------------------------------------------------------------------

if page == "Connect Branch":
    render_connect_branch()
elif page == "Digest":
    render_digest()
else:
    render_inbox()
