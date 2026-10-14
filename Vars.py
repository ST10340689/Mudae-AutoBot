"""
Vars.py - Configuration settings for Mudae AutoRoll, AutoClaim, and AutoReact Bot.

Settings are resolved in this order (later sources win):
  1. DEFAULTS defined below
  2. settings.json (written by the settings UI: `python ConfigUI.py`)
  3. Environment variables / .env file
"""

import os
import json
import copy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
ENV_FILE = os.path.join(BASE_DIR, '.env')


# ---------------------------------------------------------------------------
# Helper: Load .env file if present (without requiring external dependencies)
# ---------------------------------------------------------------------------
def _load_dotenv():
    if os.path.isfile(ENV_FILE):
        try:
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

_load_dotenv()


# Known Kakera and Ourosphere button names
KNOWN_KAKERAS = [
    'kakera', 'kakeraP', 'kakeraB', 'kakeraT', 'kakeraG', 'kakeraY',
    'kakeraO', 'kakeraR', 'kakeraW', 'kakeraL', 'kakeraC', 'kakeraD',
]
KNOWN_SPHERES = [
    'spP', 'spR', 'spO', 'spY', 'spG', 'spT', 'spB', 'spL', 'spD', 'spM', 'spW', 'spC',
]
ALL_KNOWN_BUTTONS = KNOWN_KAKERAS + KNOWN_SPHERES


# ---------------------------------------------------------------------------
# Default values (used when neither settings.json nor env vars provide a value)
# ---------------------------------------------------------------------------
DEFAULTS = {
    # --- Mandatory Discord Credentials & Channel Settings ---
    # Your Discord User Token (Keep this secret!)
    'token': '',
    # ID of the Discord channel where the Mudae bot rolls
    'channelId': '',
    # ID of the Discord server (guild) containing the channel
    'serverId': '',

    # --- Rolling Configuration ---
    # Roll command to trigger: 'wx', 'wa', 'wg', 'ma', 'mg', 'mx', 'hx', 'ha', 'hg'
    'rollCommand': 'wx',
    # Minute of the hour when the bot rolls (00 to 59). e.g. '39' rolls at XX:39 every hour
    'repeatMinute': '39',
    # Whether to run a roll session immediately when Bot.py starts up
    'runOnStartup': True,
    # Base delay (in seconds) between rolls (recommended: 1.8 to 3.0)
    'rollDelay': 2.0,
    # Random jitter (in seconds) added/subtracted to rollDelay to simulate human timing
    'randomJitter': 0.5,
    # Safety ceiling: maximum rolls allowed in a single hourly session
    'maxRollsPerSession': 50,

    # --- AutoClaim Targets & Preferences ---
    # Case-insensitive list of series you want to automatically claim
    'desiredSeries': [],
    # Case-insensitive list of specific character names you want to claim
    'desiredCharacters': [],
    # Minimum kakera power to claim (0 to disable)
    'minPowerToClaim': 0,
    # Claim ANY unclaimed card rolled, regardless of series or power
    'claimAllUnclaimed': False,
    # Emoji used to react and claim characters (e.g. '💖', '❤️', '🐿️', '💍')
    'claimEmoji': '💖',

    # --- Kakera & Ourosphere AutoReact Preferences ---
    # List of kakera types and ourosphere button emojis to automatically react / click
    'desiredKakeras': [
        'kakeraP', 'kakeraC', 'kakeraR', 'kakeraD', 'kakeraW', 'kakeraL',
        'kakeraY', 'kakeraO', 'kakeraG', 'kakeraB', 'kakeraT', 'kakera',
        'spP', 'spR', 'spO', 'spY', 'spG', 'spT', 'spB', 'spL', 'spD', 'spM', 'spW', 'spC',
    ],

    # --- Bonus & Daily Automation Features ---
    # Whether to roll Pokemon slot ($p) after completing the roll session
    'pokeRoll': False,
    # Whether to claim daily kakera ($dk)
    'dailyKakera': False,
    # Whether to claim daily rolls/votes ($daily)
    'dailyRoll': False,

    # --- Reset Timer ($rt) & Claim Cooldown Timing ---
    # Cooldown of your $rt command in hours (default is 20h; with -15h kakera loot perk, defaults to 5.0h)
    'rtCooldownHours': 5.0,
    # Automatically use $rt if a desired character appears while your regular claim is on cooldown
    'autoRtOnWishlist': True,
    # Automatically send $tu on startup to synchronize exact claim and $rt cooldown timers
    'checkTuOnStartup': True,
    # Regular claim cooldown in hours (default: 3.0)
    'claimCooldownHours': 3.0,
    # Automatically click all kakera and sphere buttons on cards with Perk 8 bonus (⚡/2 halved power & :sp: :sp: double spheres)
    'autoPerkBonusKakera': True,
}

# Setting name -> environment variable that overrides it (scalar settings only)
ENV_VARS = {
    'token': 'DISCORD_TOKEN',
    'channelId': 'CHANNEL_ID',
    'serverId': 'SERVER_ID',
    'rollCommand': 'ROLL_COMMAND',
    'repeatMinute': 'REPEAT_MINUTE',
    'runOnStartup': 'RUN_ON_STARTUP',
    'rollDelay': 'ROLL_DELAY',
    'randomJitter': 'RANDOM_JITTER',
    'maxRollsPerSession': 'MAX_ROLLS_PER_SESSION',
    'minPowerToClaim': 'MIN_POWER_TO_CLAIM',
    'claimAllUnclaimed': 'CLAIM_ALL_UNCLAIMED',
    'claimEmoji': 'CLAIM_EMOJI',
    'pokeRoll': 'POKE_ROLL',
    'dailyKakera': 'DAILY_KAKERA',
    'dailyRoll': 'DAILY_ROLL',
    'autoPerkBonusKakera': 'AUTO_PERK_BONUS_KAKERA',
    'rtCooldownHours': 'RT_COOLDOWN_HOURS',
    'autoRtOnWishlist': 'AUTO_RT_ON_WISHLIST',
    'checkTuOnStartup': 'CHECK_TU_ON_STARTUP',
    'claimCooldownHours': 'CLAIM_COOLDOWN_HOURS',
}

VALID_ROLL_COMMANDS = ['wx', 'wa', 'wg', 'mx', 'ma', 'mg', 'hx', 'ha', 'hg', 'm', 'w', 'h', 's', 'p']


# ---------------------------------------------------------------------------
# Loading / saving helpers (also used by ConfigUI.py)
# ---------------------------------------------------------------------------
def coerce_setting(key: str, value):
    """Converts a raw value (from JSON, env var or UI) to the type of DEFAULTS[key]."""
    default = DEFAULTS[key]
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    if isinstance(default, int):
        return int(str(value).strip())
    if isinstance(default, float):
        return float(str(value).strip())
    if isinstance(default, list):
        if isinstance(value, str):
            value = value.split(',')
        return [str(v).strip() for v in value if str(v).strip()]
    return str(value).strip()


def load_settings_file(path: str = None) -> dict:
    """Returns the raw contents of settings.json, or {} if missing/invalid."""
    path = path or SETTINGS_FILE
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as e:
        print(f"[Vars] Warning: could not read {path}: {e}")
        return {}


def get_file_settings(path: str = None) -> dict:
    """DEFAULTS merged with settings.json (environment overrides NOT applied)."""
    merged = copy.deepcopy(DEFAULTS)
    for key, value in load_settings_file(path).items():
        if key not in DEFAULTS:
            continue
        try:
            merged[key] = coerce_setting(key, value)
        except (TypeError, ValueError):
            print(f"[Vars] Warning: invalid value for '{key}' in settings.json, using default.")
    return merged


def get_env_overrides() -> dict:
    """Returns {setting_name: raw_value} for settings overridden by env vars / .env."""
    return {key: os.environ[env] for key, env in ENV_VARS.items() if os.environ.get(env, '') != ''}


def save_settings(settings: dict, path: str = None):
    """Writes the given settings to settings.json (atomically)."""
    path = path or SETTINGS_FILE
    clean = {key: coerce_setting(key, settings[key]) for key in DEFAULTS if key in settings}
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def resolve_settings() -> dict:
    """Final effective settings: DEFAULTS < settings.json < environment variables."""
    settings = get_file_settings()
    for key, raw in get_env_overrides().items():
        try:
            settings[key] = coerce_setting(key, raw)
        except (TypeError, ValueError):
            print(f"[Vars] Warning: invalid value for env var {ENV_VARS[key]}, ignoring.")
    return settings


# ---------------------------------------------------------------------------
# Effective module-level settings (read by Bot.py and Function.py)
# ---------------------------------------------------------------------------
_settings = resolve_settings()

token: str = _settings['token']
channelId: str = _settings['channelId']
serverId: str = _settings['serverId']

rollCommand: str = _settings['rollCommand']
repeatMinute: str = _settings['repeatMinute']
runOnStartup: bool = _settings['runOnStartup']
rollDelay: float = _settings['rollDelay']
randomJitter: float = _settings['randomJitter']
maxRollsPerSession: int = _settings['maxRollsPerSession']

desiredSeries: list = _settings['desiredSeries']
desiredCharacters: list = _settings['desiredCharacters']
minPowerToClaim: int = _settings['minPowerToClaim']
claimAllUnclaimed: bool = _settings['claimAllUnclaimed']
claimEmoji: str = _settings['claimEmoji']

desiredKakeras: list = _settings['desiredKakeras']

pokeRoll: bool = _settings['pokeRoll']
dailyKakera: bool = _settings['dailyKakera']
dailyRoll: bool = _settings['dailyRoll']

rtCooldownHours: float = float(_settings['rtCooldownHours'])
autoRtOnWishlist: bool = _settings['autoRtOnWishlist']
checkTuOnStartup: bool = _settings['checkTuOnStartup']
claimCooldownHours: float = float(_settings['claimCooldownHours'])
autoPerkBonusKakera: bool = _settings['autoPerkBonusKakera']

# Discord REST API Version
discordApiVersion: str = 'v10'


# ---------------------------------------------------------------------------
# Validation & Utility Helpers
# ---------------------------------------------------------------------------
def get_masked_token() -> str:
    """Returns a masked version of the token for secure logging."""
    if not token or len(token) < 12:
        return '***MISSING_OR_INVALID_TOKEN***'
    return f"{token[:6]}...{token[-4:]}"


def format_schedule_minute(minute=None) -> str:
    """Formats repeatMinute into a valid ':MM' string for schedule library."""
    min_str = str(repeatMinute if minute is None else minute).strip().lstrip(':')
    try:
        val = int(min_str)
        if 0 <= val <= 59:
            return f":{val:02d}"
    except ValueError:
        pass
    return ":00"


def validate_settings(s: dict) -> list:
    """Validates a settings dict. Returns a list of human-readable issues (empty = OK)."""
    issues = []
    tok = s.get('token', '')
    if not tok or tok == 'YOUR_DISCORD_TOKEN_HERE':
        issues.append("Discord token is empty or set to placeholder.")
    elif len(tok.split('.')) != 3:
        issues.append("Discord token format appears unusual (expected 3 dot-separated parts).")

    for key in ('channelId', 'serverId'):
        val = str(s.get(key, ''))
        if not val.isdigit():
            issues.append(f"Invalid {key}: '{val}'. Must be a numeric Discord ID.")

    roll = str(s.get('rollCommand', '')).lower()
    if roll not in VALID_ROLL_COMMANDS:
        issues.append(f"Unknown rollCommand: '{roll}'. Expected one of {VALID_ROLL_COMMANDS}.")

    try:
        m = int(str(s.get('repeatMinute', '')).strip().lstrip(':'))
        if not (0 <= m <= 59):
            issues.append(f"repeatMinute '{s.get('repeatMinute')}' out of bounds (0-59).")
    except ValueError:
        issues.append(f"Invalid repeatMinute format: '{s.get('repeatMinute')}'.")

    if s.get('rollDelay', 1) <= 0:
        issues.append("rollDelay must be greater than 0.")
    if s.get('randomJitter', 0) < 0:
        issues.append("randomJitter cannot be negative.")
    if s.get('maxRollsPerSession', 1) < 1:
        issues.append("maxRollsPerSession must be at least 1.")
    if s.get('minPowerToClaim', 0) < 0:
        issues.append("minPowerToClaim cannot be negative.")
    if not str(s.get('claimEmoji', '')).strip():
        issues.append("claimEmoji cannot be empty.")
    return issues


def validate_config() -> tuple:
    """
    Validates the currently loaded configuration.
    Returns (is_valid: bool, issues: list[str]).
    """
    issues = validate_settings({key: globals()[key] for key in DEFAULTS})
    return (len(issues) == 0, issues)
