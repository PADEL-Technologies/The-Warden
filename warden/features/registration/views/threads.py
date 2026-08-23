"""Akses thread yang dipakai bareng tiga view dan sapuan cleanup."""

import contextlib

import discord


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


async def speak(thread: discord.Thread, **kwargs) -> None:
    """Keputusan bisa datang berhari-hari kemudian, saat threadnya sudah ter-archive."""
    if thread.archived:
        await thread.edit(archived=False)
    await thread.send(**kwargs)
