from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from warden.features.onboarding.entities.member_role import MemberRole


class SnapshotMember(TypedDict):
    member_id: int
    joined_at: str | None  # ISO 8601 (Standar Discord)
    roles: list[MemberRole]
