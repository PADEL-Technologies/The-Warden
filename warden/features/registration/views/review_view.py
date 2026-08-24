import contextlib
import logging
from typing import TYPE_CHECKING

import asyncpg
import discord

from warden.features.registration.services.registration_service import (
    nickname,
    role_ids_for,
)
from warden.features.registration.views.reject_modal import RejectModal
from warden.features.registration.views.review_card import mark_decided
from warden.features.registration.views.threads import get_thread, speak, wake

if TYPE_CHECKING:
    from warden.config import Config
    from warden.features.registration.entities.registration import Registration
    from warden.features.registration.services.protocol import RegistrationService

log = logging.getLogger(__name__)


def is_verifier(user: discord.abc.User, verifier_role_id: int) -> bool:
    """Anyone who can see the message can click a Discord button — channel
    permissions are a second layer, not the guard."""
    if not isinstance(user, discord.Member):
        return False
    return user.guild_permissions.manage_guild or any(
        r.id == verifier_role_id for r in user.roles
    )


class ReviewView(discord.ui.View):
    def __init__(self, service: RegistrationService, config: Config) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.config = config

    async def resolve(self, interaction: discord.Interaction) -> Registration | None:
        """Authorize + lookup. None = already answered, callback must stop."""
        if not is_verifier(interaction.user, self.config.registration_verifier_role_id):
            log.warning(
                "registration: tombol review diklik non-verifikator",
                extra={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id,
                    "message_id": interaction.message.id,
                },
            )
            await interaction.response.send_message(
                "Cuma verifikator yang bisa memakai tombol ini.", ephemeral=True
            )
            return None
        reg = await self.service.by_report_message(interaction.message.id)
        if reg is None:
            log.warning(
                "registration: kartu review tanpa baris registrasi",
                extra={
                    "message_id": interaction.message.id,
                    "guild_id": interaction.guild_id,
                },
            )
            await interaction.response.send_message(
                "Kartu ini tidak punya baris registrasi.", ephemeral=True
            )
        return reg

    async def finish(
        self,
        interaction: discord.Interaction,
        decided: Registration,
        note: str,
    ) -> None:
        """Announce to the applicant's thread, then edit the card in place."""
        thread = await get_thread(interaction.guild, decided["thread_id"])
        if thread is not None:
            try:
                await speak(thread, content=f"<@{decided['user_id']}> {note}")
            except discord.HTTPException as exc:
                log.warning(
                    "registration: kabar keputusan tidak sampai ke pendaftar",
                    extra={
                        "registration_id": decided["id"],
                        "user_id": decided["user_id"],
                        "thread_id": decided["thread_id"],
                        "status": exc.status,
                    },
                )

        message = interaction.message
        embed = mark_decided(message.embeds[0], decided, interaction.user)
        disabled = ReviewView(self.service, self.config)
        for item in disabled.children:
            item.disabled = True
        await message.edit(embed=embed, view=disabled)

    async def already_decided(self, interaction: discord.Interaction) -> None:
        current = await self.service.by_report_message(interaction.message.id)
        who = f"<@{current['reviewed_by']}>" if current else "verifikator lain"
        await interaction.followup.send(
            f"Registrasi ini sudah diputuskan oleh {who}.", ephemeral=True
        )

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="registration:approve",
    )
    async def approve(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        reg = await self.resolve(interaction)
        if reg is None:
            return
        try:
            role_ids = role_ids_for(
                reg,
                mahasiswa_role_id=self.config.registration_mahasiswa_role_id,
                alumni_role_id=self.config.registration_alumni_role_id,
                prodi_roles=self.config.registration_prodi_roles,
            )
        except KeyError:
            log.warning(
                "registration: approve dibatalkan, prodi %r tidak ada di mapping",
                reg["prodi"],
                extra={
                    "registration_id": reg["id"],
                    "user_id": reg["user_id"],
                    "reviewed_by": interaction.user.id,
                },
            )
            await interaction.response.send_message(
                f"Prodi `{reg['prodi']}` tidak ada di `REGISTRATION_PRODI_ROLES`. "
                "Approve dibatalkan — perbaiki config dulu.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        # fetched once here: decide needs joined_at, _grant needs the object
        member = interaction.guild.get_member(reg["user_id"])
        try:
            decided = await self.service.decide(
                reg["id"],
                approve=True,
                reviewed_by=interaction.user.id,
                joined_at=member.joined_at.isoformat()
                if member and member.joined_at
                else None,
            )
        except asyncpg.UniqueViolationError:
            # the only index that can collide here: registrations_nim_approved
            holder = await self.service.nim_holder(reg["guild_id"], reg["nim"] or "")
            pemegang = f"<@{holder}>" if holder else "member lain"
            log.warning(
                "registration: approve dibatalkan, NIM sudah dipegang member lain",
                extra={
                    "registration_id": reg["id"],
                    "user_id": reg["user_id"],
                    "nim_holder": holder,
                    "reviewed_by": interaction.user.id,
                },
            )
            await interaction.followup.send(
                f"NIM ini sudah dipegang {pemegang}. Approve dibatalkan — reject "
                "saja, lalu minta orangnya daftar ulang dengan NIM yang benar.",
                ephemeral=True,
            )
            return
        if decided is None:
            await self.already_decided(interaction)
            return

        problem = await self._grant(interaction, decided, role_ids, member)
        await self.finish(
            interaction, decided, "registrasimu disetujui. Selamat datang!"
        )
        if problem:
            await interaction.followup.send(problem, ephemeral=True)

    async def _grant(
        self,
        interaction: discord.Interaction,
        reg: Registration,
        role_ids: list[int],
        member: discord.Member | None,
    ) -> str | None:
        """None = fine. Otherwise a message for the verifier — a failure here must
        not roll back an already-recorded approve."""
        if member is None:
            log.warning(
                "registration: approved tapi orangnya sudah keluar server",
                extra={"registration_id": reg["id"], "user_id": reg["user_id"]},
            )
            return (
                "Ditandai approved, tapi orangnya sudah keluar server. "
                "Role menyusul otomatis kalau dia join lagi."
            )
        roles = [discord.Object(id=r) for r in role_ids]
        try:
            await member.add_roles(*roles, reason=f"Registrasi · {interaction.user}")
        except discord.Forbidden:
            log.warning(
                "registration: add_roles ditolak untuk %d",
                member.id,
                extra={
                    "registration_id": reg["id"],
                    "user_id": member.id,
                    "role_ids": role_ids,
                },
            )
            return (
                "Ditandai approved, tapi bot tidak boleh memberi role itu. "
                "Naikkan posisi role bot di atas role tujuan, lalu beri manual."
            )
        # Nickname is not the important outcome; the server owner can't be
        # renamed by a bot regardless of permissions.
        with contextlib.suppress(discord.HTTPException):
            await member.edit(nick=nickname(reg))
        log.info(
            "registration: role dan nickname diberikan",
            extra={
                "registration_id": reg["id"],
                "user_id": member.id,
                "role_ids": role_ids,
            },
        )
        return None

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="registration:reject",
    )
    async def reject(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        reg = await self.resolve(interaction)
        if reg is None:
            return
        await interaction.response.send_modal(RejectModal(self, reg))

    @discord.ui.button(
        label="Join Thread",
        style=discord.ButtonStyle.secondary,
        custom_id="registration:join",
    )
    async def join(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        reg = await self.resolve(interaction)
        if reg is None:
            return
        log.debug(
            "registration: verifikator join thread",
            extra={
                "registration_id": reg["id"],
                "reviewed_by": interaction.user.id,
                "thread_id": reg["thread_id"],
            },
        )
        await interaction.response.defer(ephemeral=True)
        thread = await get_thread(interaction.guild, reg["thread_id"])
        if thread is None:
            await interaction.followup.send(
                "Threadnya sudah tidak ada.", ephemeral=True
            )
            return
        # the bot adds the verifier: `add_user` grants exactly one thread,
        # `Manage Threads` would grant the whole server
        await wake(thread)
        await thread.add_user(interaction.user)
        await interaction.followup.send(thread.jump_url, ephemeral=True)
