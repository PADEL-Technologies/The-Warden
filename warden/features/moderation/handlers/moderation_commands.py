import logging
import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from warden.features.moderation.services.labels import (
    ENFORCED_LABELS,
    LABELS,
    REGISTRABLE_LABELS,
)
from warden.features.moderation.services.moderation_service import validate_pattern
from warden.features.moderation.services.normalizer import normalize
from warden.features.moderation.views.paged_list_view import PagedListView

if TYPE_CHECKING:
    from warden.features.moderation.services.protocol import ModerationService

log = logging.getLogger(__name__)

LABEL_CHOICES = [app_commands.Choice(name=x, value=x) for x in REGISTRABLE_LABELS]
FILTER_CHOICES = [app_commands.Choice(name=x, value=x) for x in LABELS]
TARGET_CHOICES = [
    app_commands.Choice(name="raw — teks apa adanya", value="raw"),
    app_commands.Choice(name="normalized — teks ternormalisasi", value="normalized"),
]


class NotAllowed(app_commands.CheckFailure):
    pass


def owner_or_admin_role():
    """App owner (from the Developer Portal, so it survives a change of server
    ownership) or one of MODERATION_ADMIN_ROLE_IDS."""

    async def predicate(interaction: discord.Interaction) -> bool:
        bot = interaction.client
        if isinstance(bot, commands.Bot) and await bot.is_owner(interaction.user):
            return True
        allowed = set(interaction.client.config.moderation_admin_role_ids)  # type: ignore[attr-defined]
        if isinstance(interaction.user, discord.Member) and any(
            role.id in allowed for role in interaction.user.roles
        ):
            return True
        raise NotAllowed

    return app_commands.check(predicate)


def _summary(parts: list[tuple[str, list[str]]]) -> str:
    """`[("ditambahkan", [...]), ...]` → one line per non-empty bucket. Buckets
    that stayed empty are left out; a term that was not found is named rather
    than silently dropped."""
    lines = [
        f"**{len(items)} {name}**: {', '.join(f'`{i}`' for i in items)}"
        for name, items in parts
        if items
    ]
    return "\n".join(lines) or "Tidak ada yang berubah."


class ModerationCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, service: ModerationService) -> None:
        self.bot = bot
        self.service = service

    keyword = app_commands.Group(
        name="keyword", description="Kelola daftar kata terlarang"
    )
    regex = app_commands.Group(name="regex", description="Kelola aturan regex")
    label = app_commands.Group(name="label", description="Lihat label moderasi")

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Without this a failed check shows "This interaction failed" and
        nothing else."""
        if not isinstance(error, NotAllowed):
            raise error
        log.warning(
            "moderation: command ditolak, bukan owner/admin",
            extra={
                "user_id": interaction.user.id,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "command": interaction.command.qualified_name
                if interaction.command
                else None,
            },
        )
        await interaction.response.send_message(
            "Command ini hanya untuk owner bot dan role admin moderasi.",
            ephemeral=True,
        )

    # --- keyword ---------------------------------------------------------

    @keyword.command(name="add", description="Tambah satu atau banyak keyword")
    @app_commands.describe(
        label="Label untuk keyword ini",
        keywords="Satu keyword, atau banyak dipisah koma",
    )
    @app_commands.choices(label=LABEL_CHOICES)
    @owner_or_admin_role()
    async def keyword_add(
        self, interaction: discord.Interaction, label: str, keywords: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        added, already, reactivated = await self.service.add_keywords(
            label, keywords, interaction.user.id
        )
        log.info(
            "moderation: keyword ditambahkan",
            extra={
                "label": label,
                "user_id": interaction.user.id,
                "added": len(added),
                "already": len(already),
                "reactivated": len(reactivated),
            },
        )
        await interaction.followup.send(
            f"Label `{label}`\n"
            + _summary(
                [
                    ("ditambahkan", added),
                    ("diaktifkan kembali", reactivated),
                    ("sudah ada", already),
                ]
            ),
            ephemeral=True,
        )

    @keyword.command(name="remove", description="Nonaktifkan keyword")
    @app_commands.describe(
        label="Label keyword tersebut",
        keywords="Satu keyword, atau banyak dipisah koma",
    )
    @app_commands.choices(label=LABEL_CHOICES)
    @owner_or_admin_role()
    async def keyword_remove(
        self, interaction: discord.Interaction, label: str, keywords: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        removed, not_found = await self.service.remove_keywords(label, keywords)
        log.info(
            "moderation: keyword dinonaktifkan",
            extra={
                "label": label,
                "user_id": interaction.user.id,
                "removed": len(removed),
                "not_found": len(not_found),
            },
        )
        await interaction.followup.send(
            f"Label `{label}`\n"
            + _summary([("dihapus", removed), ("tidak ditemukan", not_found)]),
            ephemeral=True,
        )

    @keyword.command(name="list", description="Lihat keyword yang terdaftar")
    @app_commands.describe(
        label="Batasi ke satu label", show_disabled="Ikut tampilkan yang nonaktif"
    )
    @app_commands.choices(label=FILTER_CHOICES)
    @owner_or_admin_role()
    async def keyword_list(
        self,
        interaction: discord.Interaction,
        label: str | None = None,
        show_disabled: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        rows = await self.service.list_keywords(label, show_disabled)
        lines = [
            f"`{r['term']}` — {r['label']}" + ("" if r["enabled"] else " *(nonaktif)*")
            for r in rows
        ]
        view = PagedListView(
            title=f"Keyword: {label or 'semua label'}",
            lines=lines,
            footer=f"{len(rows)} keyword",
        )
        await interaction.followup.send(embed=view.embed(), view=view, ephemeral=True)

    # --- regex -----------------------------------------------------------

    @regex.command(name="add", description="Tambah aturan regex")
    @app_commands.describe(
        label="Label untuk aturan ini",
        pattern="Pola regex Python",
        target="Dicocokkan ke teks mentah (default) atau ternormalisasi",
        note="Catatan singkat, muncul di /regex list",
    )
    @app_commands.choices(label=LABEL_CHOICES, target=TARGET_CHOICES)
    @owner_or_admin_role()
    async def regex_add(
        self,
        interaction: discord.Interaction,
        label: str,
        pattern: str,
        target: str = "raw",
        note: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        problem = validate_pattern(pattern)
        if problem is not None:
            log.warning(
                "moderation: pola regex ditolak",
                extra={"user_id": interaction.user.id, "reason": problem},
            )
            await interaction.followup.send(f"❌ {problem}", ephemeral=True)
            return
        rule = await self.service.add_rule(
            label, pattern, target, note, interaction.user.id
        )
        if rule is None:
            await interaction.followup.send(
                f"Pola itu sudah terdaftar di label `{label}`.", ephemeral=True
            )
            return
        log.info(
            "moderation: aturan regex ditambahkan",
            extra={
                "rule_id": rule["id"],
                "label": label,
                "target": target,
                "user_id": interaction.user.id,
            },
        )
        enforced = "menghapus pesan" if label in ENFORCED_LABELS else "mencatat saja"
        await interaction.followup.send(
            f"Aturan `#{rule['id']}` ditambahkan ke `{label}` "
            f"(target `{target}`, {enforced}).",
            ephemeral=True,
        )

    @regex.command(name="remove", description="Nonaktifkan aturan regex")
    @app_commands.describe(id="ID aturan, lihat /regex list")
    @owner_or_admin_role()
    async def regex_remove(self, interaction: discord.Interaction, id: int) -> None:
        await interaction.response.defer(ephemeral=True)
        rule = await self.service.remove_rule(id)
        if rule is None:
            await interaction.followup.send(
                f"Tidak ada aturan aktif dengan ID `{id}`.", ephemeral=True
            )
            return
        log.info(
            "moderation: aturan regex dinonaktifkan",
            extra={
                "rule_id": id,
                "label": rule["label"],
                "user_id": interaction.user.id,
            },
        )
        await interaction.followup.send(
            f"Aturan `#{id}` (`{rule['label']}`) dinonaktifkan.", ephemeral=True
        )

    @regex.command(name="list", description="Lihat aturan regex")
    @app_commands.describe(
        label="Batasi ke satu label", show_disabled="Ikut tampilkan yang nonaktif"
    )
    @app_commands.choices(label=FILTER_CHOICES)
    @owner_or_admin_role()
    async def regex_list(
        self,
        interaction: discord.Interaction,
        label: str | None = None,
        show_disabled: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        rows = await self.service.list_rules(label, show_disabled)
        lines = [
            f"`#{r['id']}` **{r['label']}** ({r['target']}) — ``{r['pattern']}``"
            + ("" if r["enabled"] else " *(nonaktif)*")
            for r in rows
        ]
        view = PagedListView(
            title=f"Aturan regex: {label or 'semua label'}",
            lines=lines,
            footer=f"{len(rows)} aturan",
        )
        await interaction.followup.send(embed=view.embed(), view=view, ephemeral=True)

    @regex.command(name="test", description="Coba pola sebelum didaftarkan")
    @app_commands.describe(pattern="Pola regex Python", text="Teks contoh")
    @owner_or_admin_role()
    async def regex_test(
        self, interaction: discord.Interaction, pattern: str, text: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        problem = validate_pattern(pattern)
        if problem is not None:
            await interaction.followup.send(f"❌ {problem}", ephemeral=True)
            return
        # Same validation the real add goes through, so a pattern that passes
        # here is a pattern that will be accepted.
        compiled = re.compile(pattern)

        def outcome(hit: re.Match[str] | None) -> str:
            return f"cocok → ``{hit.group(0)}``" if hit else "tidak cocok"

        # Both targets are shown so the `target` choice can be made from
        # evidence rather than guessed.
        await interaction.followup.send(
            f"Pola valid.\n"
            f"`raw`: {outcome(compiled.search(text))}\n"
            f"`normalized`: {outcome(compiled.search(normalize(text)))}",
            ephemeral=True,
        )

    # --- label -----------------------------------------------------------

    @label.command(name="list", description="Lihat label yang tersedia")
    @owner_or_admin_role()
    async def label_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        counts = await self.service.counts()
        lines = []
        for name in LABELS:
            keywords, rules = counts.get(name, (0, 0))
            if name == "neutral":
                note = "tidak bisa didaftarkan — ketiadaan hit"
            elif name in ENFORCED_LABELS:
                note = "**pesan dihapus**"
            else:
                note = "dicatat saja"
            lines.append(f"`{name}` — {keywords} keyword, {rules} regex · {note}")
        embed = discord.Embed(
            title="Label moderasi",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
