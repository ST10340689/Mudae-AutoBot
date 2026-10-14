# Mudae AutoRoll, AutoClaim & AutoReact (2025/2026 Enhanced Edition)

An intelligent, fully automated self-bot for the Mudae Discord Bot. Automatically rolls, claims desired characters/series, collects high-tier Kakeras & Ourospheres every hour, persists claim cooldowns across system restarts, and operates with randomized anti-detection jitter.

Uses Discord Slash Commands natively (`/wx`, `/wa`, etc.) to benefit from Mudae's built-in **10% Kakera value slash boost**.

---

## ✨ Features

### 🎲 Smart Rolling Engine
- **Discord Slash Commands**: Natively uses slash commands (`/wx`, `/wa`, `/wg`, `/mx`, `/ma`, `/mg`, `/hx`, `/ha`, `/hg`).
- **Hourly Scheduler**: Runs automatically every hour at a configurable minute (e.g. XX:39).
- **Anti-Bot Jitter**: Randomized delay variation between rolls to simulate human pacing and prevent rate limits.
- **Roll Limit Detection**: Automatically detects when your rolls are exhausted (`⏳`) and gracefully finishes the session.

### 💖 Precision Auto-Claiming
- **Strict Word-for-Word Matching**: Exact whole-word matching prevents false positives (e.g., `Durandal` will never claim `Durandal (Uma)` from Umamusume, and `Titan (to)` won't claim `Titan Altera`).
- **Wishlist Characters & Series**: Target specific characters (`desiredCharacters`) or entire franchises (`desiredSeries`).
- **High-Value Threshold Claiming**: Automatically claims any character worth over a specified kakera value (`minPowerToClaim`).
- **Emergency Auto-`$rt` on Wishlist**: If a wishlist character appears while your normal claim is on cooldown, the bot instantly fires `$rt` to reset your claim and secure the card.
- **Persistent Cooldown Tracking**: Cooldowns are stored in `bot_state.json`. If the bot or computer restarts, it remembers exact claim and `$rt` availability without losing progress.
- **Automatic `$tu` Calibration**: Sends `$tu` on startup and hourly to sync timers directly with Mudae's server clock.

### 🔮 Kakera & Ourosphere Auto-Reaction
- **Full Ourosphere Support**: Reacts to all sphere types (`spP`, `spR`, `spO`, `spY`, `spG`, `spT`, `spB`, `spL`, `spD`, `spM`, `spW`, `spC`).
- **Perk 8 Halved Power (`⚡/2`) & Double Spheres (`:sp: :sp:`) Auto-Clicker**:
  - Automatically identifies cards with **halved kakera power cost (`⚡/2`)** and **double sphere drops (`:sp: :sp:`)**.
  - Automatically overrides color restrictions and clicks **ALL** kakera buttons on these cards to maximize sphere earnings from Perk 5!
- **Prioritized Clicking**: Free claims (`spP`, `kakeraP`) and sphere buttons are clicked first to conserve kakera power.

### 🖥️ Modern Configuration UI (`ConfigUI.py`)
- Clean, tabbed graphical interface built with Tkinter.
- Human-friendly color names for both Kakera (Purple, Red, Orange, Yellow, etc.) and Ourospheres.
- Quick-selection buttons (`Select All Kakera`, `Select All Spheres`, `Select All`, `Select None`).
- Live settings validation and conflict prevention.

---

## 📁 Project Structure

```
├── Bot.py               # Main launcher, hourly scheduler & terminal dashboard
├── ConfigUI.py          # Graphical configuration editor
├── Function.py          # Discord interaction client, card parser & rolling engine
├── Vars.py              # Configuration manager, environment resolver & validation
├── requirements.txt     # Python package dependencies
├── settings.example.json# Template settings file
├── .env.example         # Template environment variables file
└── .gitignore           # Prevents committing tokens, state, or private wishlists
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python **3.9** or higher installed ([python.org](https://www.python.org/downloads/)).
- Git installed (optional, for cloning).

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/your-username/mudae-autobot.git
cd mudae-autobot
pip install -r requirements.txt
```

### 3. Configuration
Launch the graphical configuration editor:
```bash
python ConfigUI.py
```
1. **Account Tab**: Enter your Discord User Token, Channel ID, and Server ID.
2. **Rolling Tab**: Choose your roll command (`wx`), roll minute, delay, and daily bonuses (`$p`, `$dk`, `$daily`).
3. **Auto-Claim Tab**: Enter your target characters, series, minimum kakera threshold, and set your `$rt` cooldown (e.g. `5.0h` if you have the -15h kakera perk, or `20.0h` default).
4. **Kakera & Spheres Tab**: Select which kakera colors and ourospheres to react to. Keep **Auto-click ALL kakera on Perk 8 cards** enabled for maximum spheres.
5. Press **Save** (`Ctrl+S`).

*(Alternative: You can copy `settings.example.json` to `settings.json` or copy `.env.example` to `.env` and fill in your details manually).*

### 4. Run the Bot
Start the bot:
```bash
python Bot.py
```
The terminal dashboard will display your active configuration and begin rolling immediately (if `runOnStartup` is enabled) or wait for your scheduled minute.

---

## 📊 Terminal Logging Legend

- `🤍` Unclaimed character card rolled
- `❤️` Already claimed character card
- `✨` Auto-Claim triggered (wishlist character, series, or high value)
- `🔄` `$rt` reset timer used to claim a wishlist character
- `💎` Kakera button reacted / clicked
- `🔮` Ourosphere button clicked
- `⚡` Perk 8 bonus click (`⚡/2` halved power or `:sp: :sp:` double spheres)
- `⏳` Hourly roll limit reached

---

## 🔒 Security Best Practices

> [!CAUTION]
> **Never commit or share your Discord User Token!**
> Anyone with your token has full access to your Discord account.
> - `settings.json`, `.env`, and `bot_state.json` are automatically included in `.gitignore` to prevent accidental exposure.
> - Keep `settings.json` private on your local machine.

---

## ⚖️ Disclaimer

This project is an educational automation tool. Automated interaction with user accounts may violate Discord's Terms of Service (Self-Bot policy). Use responsibly and at your own risk.
