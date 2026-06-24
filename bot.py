"""
President Log Bot — discord.py
USA President Roleplay tracker.
"""

import discord
from discord import app_commands
from typing import Optional, Callable, Awaitable
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN                = os.getenv("DISCORD_TOKEN")
DATA_FILE            = "president_data.json"

COMMAND_COOLDOWN     = timedelta(minutes=5)
BUTTON_DIED_COOLDOWN = timedelta(minutes=2)
ALLOWED_CHANNEL_ID   = 1439820792320753703
REQUIRED_ROLE_ID     = 1439820790320201803

COLOR_ACTIVE = 0xF5C518   # 🟡 Yellow — active
COLOR_LOSS   = 0xFF4444   # 🔴 Red    — civilians won / president lost
COLOR_WIN    = 0x44DD88   # 🟢 Green  — presidency won

# ── Data persistence ──────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"log_nr": 0}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)

command_last_used: Optional[datetime] = None

def has_role(member: discord.Member) -> bool:
    return any(r.id == REQUIRED_ROLE_ID for r in member.roles)

# ── Generic confirm view (ephemeral) ─────────────────────────────────────────

class ConfirmView(discord.ui.View):
    def __init__(self, on_confirm: Callable[[discord.Interaction], Awaitable[None]]):
        super().__init__(timeout=30)
        self._cb = on_confirm

    def _lock(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="✅  Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._lock()
        await self._cb(interaction)
        self.stop()

    @discord.ui.button(label="❌  Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._lock()
        await interaction.response.edit_message(content="❌  Cancelled.", view=self)
        self.stop()

# ── Change Users modal ────────────────────────────────────────────────────────

class ChangeUsersModal(discord.ui.Modal, title="✏️  Change POTUS / VPOTUS"):
    new_potus  = discord.ui.TextInput(label="POTUS  (Roblox Username)", max_length=50)
    new_vpotus = discord.ui.TextInput(
        label="VPOTUS  (leave empty = None)",
        required=False,
        max_length=50,
    )

    def __init__(self, pv: "PresidentView", orig: discord.Message):
        super().__init__()
        self._pv, self._orig = pv, orig
        self.new_potus.default  = pv.potus
        self.new_vpotus.default = pv.vpotus or ""

    async def on_submit(self, interaction: discord.Interaction):
        np  = self.new_potus.value.strip()  or self._pv.potus
        nvp = self.new_vpotus.value.strip() or None
        pv, orig = self._pv, self._orig

        async def apply(ci: discord.Interaction):
            pv.potus, pv.vpotus = np, nvp
            await orig.edit(embed=pv.build_embed(), view=pv)
            await ci.response.edit_message(
                content=(
                    f"✅  **Users updated!**\n"
                    f"🏛️  POTUS  →  `{np}`\n"
                    f"🤝  VPOTUS →  `{nvp or 'None'}`"
                ),
                view=None,
            )

        await interaction.response.send_message(
            f"⚠️  **Confirm changes?**\n"
            f"🏛️  POTUS  →  `{np}`\n"
            f"🤝  VPOTUS →  `{nvp or 'None'}`",
            view=ConfirmView(apply),
            ephemeral=True,
        )

# ── President View ────────────────────────────────────────────────────────────

class PresidentView(discord.ui.View):
    def __init__(self, potus: str, vpotus: Optional[str], lives: int, author: discord.Member):
        super().__init__(timeout=None)
        self.potus   = potus
        self.vpotus  = vpotus
        self.lives   = lives
        self.author  = author
        self.died_cooldown_until: Optional[datetime] = None
        self.ended   = False

    # ── Embed builders ────────────────────────────────────────────────────────

    def build_embed(self) -> discord.Embed:
        hearts   = "❤️  " * self.lives + "🖤  " * max(0, 3 - self.lives)
        vpotus_v = f"`{self.vpotus}`" if self.vpotus else "*None*"

        embed = discord.Embed(
            title="🇺🇸  President Roleplay",
            color=COLOR_ACTIVE,
        )
        embed.set_author(
            name=self.author.display_name,
            icon_url=self.author.display_avatar.url,
        )
        embed.add_field(name="🏛️  POTUS",   value=f"`{self.potus}`", inline=True)
        embed.add_field(name="🤝  VPOTUS",  value=vpotus_v,          inline=True)
        embed.add_field(name="❤️  Lives",   value=hearts,            inline=False)
        embed.add_field(
            name="📋  Copy-paste command",
            value=f"```\n:h President: {self.potus} - Location: \n```",
            inline=False,
        )
        embed.set_footer(text="🟡  Status: Active  •  USA President Roleplay")
        return embed

    def build_end_embed(self, title: str, description: str, color: int) -> discord.Embed:
        vpotus_v = f"`{self.vpotus}`" if self.vpotus else "*None*"
        status   = "🔴  Civilians won" if color == COLOR_LOSS else "🟢  Presidency won"

        embed = discord.Embed(title=title, description=f"*{description}*", color=color)
        embed.set_author(
            name=self.author.display_name,
            icon_url=self.author.display_avatar.url,
        )
        embed.add_field(name="🏛️  POTUS",  value=f"`{self.potus}`", inline=True)
        embed.add_field(name="🤝  VPOTUS", value=vpotus_v,          inline=True)
        embed.set_footer(text=f"{status}  •  USA President Roleplay  •  Session ended")
        return embed

    # ── Helpers ───────────────────────────────────────────────────────────────

    def disable_all(self):
        for item in self.children:
            item.disabled = True
        self.ended = True

    async def guard(self, interaction: discord.Interaction) -> bool:
        """Returns True if the action may proceed."""
        if self.ended:
            await interaction.response.send_message(
                "❌  This session has already ended.", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not has_role(interaction.user):
            await interaction.response.send_message(
                "❌  You need the **On-Duty** role to use this!", ephemeral=True)
            return False
        return True

    # ── Buttons — Row 0 ───────────────────────────────────────────────────────

    @discord.ui.button(label="💀  POTUS died", style=discord.ButtonStyle.danger, row=0)
    async def potus_died(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return

        now = datetime.now()
        if self.died_cooldown_until and now < self.died_cooldown_until:
            rem  = int((self.died_cooldown_until - now).total_seconds())
            m, s = divmod(rem, 60)
            await interaction.response.send_message(
                f"⏳  Button on cooldown for **{m}m {s}s** more.", ephemeral=True)
            return

        orig, pv    = interaction.message, self
        after_lives = self.lives - 1

        async def apply(ci: discord.Interaction):
            pv.died_cooldown_until = datetime.now() + BUTTON_DIED_COOLDOWN
            pv.lives -= 1
            if pv.lives <= 0:
                pv.disable_all()
                embed = pv.build_end_embed(
                    "🏴  The civilians have won!",
                    f"{pv.potus} has run out of lives.",
                    COLOR_LOSS,
                )
            else:
                embed = pv.build_embed()
            await orig.edit(embed=embed, view=pv)
            await ci.response.edit_message(content="✅  Done!", view=None)

        after_txt = "**0  —  Session will end! 🏴**" if after_lives <= 0 else f"**{after_lives}**"
        await interaction.response.send_message(
            f"⚠️  **Are you sure?**\n"
            f"Removes **1 life** from `{self.potus}`.\n"
            f"Lives after: {after_txt}",
            view=ConfirmView(apply),
            ephemeral=True,
        )

    @discord.ui.button(label="🚪  POTUS left", style=discord.ButtonStyle.primary, row=0)
    async def potus_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return

        orig, pv = interaction.message, self
        suffix   = (f"`{self.vpotus}` will become the new POTUS."
                    if self.vpotus else "⚠️  **No VPOTUS — civilians will win!**")

        async def apply(ci: discord.Interaction):
            if pv.vpotus:
                old, pv.potus, pv.vpotus = pv.potus, pv.vpotus, None
                embed = pv.build_embed()
                embed.set_footer(text=f"⚡  {old} left → {pv.potus} is now POTUS  •  USA President Roleplay")
            else:
                pv.disable_all()
                embed = pv.build_end_embed(
                    "🏴  The civilians have won!",
                    "POTUS left with no VPOTUS to take over.",
                    COLOR_LOSS,
                )
            await orig.edit(embed=embed, view=pv)
            await ci.response.edit_message(content="✅  Done!", view=None)

        await interaction.response.send_message(
            f"⚠️  **Are you sure?**\n`{self.potus}` will leave.\n{suffix}",
            view=ConfirmView(apply),
            ephemeral=True,
        )

    @discord.ui.button(label="🏳️  VPOTUS & POTUS left", style=discord.ButtonStyle.secondary, row=0)
    async def both_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return

        orig, pv = interaction.message, self

        async def apply(ci: discord.Interaction):
            pv.disable_all()
            embed = pv.build_end_embed(
                "🏴  The civilians have won!",
                "Both POTUS and VPOTUS have abandoned their posts.",
                COLOR_LOSS,
            )
            await orig.edit(embed=embed, view=pv)
            await ci.response.edit_message(content="✅  Session ended — civilians win! 🏴", view=None)

        await interaction.response.send_message(
            f"⚠️  **Are you sure?**\n"
            f"Both `{self.potus}` and `{self.vpotus or 'None'}` will leave.\n"
            "🏴  **Civilians will win!**",
            view=ConfirmView(apply),
            ephemeral=True,
        )

    @discord.ui.button(label="🎉  PRTY over", style=discord.ButtonStyle.success, row=0)
    async def prty_over(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return

        orig, pv = interaction.message, self

        async def apply(ci: discord.Interaction):
            pv.disable_all()
            embed = pv.build_end_embed(
                "🎉  The POTUS & VPOTUS have won!",
                "The presidency has secured victory!",
                COLOR_WIN,
            )
            await orig.edit(embed=embed, view=pv)
            await ci.response.edit_message(content="✅  Session ended — presidency wins! 🎉", view=None)

        await interaction.response.send_message(
            "⚠️  **Are you sure?**\nThis ends the session with a 🟢 **presidency victory**.",
            view=ConfirmView(apply),
            ephemeral=True,
        )

    # ── Buttons — Row 1 ───────────────────────────────────────────────────────

    @discord.ui.button(label="✏️  Change Users", style=discord.ButtonStyle.secondary, row=1)
    async def change_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_modal(ChangeUsersModal(self, interaction.message))


# ── Slash commands ────────────────────────────────────────────────────────────

president_group = app_commands.Group(name="president", description="President roleplay commands")


@president_group.command(name="log", description="Start a new President Roleplay session")
@app_commands.describe(
    potus="Roblox username of the current POTUS",
    vpotus="Roblox username of the current VPOTUS (optional)",
)
async def president_log(
    interaction: discord.Interaction,
    potus: str,
    vpotus: Optional[str] = None,
):
    global command_last_used

    # Channel guard
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌  This command can only be used in <#{ALLOWED_CHANNEL_ID}>!", ephemeral=True)
        return

    # Role guard
    if not isinstance(interaction.user, discord.Member) or not has_role(interaction.user):
        await interaction.response.send_message(
            "❌  You need the **On-Duty** role to use this!", ephemeral=True)
        return

    # Cooldown
    now = datetime.now()
    if command_last_used is not None:
        elapsed = now - command_last_used
        if elapsed < COMMAND_COOLDOWN:
            remaining = int((COMMAND_COOLDOWN - elapsed).total_seconds())
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                f"⏳  Global cooldown — wait **{minutes}m {seconds}s** more.\n"
                "*(Buttons on active logs still work!)*",
                ephemeral=True,
            )
            return

    command_last_used = now

    # Increment log counter (kept for data tracking, not shown in embed)
    data = load_data()
    data["log_nr"] += 1
    save_data(data)

    view = PresidentView(potus=potus, vpotus=vpotus, lives=3, author=interaction.user)
    await interaction.response.send_message(embed=view.build_embed(), view=view)


@tree.command(name="h", description="Show President Roleplay Bot help")
async def cmd_h(interaction: discord.Interaction):
    embed = discord.Embed(title="🇺🇸  President Log Bot — Help", color=COLOR_ACTIVE)
    embed.add_field(name="📋  Commands", value=(
        "`/president log <potus> [vpotus]`\n"
        "→ Start a new roleplay session.\n\n"
        "`/h`\n"
        "→ Show this help message."
    ), inline=False)
    embed.add_field(name="🎮  Buttons", value=(
        "**💀 POTUS died** — Remove 1 life  *(2 min cooldown)*\n"
        "**🚪 POTUS left** — VPOTUS becomes POTUS\n"
        "**🏳️ VPOTUS & POTUS left** — Civilians win 🏴\n"
        "**🎉 PRTY over** — Presidency wins 🎉\n"
        "**✏️ Change Users** — Edit POTUS / VPOTUS names"
    ), inline=False)
    embed.add_field(name="⚙️  Rules", value=(
        "• Requires **On-Duty** role\n"
        f"• Only usable in <#{ALLOWED_CHANNEL_ID}>\n"
        "• 5 min cooldown between new sessions\n"
        "• All buttons require ephemeral confirmation"
    ), inline=False)
    embed.set_footer(text="USA President Roleplay Bot")
    await interaction.response.send_message(embed=embed, ephemeral=True)


tree.add_command(president_group)


# ── Events ────────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"✅  Logged in as {client.user}  (ID: {client.user.id})")
    print(f"✅  Synced {len(synced)} slash command(s)")
    print("─" * 40)
    print("Bot is running! Use /president log in Discord.")


if not TOKEN:
    raise ValueError("❌  DISCORD_TOKEN not found! Check your .env file.")

client.run(TOKEN)
