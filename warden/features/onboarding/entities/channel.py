from typing import TypedDict


class SnapshotChannel(TypedDict):
    channel_id: int
    name: str
    type: str  # str(guild.channel_type), e.g. text | voice | category
