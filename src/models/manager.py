"""Manager entity — data-model.md § Manager.

`google_identity_email` is the authenticated identity (FR-019) resolved from the
Identity-Aware Proxy header; `Draft Reply.approved_by` is populated from this field, never
from client-supplied free text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AlertChannel(str, Enum):
    IN_APP = "in_app"  # only supported channel for MVP — no Slack/email (Assumptions)


@dataclass
class Manager:
    manager_id: str
    name: str
    google_identity_email: str
    branch_ids: list[str] = field(default_factory=list)
    alert_channel: AlertChannel = AlertChannel.IN_APP

    def to_dict(self) -> dict:
        return {
            "manager_id": self.manager_id,
            "name": self.name,
            "google_identity_email": self.google_identity_email,
            "branch_ids": self.branch_ids,
            "alert_channel": self.alert_channel.value,
        }

    @staticmethod
    def from_dict(data: dict) -> Manager:
        return Manager(
            manager_id=data["manager_id"],
            name=data.get("name", ""),
            google_identity_email=data["google_identity_email"],
            branch_ids=list(data.get("branch_ids", [])),
            alert_channel=AlertChannel(data.get("alert_channel", "in_app")),
        )
