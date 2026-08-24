"""Akses thread yang dipakai bareng tiga view dan sapuan cleanup."""

import contextlib

import discord

# Discord me-reset auto_archive_duration ke default server setiap thread
# di-unarchive — harus dipin ulang di setiap wake().
THREAD_ARCHIVE_MINUTES = 60


async def get_thread(
    guild: discord.Guild, thread_id: int | None
) -> discord.Thread | None:
    """Thread yang sudah ter-archive tidak ada di cache — harus di-fetch."""
    if thread_id is None:
        return None
    thread = guild.get_thread(thread_id)
    if thread is None:
        with contextlib.suppress(discord.HTTPException):
            fetched = await guild.fetch_channel(thread_id)
            thread = fetched if isinstance(fetched, discord.Thread) else None
    return thread


async def wake(thread: discord.Thread) -> None:
    """Unarchive sambil pin ulang durasinya: `edit(archived=False)` tanpa
    `auto_archive_duration` me-reset "Hide after inactivity" ke default
    server (bisa 1 Week)."""
    if thread.archived:
        await thread.edit(archived=False, auto_archive_duration=THREAD_ARCHIVE_MINUTES)


async def speak(thread: discord.Thread, **kwargs) -> None:
    """Keputusan bisa datang berhari-hari kemudian, saat threadnya sudah ter-archive."""
    await wake(thread)
    await thread.send(**kwargs)
