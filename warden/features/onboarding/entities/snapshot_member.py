from typing import TypedDict

from warden.features.onboarding.entities.member_role import MemberRole


class SnapshotMember(TypedDict):
    member_id: int
    joined_at: str | None  # ISO 8601 (Standar Discord)
    roles: list[MemberRole]
