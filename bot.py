import discord
from discord import app_commands
from typing import Callable, Awaitable
import json
import os
import time
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TOKEN              = os.getenv("DISCORD_TOKEN")
DATA_FILE          = "president_data.json"
ALLOWED_CHANNEL_ID = 1439820792320753703
REQUIRED_ROLE_ID   = 1439820790320201803
BANNER_URL         = os.getenv("BANNER_URL", "")
ERLC_API_KEY       = os.getenv("ERLC_API_KEY", "")

COLOR_ACTIVE = 0xF5C518
COLOR_END    = 0x99AAB5

# ── Data ──────────────────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"log_nr": 0}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Bot ───────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)

def has_role(member: discord.Member) -> bool:
    return any(r.id == REQUIRED_ROLE_ID for r in member.roles)

# ── ER:LC API ─────────────────────────────────────────────────────────────────

async def erlc(command: str):
    if not ERLC_API_KEY:
        print("[ER:LC] ⚠️  No API key set — skipping command.")
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.policeroleplay.community/v1/server/command",
                headers={
                    "Server-Key": ERLC_API_KEY,
                    "Content-Type": "application/json",
                },
                json={"command": command},
            ) as resp:
                body = await resp.text()
                if resp.status in (200, 204):
                    print(f"[ER:LC] ✅  Sent: {command}")
                else:
                    print(f"[ER:LC] ⚠️  Status {resp.status} for: {command}")
                    print(f"[ER:LC] ⚠️  Response: {body}")
    except Exception as e:
        print(f"[ER:LC] ❌  Exception: {e}")

async def erlc_seq(*commands: str):
    for cmd in commands:
        await erlc(cmd)
        await asyncio.sleep(0.6)

async def erlc_after(delay: float, command: str):
    await asyncio.sleep(delay)
    await erlc(command)

async def erlc_potus_died(lives_remaining: int):
    life_word = "life" if lives_remaining == 1 else "lives"
    await erlc_seq(
        f":m ATTENTION: The president has lost a life. He/she now has {lives_remaining} {life_word} remaining. "
        f"There will now be a 2 minute cooldown. No shooting during the peacetimer. Everyone will now be healed.",
        ":pt 120",
        ":heal all",
    )
    asyncio.create_task(erlc_after(
        120,
        f":h The peacetimer has now ended. The president can be killed and has {lives_remaining} {life_word} remaining.",
    ))

async def erlc_civilians_win():
    await erlc_seq(
        ":m IMPORTANT: The civilians have won! The president has lost all 3 of their lives. "
        "An election to decide the next president will begin shortly.",
        ":prty 0",
    )

async def erlc_presidency_wins():
    await erlc(
        ":m IMPORTANT: The president has won! The president managed to stay alive until the end of the timer. "
        "An election to decide the next president will begin shortly."
    )

async def erlc_potus_left(new_potus: str):
    await erlc(
        f":m IMPORTANT: The president has left the game therefore the VP, {new_potus}, is the new president."
    )

async def erlc_both_left():
    await erlc(
        ":m IMPORTANT: The president and VP have both left the game therefore "
        "an election to decide the next president will begin soon."
    )

# ── Confirm View ──────────────────────────────────────────────────────────────

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

# ── Change Users Modal ────────────────────────────────────────────────────────

class ChangeUsersModal(discord.ui.Modal, title="Change POTUS / VPOTUS"):
    new_potus  = discord.ui.TextInput(label="POTUS (Roblox Username)", max_length=50)
    new_vpotus = discord.ui.TextInput(label="VPOTUS (Roblox Username)", max_length=50)

    def __init__(self, pv: "PresidentView", orig: discord.Message):
        super().__init__()
        self._pv, self._orig    = pv, orig
        self.new_potus.default  = pv.potus
        self.new_vpotus.default = pv.vpotus

    async def on_submit(self, interaction: discord.Interaction):
        np  = self.new_potus.value.strip()  or self._pv.potus
        nvp = self.new_vpotus.value.strip() or self._pv.vpotus
        pv, orig = self._pv, self._orig

        async def apply(ci: discord.Interaction):
            pv.potus, pv.vpotus = np, nvp
            pv.last_edited = int(time.time())
            await orig.edit(embed=pv.build_embed(), view=pv)
            await ci.response.edit_message(
                content=f"✅  Updated!\nPOTUS → `{np}`\nVPOTUS → `{nvp}`", view=None)

        await interaction.response.send_message(
            f"⚠️  **Confirm changes?**\nPOTUS → `{np}`\nVPOTUS → `{nvp}`",
            view=ConfirmView(apply), ephemeral=True)

# ── President View ────────────────────────────────────────────────────────────

class PresidentView(discord.ui.View):
    def __init__(self, potus: str, vpotus: str, lives: int, author: discord.Member):
        super().__init__(timeout=None)
        self.potus       = potus
        self.vpotus      = vpotus
        self.lives       = lives
        self.author      = author
        self.created_at  = int(time.time())
        self.last_edited: int | None = None
        self.ended       = False

    def _base(self, title: str, color: int) -> discord.Embed:
        e = discord.Embed(title=title, color=color)
        e.set_author(name=self.author.display_name, icon_url=self.author.display_avatar.url)
        if BANNER_URL:
            e.set_image(url=BANNER_URL)
        return e

    def _timestamps(self, embed: discord.Embed):
        edited = f"<t:{self.last_edited}:f> (<t:{self.last_edited}:R>)" if self.last_edited else "*Not yet edited*"
        embed.add_field(
            name="Timestamps",
            value=f"Created: <t:{self.created_at}:f>\nLast Edited: {edited}",
            inline=False,
        )

    def build_embed(self) -> discord.Embed:
        hearts = "❤️" * self.lives + "🖤" * max(0, 3 - self.lives)
        e = self._base("UPR - President Log", COLOR_ACTIVE)
        e.add_field(name="**__POTUS__**",  value=f"```{self.potus}```",  inline=True)
        e.add_field(name="**__VPOTUS__**", value=f"```{self.vpotus}```", inline=True)
        e.add_field(name="**__Lives__**",  value=hearts,                 inline=False)
        e.add_field(
            name="**Location · Copy-Paste Command**",
            value=f"```\n:h President: {self.potus} - Location: \n```",
            inline=False,
        )
        self._timestamps(e)
        e.set_footer(text="USA President Roleplay  •  UPR")
        e.timestamp = discord.utils.utcnow()
        return e

    def build_end_embed(self, title: str) -> discord.Embed:
        e = self._base(title, COLOR_END)
        e.add_field(name="**__POTUS__**",  value=f"```{self.potus}```",  inline=True)
        e.add_field(name="**__VPOTUS__**", value=f"```{self.vpotus}```", inline=True)
        self._timestamps(e)
        e.set_footer(text="USA President Roleplay  •  UPR")
        e.timestamp = discord.utils.utcnow()
        return e

    def disable_all(self):
        for item in self.children:
            item.disabled = True
        self.ended = True

    async def guard(self, interaction: discord.Interaction) -> bool:
        if self.ended:
            await interaction.response.send_message("❌  This log has already ended.", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not has_role(interaction.user):
            await interaction.response.send_message("❌  You need the **On-Duty** role!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="POTUS died", style=discord.ButtonStyle.danger, row=0)
    async def potus_died(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        orig, pv = interaction.message, self
        after    = self.lives - 1

        async def apply(ci: discord.Interaction):
            pv.lives -= 1
            pv.last_edited = int(time.time())
            if pv.lives <= 0:
                pv.disable_all()
                await orig.edit(embed=pv.build_end_embed("The civilians have won!"), view=None)
                await ci.response.edit_message(content="✅  Done!", view=None)
                await erlc_civilians_win()
            else:
                await orig.edit(embed=pv.build_embed(), view=pv)
                await ci.response.edit_message(content="✅  Done!", view=None)
                await erlc_potus_died(pv.lives)

        after_txt = "**0 — Log will end!**" if after <= 0 else f"**{after}**"
        await interaction.response.send_message(
            f"⚠️  **Are you sure?**\nRemoves 1 life from `{self.potus}`.\nLives after: {after_txt}",
            view=ConfirmView(apply), ephemeral=True)

    @discord.ui.button(label="PRTY over", style=discord.ButtonStyle.success, row=0)
    async def prty_over(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        orig, pv = interaction.message, self

        async def apply(ci: discord.Interaction):
            pv.last_edited = int(time.time())
            pv.disable_all()
            await orig.edit(embed=pv.build_end_embed("The POTUS & VPOTUS have won!"), view=None)
            await ci.response.edit_message(content="✅  Done!", view=None)
            await erlc_presidency_wins()

        await interaction.response.send_message(
            "⚠️  **Are you sure?**\nThis ends the log with a **presidency victory**.",
            view=ConfirmView(apply), ephemeral=True)

    @discord.ui.button(label="POTUS left", style=discord.ButtonStyle.secondary, row=0)
    async def potus_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        orig, pv = interaction.message, self

        async def apply(ci: discord.Interaction):
            old_potus      = pv.potus
            pv.potus       = pv.vpotus
            pv.vpotus      = "None"
            pv.last_edited = int(time.time())
            await orig.edit(embed=pv.build_embed(), view=pv)
            await ci.response.edit_message(
                content=f"✅  Done! `{old_potus}` left — `{pv.potus}` is now POTUS.", view=None)
            await erlc_potus_left(pv.potus)

        await interaction.response.send_message(
            f"⚠️  **Are you sure?**\n`{self.potus}` will leave.\n`{self.vpotus}` becomes the new POTUS.",
            view=ConfirmView(apply), ephemeral=True)

    @discord.ui.button(label="VPOTUS & POTUS left", style=discord.ButtonStyle.secondary, row=0)
    async def both_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        orig, pv = interaction.message, self

        async def apply(ci: discord.Interaction):
            pv.last_edited = int(time.time())
            pv.disable_all()
            await orig.edit(embed=pv.build_end_embed("The civilians have won!"), view=None)
            await ci.response.edit_message(content="✅  Done!", view=None)
            await erlc_both_left()

        await interaction.response.send_message(
            f"⚠️  **Are you sure?**\nBoth `{self.potus}` and `{self.vpotus}` will leave.\n**Civilians will win!**",
            view=ConfirmView(apply), ephemeral=True)

    @discord.ui.button(label="Change Users", style=discord.ButtonStyle.secondary, row=1)
    async def change_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_modal(ChangeUsersModal(self, interaction.message))

# ── Slash Commands ────────────────────────────────────────────────────────────

president_group = app_commands.Group(name="president", description="President roleplay commands")

@president_group.command(name="log", description="Start a new President Log")
@app_commands.describe(potus="Roblox username of the POTUS", vpotus="Roblox username of the VPOTUS")
async def president_log(interaction: discord.Interaction, potus: str, vpotus: str):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌  Only usable in <#{ALLOWED_CHANNEL_ID}>!", ephemeral=True); return
    if not isinstance(interaction.user, discord.Member) or not has_role(interaction.user):
        await interaction.response.send_message(
            "❌  You need the **On-Duty** role!", ephemeral=True); return

    data = load_data()
    data["log_nr"] += 1
    save_data(data)

    view = PresidentView(potus=potus, vpotus=vpotus, lives=3, author=interaction.user)
    await interaction.response.send_message(embed=view.build_embed(), view=view)

@tree.command(name="h", description="President Roleplay Bot — help")
async def cmd_h(interaction: discord.Interaction):
    e = discord.Embed(title="UPR - President Log Bot — Help", color=COLOR_ACTIVE)
    if BANNER_URL:
        e.set_image(url=BANNER_URL)
    e.add_field(name="📋  Commands", value=(
        "`/president log <potus> <vpotus>` → Start a new log.\n`/h` → This message."
    ), inline=False)
    e.add_field(name="🎮  Buttons", value=(
        "**POTUS died** — -1 life + ER:LC peacetimer\n"
        "**PRTY over** — Presidency wins\n"
        "**POTUS left** — VP becomes new POTUS\n"
        "**VPOTUS & POTUS left** — Civilians win\n"
        "**Change Users** — Edit names"
    ), inline=False)
    e.add_field(name="⚙️  Rules", value=(
        "• Requires **On-Duty** role\n"
        f"• Only in <#{ALLOWED_CHANNEL_ID}>\n"
        "• All actions require confirmation"
    ), inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

tree.add_command(president_group)

@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"✅  Logged in as {client.user}  (ID: {client.user.id})")
    print(f"✅  Synced {len(synced)} slash command(s)")
    if ERLC_API_KEY:
        print("✅  ER:LC API key found — in-game commands enabled!")
    else:
        print("⚠️  No ER:LC API key — add ERLC_API_KEY to .env to enable in-game commands.")
    print("─" * 40)

if not TOKEN:
    raise ValueError("❌  DISCORD_TOKEN not found! Check your .env file.")

client.run(TOKEN)


