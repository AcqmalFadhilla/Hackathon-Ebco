"""Branch entity — data-model.md § Branch."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class Branch:
    branch_id: str
    name: str
    address: str
    gbp_location_id: str
    manager_id: str
    oauth_credential_ref: str
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_ingested_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "name": self.name,
            "address": self.address,
            "gbp_location_id": self.gbp_location_id,
            "manager_id": self.manager_id,
            "oauth_credential_ref": self.oauth_credential_ref,
            "connection_status": self.connection_status.value,
            "last_ingested_at": self.last_ingested_at,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict) -> Branch:
        return Branch(
            branch_id=data["branch_id"],
            name=data["name"],
            address=data.get("address", ""),
            gbp_location_id=data["gbp_location_id"],
            manager_id=data["manager_id"],
            oauth_credential_ref=data.get("oauth_credential_ref", ""),
            connection_status=ConnectionStatus(data.get("connection_status", "disconnected")),
            last_ingested_at=data.get("last_ingested_at"),
            created_at=data.get("created_at") or datetime.now(UTC),
        )
