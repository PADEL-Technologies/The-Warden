import discord

PAGE_SIZE = 20


class PagedListView(discord.ui.View):
    """Plain ◀ ▶ paging over a list of lines.

    Deliberately not persistent — no `add_view` at startup. This is an admin
    listing behind an ephemeral reply; when it times out the buttons should go
    dead rather than come back to life after a restart."""

    def __init__(self, title: str, lines: list[str], footer: str) -> None:
        super().__init__(timeout=180)
        self._title = title
        self._pages = [
            lines[i : i + PAGE_SIZE] for i in range(0, len(lines), PAGE_SIZE)
        ] or [["_(kosong)_"]]
        self._footer = footer
        self._page = 0
        self._sync()

    def embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self._title,
            description="\n".join(self._pages[self._page]),
            color=discord.Color.orange(),
        )
        embed.set_footer(
            text=f"Halaman {self._page + 1}/{len(self._pages)} · {self._footer}"
        )
        return embed

    def _sync(self) -> None:
        # The decorated callbacks are Button objects at runtime but plain
        # methods to a type checker; reach them through children instead.
        prev, nxt = self.children[:2]
        if isinstance(prev, discord.ui.Button):
            prev.disabled = self._page == 0
        if isinstance(nxt, discord.ui.Button):
            nxt.disabled = self._page >= len(self._pages) - 1

    async def _turn(self, interaction: discord.Interaction, delta: int) -> None:
        self._page = max(0, min(self._page + delta, len(self._pages) - 1))
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def prev(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._turn(interaction, -1)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def next(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._turn(interaction, 1)
