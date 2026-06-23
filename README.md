# 🇺🇸 President Log Bot — Setup & Hosting Guide

A Discord bot for USA President Roleplay communities. Creates tracked log entries with interactive buttons.

---

## Features

- `/president log @potus @vpotus` — creates a new President Log embed
- **POTUS died** button — removes 1 life (2-minute cooldown per click)
- **POTUS left** button — VPOTUS becomes POTUS
- **VPOTUS & POTUS left** button — civilians win
- **PRTY over** button — presidency wins
- Auto-ends when lives reach 0 (civilians win)
- Log number increments globally and persists across restarts
- 5-minute global command cooldown (buttons always work regardless)

---

## Step 1 — Create the Discord Bot

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name (e.g. *President Log Bot*)
3. Click on **Bot** in the left sidebar
4. Click **Reset Token** → copy and save the token somewhere safe *(you'll need it later)*
5. Scroll down and enable **PUBLIC BOT** if you want others to invite it
6. Under **Privileged Gateway Intents**, enable nothing — the bot needs no special intents

### Invite the bot to your server

1. Go to **OAuth2 → URL Generator** in the sidebar
2. Under **Scopes**, check: `bot` and `applications.commands`
3. Under **Bot Permissions**, check: `Send Messages`, `Embed Links`, `Use Slash Commands`
4. Copy the generated URL at the bottom and open it in your browser
5. Select your server and click **Authorize**

---

## Step 2 — Set Up the Project

### Requirements
- Python **3.10 or newer** ([python.org/downloads](https://www.python.org/downloads/))
- pip (comes with Python)

### Install dependencies

Open a terminal/command prompt in the project folder and run:

```bash
pip install -r requirements.txt
```

### Configure the token

1. Rename `.env.example` to `.env`
2. Open `.env` and replace `your_bot_token_here` with your actual bot token:

```
DISCORD_TOKEN=MTExxxxxxxxxxxxxxxxxxx.Gyyyyy.zzzzzzzzzzzzzzzzzzzzzzzzzzz
```

> ⚠️ **Never share your token!** It gives full control over your bot.

---

## Step 3 — Run the Bot Locally

```bash
python bot.py
```

You should see:
```
✅  Logged in as President Log Bot#1234  (ID: 123456789)
✅  Synced 1 slash command(s)
────────────────────────────────────────
Bot is running! Use /president log in Discord.
```

> **Note:** The first time you sync slash commands it can take up to 1 hour to appear on Discord. Running it on a test server (guild) shows them instantly — see the advanced section below.

---

## Step 4 — Hosting (so it runs 24/7)

Running `python bot.py` on your PC only keeps the bot online while the PC is on. For a permanent host, use one of the options below.

---

### Option A: Railway.app ⭐ (Recommended — Free)

Railway gives you free cloud hosting with no credit card needed.

1. Create a free account at [railway.app](https://railway.app)
2. Click **New Project → Deploy from GitHub repo**
3. Push your bot files to a GitHub repo first:
   ```bash
   git init
   git add .
   git commit -m "Initial bot"
   git remote add origin https://github.com/YOUR_USERNAME/president-bot.git
   git push -u origin main
   ```
4. Back in Railway, select your repo and click **Deploy**
5. Click **Variables** → **New Variable** and add:
   - Key: `DISCORD_TOKEN`
   - Value: *(your bot token)*
6. Railway will automatically build and run your bot

> ✅ Free plan gives you 500 hours/month — enough for most use cases.

---

### Option B: Replit (Free, Easy)

1. Go to [replit.com](https://replit.com) and create an account
2. Create a new **Python** Repl
3. Upload your `bot.py` and `requirements.txt`
4. Click the **Secrets** tab (lock icon) and add:
   - Key: `DISCORD_TOKEN`, Value: your token
5. In `bot.py`, change the token loading to:
   ```python
   import os
   TOKEN = os.environ.get("DISCORD_TOKEN")
   ```
   *(already done in the provided code via dotenv)*
6. Click **Run**

> ⚠️ Free Replit bots sleep after 30 minutes of inactivity. Use [UptimeRobot](https://uptimerobot.com) to ping it every 5 minutes to keep it awake, or upgrade to a paid plan.

---

### Option C: Your own VPS / Server

If you have a Linux VPS (e.g. Hetzner, DigitalOcean):

```bash
# Install Python
sudo apt update && sudo apt install python3 python3-pip -y

# Copy your files, then install dependencies
pip3 install -r requirements.txt

# Run with screen so it stays alive after you close SSH
screen -S presidentbot
python3 bot.py
# Press Ctrl+A then D to detach
```

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `/president log @potus @vpotus` | Start a new President Log |

### Buttons on the embed

| Button | What it does |
|--------|-------------|
| 💀 POTUS died | -1 life · 2-minute cooldown |
| 🚪 POTUS left | VPOTUS → POTUS, VPOTUS = None |
| 🏳️ VPOTUS & POTUS left | Civilians win |
| 🎉 PRTY over | Presidency wins |

---

## Notes

- **Log number** persists across bot restarts (saved in `president_data.json`)
- **Buttons stop working** after a bot restart if the message was sent before the restart — this is a Discord limitation for non-registered persistent views. Just use `/president log` again to start a new one.
- **Lives** always start at 3 for each new log entry
- The **5-minute cooldown** is global — if anyone uses the command, everyone has to wait 5 minutes for a new log. Buttons on existing logs always work.
- The `vpotus` option is **optional** — you can run `/president log @user` without a VPOTUS

---

## File Structure

```
president_bot/
├── bot.py               ← Main bot code
├── requirements.txt     ← Python dependencies
├── .env                 ← Your secret token (create from .env.example)
├── .env.example         ← Template for .env
├── president_data.json  ← Auto-created, stores log number
└── README.md            ← This file
```
