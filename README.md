# Mudae Automation Tool

An automation tool for the Mudae Discord bot. Automates rolling via native Discord Slash Commands, claims targeted characters and series, reacts to configured Kakera and Ourospheres, maintains persistent claim cooldowns across system restarts, and operates with randomized anti-detection delays.

Uses Discord Slash Commands natively (`/wx`, `/wa`, etc.) to benefit from Mudae's built-in 10% Kakera value slash bonus.

---

## Features

### Rolling Engine
- **Discord Slash Commands**: Natively executes slash commands (`/wx`, `/wa`, `/wg`, `/mx`, `/ma`, `/mg`, `/hx`, `/ha`, `/hg`).
- **Hourly Scheduler**: Runs automatically every hour at a configurable minute (e.g., XX:39).
- **Anti-Detection Jitter**: Applies randomized delay variations between rolls to simulate human pacing and prevent rate limits.
- **Roll Limit Detection**: Detects roll exhaustion messages and gracefully concludes the session.

### Auto-Claiming
- **Strict Word Matching**: Word-boundary matching prevents false positive claims on substring matches.
- **Wishlist Characters and Series**: Target specific character names (`desiredCharacters`) or entire franchises (`desiredSeries`).
- **High-Value Threshold Claiming**: Automatically claims any character exceeding a specified kakera value (`minPowerToClaim`).
- **Automatic $rt on Wishlist**: If a wishlist character appears while your standard claim is on cooldown, the tool checks whether `$rt` is available and fires `$rt` immediately to claim the card.
- **Persistent Cooldown Tracking**: Cooldown states are stored in `bot_state.json`. If the program or system restarts, claim and `$rt` availability timestamps are retained.
- **Automatic $tu Calibration**: Issues `$tu` on startup and hourly to synchronize timers and kakera power directly with Mudae's server clock.

### Kakera and Ourosphere Reaction
- **Ourosphere Support**: Reacts to all sphere types (`spP`, `spR`, `spO`, `spY`, `spG`, `spT`, `spB`, `spL`, `spD`, `spM`, `spW`, `spC`).
- **Perk 8 Halved Power and Double Spheres**:
  - Detects cards with halved kakera power cost (`⚡/2`) and double sphere drops (`:sp: :sp:`).
  - Overrides standard color restrictions and clicks all available kakera buttons on these cards to maximize sphere yield.
- **Prioritized Clicking**: Free claims and sphere buttons are prioritized to optimize kakera power consumption.

### Dynamic Daily Kakera ($dk) Power Management
- Automatically checks current kakera power via `$tu` before executing `$dk`.
- Only sends `$dk` if current power is strictly below the configured threshold (default: 15%), preventing wasted power replenishment.

### Configuration UI
- Graphical interface built with Tkinter (`ConfigUI.py`).
- Plain-text color names for Kakera and Ourosphere selectors.
- Bulk selection controls (All Kakera, All Spheres, Select All, Clear).
- Settings validation and environment variable override indicators.

---

## Project Structure

```
├── Bot.py               # Main launcher, hourly scheduler, and console dashboard
├── ConfigUI.py          # Graphical configuration editor
├── Function.py          # Discord API client, card parser, and rolling engine
├── Vars.py              # Configuration manager, environment resolver, and validation
├── requirements.txt     # Python package dependencies
├── settings.example.json# Template configuration file
├── .env.example         # Template environment variables file
└── .gitignore           # Prevents committing tokens, state, or private configuration
```

---

## Getting Started

### 1. Prerequisites
- Python 3.9 or higher ([python.org](https://www.python.org/downloads/)).
- Git.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/ST10340689/Mudae-AutoBot.git
cd Mudae-AutoBot
pip install -r requirements.txt
```

### 3. Configuration
Launch the configuration editor:
```bash
python ConfigUI.py
```
1. **Account**: Enter your Discord User Token, Channel ID, and Server ID.
2. **Rolling**: Configure your roll command (`wx`), scheduled roll minute, roll delay, and bonus command toggles (`$p`, `$dk`, `$daily`).
3. **Auto-Claim**: Define desired characters, desired series, minimum kakera threshold, and set your base `$rt` cooldown (e.g., `5.0h` with the -15h kakera perk, or `20.0h` default).
4. **Kakera & Spheres**: Select target kakera colors and ourospheres. Keep "Auto-click all kakera on Perk 8 cards" enabled if applicable.
5. Save settings (`Ctrl+S`).

Configuration can alternatively be supplied via `settings.json` or `.env` using the provided templates (`settings.example.json`, `.env.example`).

### 4. Running the Tool
Start the runner:
```bash
python Bot.py
```
The console will display active configuration settings, synchronize timers via `$tu`, and begin rolling either immediately (if `runOnStartup` is enabled) or at the next scheduled roll minute.

---

## Console Logging Legend

- `[UNCLAIMED]` : Unclaimed character card rolled
- `[CLAIMED]`   : Already claimed character card rolled
- `[AUTO-CLAIM]`: Auto-claim triggered (wishlist character, series, or high value)
- `[RT-CLAIM]`  : `$rt` reset timer used to claim a wishlist character
- `[KAKERA]`    : Kakera button clicked
- `[SPHERE]`    : Ourosphere button clicked
- `[PERK-8]`    : Perk 8 bonus reaction executed (halved power or double spheres)
- `[ROLL-LIMIT]`: Hourly roll limit reached
- `[INFO]`      : Status, timer calibration, or power check notification
- `[SUCCESS]`   : Successful claim or action execution
- `[WARNING]`   : Cooldown active or action skipped
- `[ERROR]`     : Request failure or parsing issue

---

## Security and Token Safety

- Never commit or publish your Discord User Token.
- `settings.json`, `.env`, and `bot_state.json` are listed in `.gitignore` to prevent private credentials and local states from being committed to version control.
- Ensure all private configuration files remain on your local machine only.

---

## Disclaimer

This software is an automation script created for educational purposes. Automated interaction with user accounts may violate Discord's Terms of Service (Self-Bot policy). Use responsibly and at your own risk.
