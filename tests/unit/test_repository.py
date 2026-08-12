"""Unit tests for InMemoryRepository — covers list_managers, added for the manager
selector gate (Option C, src/ui/app.py)."""

from src.models.manager import Manager
from src.storage.firestore_repo import InMemoryRepository


def test_list_managers_returns_all_saved_managers():
    repo = InMemoryRepository()
    repo.save_manager(Manager(manager_id="m1", name="A", google_identity_email="a@example.com"))
    repo.save_manager(Manager(manager_id="m2", name="B", google_identity_email="b@example.com"))

    managers = repo.list_managers()

    assert {m.manager_id for m in managers} == {"m1", "m2"}


def test_list_managers_empty_when_none_saved():
    repo = InMemoryRepository()

    assert repo.list_managers() == []
