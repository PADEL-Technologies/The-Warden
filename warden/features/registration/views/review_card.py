from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from warden.features.registration.entities.registration import Registration


def _dt(value) -> str:
    return (
        f"{discord.utils.format_dt(value, 'D')} ({discord.utils.format_dt(value, 'R')})"
    )


def build_review_embed(
    reg: Registration,
    member: discord.Member | discord.User | None,
    attempt: int,
    nim_holder: int | None,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Registrasi {(reg['type'] or '').capitalize()} · Percobaan ke-{attempt}",
        # mention untuk buka profil, id mentah karena mention tidak berguna
        # begitu orangnya keluar server
        description=f"<@{reg['user_id']}> · `{reg['user_id']}`",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )
    if nim_holder is not None:
        embed.add_field(
            name="⚠️ NIM sudah dipakai",
            value=f"<@{nim_holder}> sudah terverifikasi dengan NIM ini.",
            inline=False,
        )
    embed.add_field(name="Nama", value=reg["nama"] or "-")
    embed.add_field(name="Nama Panggilan", value=reg["nama_panggilan"] or "-")
    embed.add_field(name="Angkatan", value=reg["angkatan"] or "-")
    embed.add_field(name="NIM", value=reg["nim"] or "—")
    if reg["type"] == "mahasiswa":
        embed.add_field(name="Prodi", value=reg["prodi"] or "-")
    else:
        embed.add_field(name="LinkedIn", value=reg["linkedin"] or "-", inline=False)

    # satu-satunya sinyal alt account yang tersedia — ditampilkan, tidak dipakai
    # untuk aturan otomatis
    created = getattr(member, "created_at", None)
    joined = getattr(member, "joined_at", None)
    embed.add_field(
        name="Akun dibuat", value=_dt(created) if created else "tidak diketahui"
    )
    embed.add_field(
        name="Gabung server",
        value=_dt(joined) if joined else "sudah keluar server",
    )
    embed.set_footer(text="Disubmit")
    return embed


def mark_decided(
    embed: discord.Embed, reg: Registration, verifier: discord.abc.User
) -> discord.Embed:
    """Kartu diedit di tempat, bukan dihapus: #registration-report jadi log
    keputusan yang bisa digulir."""
    approved = reg["state"] == "approved"
    embed.color = discord.Color.green() if approved else discord.Color.red()
    if reg["reject_reason"]:
        embed.add_field(name="Alasan", value=reg["reject_reason"], inline=False)
    embed.timestamp = reg["reviewed_at"] or discord.utils.utcnow()
    embed.set_footer(text=f"{'Disetujui' if approved else 'Ditolak'} oleh {verifier}")
    return embed
