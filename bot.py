"""
President Log Bot — discord.py
A roleplay tracker for USA President Roleplay communities.

Usage: /president log potus:RobloxName vpotus:RobloxName
"""

import discord
from discord import app_commands
from typing import Optional
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "president_data.json"

COMMAND_COOLDOWN = timedelta(minutes=5)
BUTTON_DIED_COOLDOWN = timedelta(minutes=2)

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
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

command_last_used: Optional[datetime] = None

# ── President Log View (Embed + Buttons) ──────────────────────────────────────

class PresidentView(discord.ui.View):
    def __init__(
        self,
        log_nr: int,
        potus: str,
        vpotus: Optional[str],
        lives: int,
        author: discord.Member,
    ):
        super().__init__(timeout=None)
        self.log_nr = log_nr
        self.potus = potus
        self.vpotus = vpotus
        self.lives = lives
        self.author = author
        self.died_cooldown_until: Optional[datetime] = None
        self.ended = False

    def build_embed(self) -> discord.Embed:
        hearts = "❤️" * self.lives + "🖤" * max(0, 3 - self.lives)
        vpotus_str = self.vpotus if self.vpotus else "*(None)*"

        embed = discord.Embed(
            title=f"President Log nr. {self.log_nr}",
            description=(
                f"**Current POTUS:** {self.potus}\n"
                f"**Current VPOTUS:** {vpotus_str}\n"
                f"**Lives:** {hearts}"
            ),
            color=0xE05C5C,
        )
        embed.set_author(
            name=self.author.display_name,
            icon_url=self.author.display_avatar.url,
        )
        return embed

    def build_end_embed(self, title: str, description: str, color: int) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_author(
            name=self.author.display_name,
            icon_url=self.author.display_avatar.url,
        )
        embed.set_footer(text=f"Log nr. {self.log_nr} • Game ended")
        return embed

    def disable_all(self):
        for item in self.children:
            item.disabled = True
        self.ended = True

    async def civilian_win(self, interaction: discord.Interaction, reason: str):
        self.disable_all()
        embed = self.build_end_embed("🏴 The civilians have won!", reason, 0xFF4444)
        await interaction.response.edit_message(embed=embed, view=self)

    async def presidency_win(self, interaction: discord.Interaction):
        self.disable_all()
        vpotus_str = self.vpotus if self.vpotus else "*(none)*"
        embed = self.build_end_embed(
            "🎉 The POTUS and VPOTUS have won!",
            f"**POTUS:** {self.potus}\n**VPOTUS:** {vpotus_str}",
            0x44DD88,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="POTUS died", style=discord.ButtonStyle.danger, emoji="💀")
    async def potus_died(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ended:
            await interaction.response.send_message("❌ This log has already ended.", ephemeral=True)
            return

        now = datetime.now()
        if self.died_cooldown_until and now < self.died_cooldown_until:
            remaining = int((self.died_cooldown_until - now).total_seconds())
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                f"⏳ This button is on cooldown for **{minutes}m {seconds}s** more.",
                ephemeral=True,
            )
            return

        self.died_cooldown_until = now + BUTTON_DIED_COOLDOWN
        self.lives -= 1

        if self.lives <= 0:
            await self.civilian_win(
                interaction,
                f"**{self.potus}** (POTUS) has run out of lives — the civilians prevail!",
            )
            return

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="POTUS left", style=discord.ButtonStyle.primary, emoji="🚪")
    async def potus_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ended:
            await interaction.response.send_message("❌ This log has already ended.", ephemeral=True)
            return

        if self.vpotus:
            old_potus = self.potus
            self.potus = self.vpotus
            self.vpotus = None

            embed = self.build_embed()
            embed.set_footer(text=f"{old_potus} left. {self.potus} is now POTUS.")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.civilian_win(
                interaction,
                "The POTUS left and there is **no VPOTUS** to take over — the civilians prevail!",
            )

    @discord.ui.button(label="VPOTUS & POTUS left", style=discord.ButtonStyle.secondary, emoji="🏳️")
    async def both_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ended:
            await interaction.response.send_message("❌ This log has already ended.", ephemeral=True)
            return
        await self.civilian_win(
            interaction,
            "Both the **POTUS and VPOTUS** have abandoned their posts — the civilians prevail!",
        )

    @discord.ui.button(label="PRTY over", style=discord.ButtonStyle.success, emoji="🎉")
    async def prty_over(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ended:
            await interaction.response.send_message("❌ This log has already ended.", ephemeral=True)
            return
        await self.presidency_win(interaction)


# ── Slash command ─────────────────────────────────────────────────────────────

president_group = app_commands.Group(name="president", description="President roleplay commands")


@president_group.command(name="log", description="Start a new President Log entry")
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
    now = datetime.now()

    if command_last_used is not None:
        elapsed = now - command_last_used
        if elapsed < COMMAND_COOLDOWN:
            remaining = int((COMMAND_COOLDOWN - elapsed).total_seconds())
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                f"⏳ This command is on a global **5-minute cooldown**!\n"
                f"Please wait **{minutes}m {seconds}s** more.\n"
                f"*(Buttons on active logs still work!)*",
                ephemeral=True,
            )
            return

    command_last_used = now

    data = load_data()
    data["log_nr"] += 1
    save_data(data)

    view = PresidentView(
        log_nr=data["log_nr"],
        potus=potus,
        vpotus=vpotus,
        lives=3,
        author=interaction.user,
    )
    await interaction.response.send_message(embed=view.build_embed(), view=view)


tree.add_command(president_group)


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
