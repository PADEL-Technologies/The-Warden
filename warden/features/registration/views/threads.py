"""Thread access shared by three views and the cleanup sweep."""

import contextlib

import discord

# Discord resets auto_archive_duration to the server default on unarchive —
# must be re-pinned on every wake().
THREAD_ARCHIVE_MINUTES = 60


async def get_thread(
    guild: discord.Guild, thread_id: int | None
) -> discord.Thread | None:
    """Archived threads are not in the cache — must be fetched."""
    if thread_id is None:
        return None
    thread = guild.get_thread(thread_id)
    if thread is None:
        with contextlib.suppress(discord.HTTPException):
            fetched = await guild.fetch_channel(thread_id)
            thread = fetched if isinstance(fetched, discord.Thread) else None
    return thread


async def wake(thread: discord.Thread) -> None:
    """Unarchive while re-pinning duration: `edit(archived=False)` without
    `auto_archive_duration` resets "Hide after inactivity" to the server
    default (can be 1 Week)."""
    if thread.archived:
        await thread.edit(archived=False, auto_archive_duration=THREAD_ARCHIVE_MINUTES)


async def speak(thread: discord.Thread, **kwargs) -> None:
    """The decision can arrive days later, when the thread is already archived."""
    await wake(thread)
    await thread.send(**kwargs)
