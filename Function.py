"""
Function.py - Core rolling, claiming, and reaction engine for Mudae Bot.
Handles Discord API interactions, slash commands, embed parsing, and automatic reactions.
"""

import os
import sys
import time
import json
import re
import random
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple

# Reconfigure stdout/stderr on Windows to ensure UTF-8 symbols render properly without charmap errors
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import requests
import discum
from discum.utils.slash import SlashCommander

try:
    import colorama
    from colorama import Fore, Style, Back
    colorama.init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    class DummyColor:
        def __getattr__(self, name):
            return ''
    Fore = DummyColor()
    Style = DummyColor()
    Back = DummyColor()

import Vars

# ---------------------------------------------------------------------------
# Constants, State Persistence & Backward-Compatibility Globals
# ---------------------------------------------------------------------------
BOT_ID = '432610292342587392'  # Mudae Discord Bot ID
API_VERSION = getattr(Vars, 'discordApiVersion', 'v10')
STATE_FILE = os.path.join(getattr(Vars, 'BASE_DIR', '.'), 'bot_state.json')


class StateManager:
    """Manages persistent bot state on disk (survives restarts)."""
    def __init__(self):
        self.state: Dict[str, Any] = {
            'last_rt_timestamp': 0.0,
            'last_claim_timestamp': 0.0,
            'last_tu_sync': 0.0,
            'claim_available': True,
            'claim_ready_at': 0.0,
            'rt_available': True,
            'rt_ready_at': 0.0,
            'kakera_power': None,
            'dk_available': None,
            'dk_ready_at': 0.0,
            'last_bonus_timestamps': {}
        }
        self.load()

    def load(self):
        if os.path.isfile(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.state.update(data)
            except Exception:
                pass

    def save(self):
        try:
            tmp = STATE_FILE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            os.replace(tmp, STATE_FILE)
        except Exception:
            pass

    def is_rt_ready(self) -> bool:
        if self.state.get('rt_available') is True:
            return True
        now = time.time()
        rt_ready_at = self.state.get('rt_ready_at', 0.0)
        if rt_ready_at > 0.0:
            if now >= rt_ready_at:
                self.state['rt_available'] = True
                return True
            return False
        last_rt = self.state.get('last_rt_timestamp', 0.0)
        if last_rt <= 0.0:
            return False
        cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
        if (now - last_rt) >= cooldown_secs:
            self.state['rt_available'] = True
            return True
        return False

    def record_rt_used(self):
        now = time.time()
        cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
        self.state['last_rt_timestamp'] = now
        self.state['rt_ready_at'] = now + cooldown_secs
        self.state['rt_available'] = False
        self.state['claim_available'] = True
        self.state['claim_ready_at'] = 0.0
        self.save()

    def is_claim_ready(self) -> bool:
        if self.state.get('claim_available') is True:
            return True
        now = time.time()
        claim_ready_at = self.state.get('claim_ready_at', 0.0)
        if claim_ready_at > 0.0:
            if now >= claim_ready_at:
                self.state['claim_available'] = True
                return True
            return False
        last_claim = self.state.get('last_claim_timestamp', 0.0)
        if last_claim <= 0.0:
            return False
        cooldown_secs = getattr(Vars, 'claimCooldownHours', 3.0) * 3600.0
        if (now - last_claim) >= cooldown_secs:
            self.state['claim_available'] = True
            return True
        return False

    def record_claim_used(self):
        now = time.time()
        cooldown_secs = getattr(Vars, 'claimCooldownHours', 3.0) * 3600.0
        self.state['last_claim_timestamp'] = now
        self.state['claim_ready_at'] = now + cooldown_secs
        self.state['claim_available'] = False
        self.save()

    def is_dk_ready(self) -> Optional[bool]:
        if self.state.get('dk_available') is True:
            return True
        dk_ready_at = self.state.get('dk_ready_at', 0.0)
        if dk_ready_at > 0.0:
            if time.time() >= dk_ready_at:
                self.state['dk_available'] = True
                return True
            return False
        return self.state.get('dk_available', None)

    def record_dk_used(self):
        now = time.time()
        self.state['dk_available'] = False
        self.state['dk_ready_at'] = now + 20.0 * 3600.0
        self.save()

    def get_rt_remaining_str(self) -> str:
        if self.is_rt_ready():
            return "READY"
        now = time.time()
        rt_ready_at = self.state.get('rt_ready_at', 0.0)
        if rt_ready_at > now:
            remaining = rt_ready_at - now
        else:
            last_rt = self.state.get('last_rt_timestamp', 0.0)
            cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
            remaining = cooldown_secs - (now - last_rt)
        if remaining <= 0:
            return "READY"
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        return f"{h}h {m:02d}m remaining"

    def get_dk_remaining_str(self) -> str:
        if self.is_dk_ready() is True:
            return "READY"
        now = time.time()
        dk_ready_at = self.state.get('dk_ready_at', 0.0)
        if dk_ready_at > now:
            remaining = dk_ready_at - now
            h = int(remaining // 3600)
            m = int((remaining % 3600) // 60)
            return f"{h}h {m:02d}m remaining"
        return "ON COOLDOWN"


# Preserve legacy globals for backwards compatibility
botID = BOT_ID
auth = {'authorization': Vars.token}
bot = None
url = f'https://discord.com/api/{API_VERSION}/channels/{Vars.channelId}/messages'


# ---------------------------------------------------------------------------
# Formatted Terminal Logger
# ---------------------------------------------------------------------------
class Logger:
    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%H:%M:%S", time.localtime())

    @staticmethod
    def info(msg: str):
        print(f"{Fore.CYAN}[{Logger._timestamp()}] [INFO] {msg}{Style.RESET_ALL}")

    @staticmethod
    def success(msg: str):
        print(f"{Fore.GREEN}[{Logger._timestamp()}] [SUCCESS] {msg}{Style.RESET_ALL}")

    @staticmethod
    def warn(msg: str):
        print(f"{Fore.YELLOW}[{Logger._timestamp()}] [WARNING] {msg}{Style.RESET_ALL}")

    @staticmethod
    def error(msg: str):
        print(f"{Fore.RED}[{Logger._timestamp()}] [ERROR] {msg}{Style.RESET_ALL}")

    @staticmethod
    def roll_unclaimed(index: int, power: int, name: str, series: str):
        p_str = f"{power:,}".rjust(7) if power > 0 else "      -"
        print(f"{Fore.WHITE}[{Logger._timestamp()}] #{index:<3} [UNCLAIMED] {Fore.CYAN}{p_str} kakera{Fore.WHITE} | {Fore.GREEN}{name}{Fore.WHITE} ({series}){Style.RESET_ALL}")

    @staticmethod
    def roll_claimed(index: int, power: int, name: str, series: str):
        p_str = f"{power:,}".rjust(7) if power > 0 else "      -"
        print(f"{Fore.LIGHTBLACK_EX}[{Logger._timestamp()}] #{index:<3} [CLAIMED]   {p_str} kakera | {name} ({series}){Style.RESET_ALL}")

    @staticmethod
    def claim_triggered(name: str, series: str, reason: str):
        print(f"{Fore.MAGENTA}{Style.BRIGHT}[{Logger._timestamp()}] [AUTO-CLAIM] -> {name} ({series}) [{reason}]{Style.RESET_ALL}")

    @staticmethod
    def kakera_reacted(emoji_name: str, card_name: str):
        print(f"{Fore.YELLOW}[{Logger._timestamp()}] [KAKERA] Reacted to {emoji_name} on {card_name}{Style.RESET_ALL}")


# ---------------------------------------------------------------------------
# Card Parser & Matcher (Pre-compiled Regexes & O(1) Target Lookup Cache)
# ---------------------------------------------------------------------------
class CardParser:
    _RE_CUSTOM_EMOJI = re.compile(r'<a?:\w+:\d+>')
    _RE_TEXT_EMOJI = re.compile(r':(?:female|male|transgender_symbol|gem|star|sparkles|\w+):')
    _RE_UNICODE_SYMBOLS = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27ff\u2300-\u23ff\u2b50\ufe0f\u200d]')
    _RE_SPACES = re.compile(r'\s+')
    _RE_PARENS = re.compile(r'[\(\[\{].*?[\)\]\}]')

    _RE_KAKERA_1 = re.compile(r'(?:\*\*([\d,]+)\*\*|([\d,]+))\s*(?:<a?:\w+:\d+>|:?kakera\b)', re.IGNORECASE)
    _RE_KAKERA_2 = re.compile(r'(?:<a?:\w+:\d+>|:?kakera\b)\s*(?:\*\*([\d,]+)\*\*|([\d,]+))', re.IGNORECASE)
    _RE_BOLD_NUM = re.compile(r'\*\*([\d,]+)\*\*')

    _RE_HALVED_POWER = re.compile(r'(?:⚡|\u26a1\ufe0f?|:zap:|<a?:\w*zap\w*:\d+>)\s*/\s*2')
    _RE_DOUBLE_SP = re.compile(r'(?:<a?:sp:\d+>|:sp:|🔴)\s*(?:<a?:sp:\d+>|:sp:|🔴)', re.IGNORECASE)
    _RE_SINGLE_SP = re.compile(r'<a?:sp:\d+>|:sp:', re.IGNORECASE)

    # Target cache state
    _cached_chars_source: Optional[tuple] = None
    _cached_chars_map: Dict[str, str] = {}
    _cached_series_source: Optional[tuple] = None
    _cached_series_entries: List[Tuple[str, str, str, Optional[re.Pattern]]] = []

    @classmethod
    def clean_series_name(cls, raw_series: str) -> str:
        """Removes Discord emojis, unicode pictographs, and clutter from series string."""
        if not raw_series:
            return "Unknown Series"
        cleaned = cls._RE_CUSTOM_EMOJI.sub('', raw_series)
        cleaned = cls._RE_TEXT_EMOJI.sub('', cleaned)
        cleaned = cls._RE_UNICODE_SYMBOLS.sub('', cleaned)
        cleaned = cls._RE_SPACES.sub(' ', cleaned).strip()
        return cleaned if cleaned else "Unknown Series"

    @classmethod
    def extract_kakera_power(cls, description: str) -> int:
        """Extracts kakera value from Mudae embed description (both bolded and unbolded)."""
        if not description:
            return 0

        m1 = cls._RE_KAKERA_1.search(description)
        if m1:
            try:
                val = m1.group(1) or m1.group(2)
                return int(val.replace(',', ''))
            except (ValueError, AttributeError):
                pass

        m2 = cls._RE_KAKERA_2.search(description)
        if m2:
            try:
                val = m2.group(1) or m2.group(2)
                return int(val.replace(',', ''))
            except (ValueError, AttributeError):
                pass

        all_bold = cls._RE_BOLD_NUM.findall(description)
        if all_bold:
            try:
                return int(all_bold[-1].replace(',', ''))
            except ValueError:
                pass

        return 0

    @classmethod
    def parse(cls, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parses a Discord message from Mudae into structured card details."""
        embeds = message.get('embeds', [])
        if not embeds:
            return None

        embed = embeds[0]
        card_name = embed.get('author', {}).get('name', 'Unknown')
        description = embed.get('description', '')

        lines = [line.strip() for line in description.split('\n') if line.strip()]
        raw_series = lines[0] if lines else ''
        card_series = cls.clean_series_name(raw_series)
        card_power = cls.extract_kakera_power(description)

        # Claim status is indicated by the presence of an avatar icon in the embed footer
        footer = embed.get('footer', {})
        is_claimed = bool(footer.get('icon_url'))

        # Check for Perk 8 Halved Power (⚡/2) and Double Spheres (:sp: :sp:)
        full_text = f"{description} {footer.get('text', '')} {message.get('content', '')}"
        is_halved_power = bool(cls._RE_HALVED_POWER.search(full_text))
        has_double_spheres = bool(
            cls._RE_DOUBLE_SP.search(full_text) or
            len(cls._RE_SINGLE_SP.findall(full_text)) >= 2
        )
        has_sphere_perk_bonus = is_halved_power or has_double_spheres
        sphere_bonus_reason = ""
        if is_halved_power and has_double_spheres:
            sphere_bonus_reason = "Halved Kakera Cost (⚡/2) & Double Spheres (:sp: :sp:)"
        elif is_halved_power:
            sphere_bonus_reason = "Halved Kakera Cost (⚡/2)"
        elif has_double_spheres:
            sphere_bonus_reason = "Double Spheres (:sp: :sp:)"

        # Extract interactive button components (for kakera and claim buttons)
        components = message.get('components', [])
        buttons = [
            comp
            for row in components
            for comp in row.get('components', [])
        ]

        return {
            'message_id': message.get('id'),
            'channel_id': message.get('channel_id'),
            'name': card_name,
            'series': card_series,
            'raw_series': raw_series,
            'power': card_power,
            'is_claimed': is_claimed,
            'buttons': buttons,
            'flags': message.get('flags', 0),
            'author_id': message.get('author', {}).get('id'),
            'is_halved_power': is_halved_power,
            'has_double_spheres': has_double_spheres,
            'has_sphere_perk_bonus': has_sphere_perk_bonus,
            'sphere_bonus_reason': sphere_bonus_reason,
        }

    @classmethod
    def normalize_text(cls, s: str) -> str:
        """Normalizes smart quotes, apostrophes, and spacing."""
        if not s:
            return ""
        s = s.replace("’", "'").replace("`", "'").replace("“", '"').replace("”", '"')
        s = cls._RE_SPACES.sub(' ', s)
        return s.strip().lower()

    @classmethod
    def match_character(cls, target: str, card_name: str) -> bool:
        """
        Matches desired character name against the rolled card name.
        Requires an exact match including any tags (e.g. 'Durandal' will not match 'Durandal (Uma)').
        """
        t = cls.normalize_text(target)
        c = cls.normalize_text(card_name)
        if not t or not c:
            return False
        return t == c

    @classmethod
    def match_series(cls, target: str, card_series: str) -> bool:
        """Precisely matches a desired series name against the rolled card series."""
        t = cls.normalize_text(target)
        c = cls.normalize_text(card_series)
        if not t or not c:
            return False

        if t == c:
            return True

        t_base = cls._RE_PARENS.sub('', t).strip()
        c_base = cls._RE_PARENS.sub('', c).strip()
        if t_base and c_base and t_base == c_base:
            return True

        if len(t) >= 3:
            if c.startswith(t):
                return True
            pattern = r'(?:\b|^)' + re.escape(t) + r'(?:\b|$)'
            if re.search(pattern, c):
                return True

        return False

    @classmethod
    def _ensure_caches(cls):
        """Rebuilds O(1) character lookup map and compiled series patterns if Vars changed."""
        raw_chars = tuple(getattr(Vars, 'desiredCharacters', []) or ())
        if raw_chars != cls._cached_chars_source:
            char_map = {}
            for target in raw_chars:
                if target and str(target).strip():
                    norm = cls.normalize_text(str(target))
                    if norm and norm not in char_map:
                        char_map[norm] = str(target).strip()
            cls._cached_chars_map = char_map
            cls._cached_chars_source = raw_chars

        raw_series = tuple(getattr(Vars, 'desiredSeries', []) or ())
        if raw_series != cls._cached_series_source:
            entries = []
            for target in raw_series:
                if target and str(target).strip():
                    t_raw = str(target).strip()
                    t_norm = cls.normalize_text(t_raw)
                    if not t_norm:
                        continue
                    t_base = cls._RE_PARENS.sub('', t_norm).strip()
                    pat = re.compile(r'(?:\b|^)' + re.escape(t_norm) + r'(?:\b|$)') if len(t_norm) >= 3 else None
                    entries.append((t_raw, t_norm, t_base, pat))
            cls._cached_series_entries = entries
            cls._cached_series_source = raw_series

    @classmethod
    def should_claim(cls, card_info: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determines if a card should be claimed based on configured criteria.
        Returns (should_claim: bool, match_reason: str).
        """
        if card_info['is_claimed']:
            return False, ""

        if getattr(Vars, 'claimAllUnclaimed', False):
            return True, "Claim All Unclaimed"

        cls._ensure_caches()

        # 1. O(1) Lookup for Desired Characters
        norm_name = cls.normalize_text(card_info['name'])
        if norm_name and norm_name in cls._cached_chars_map:
            return True, f"Desired Character: '{cls._cached_chars_map[norm_name]}'"

        # 2. Pre-compiled Lookup for Desired Series
        norm_series = cls.normalize_text(card_info['series'])
        if norm_series and cls._cached_series_entries:
            c_base = cls._RE_PARENS.sub('', norm_series).strip()
            for t_raw, t_norm, t_base, pat in cls._cached_series_entries:
                if t_norm == norm_series:
                    return True, f"Desired Series: '{t_raw}'"
                if t_base and c_base and t_base == c_base:
                    return True, f"Desired Series: '{t_raw}'"
                if pat is not None and (norm_series.startswith(t_norm) or pat.search(norm_series)):
                    return True, f"Desired Series: '{t_raw}'"

        # 3. Minimum Kakera Power Threshold
        min_power = getattr(Vars, 'minPowerToClaim', 0)
        if min_power > 0 and card_info['power'] >= min_power:
            return True, f"High Kakera: {card_info['power']} >= {min_power}"

        return False, ""


# ---------------------------------------------------------------------------
# Mudae Roller Engine
# ---------------------------------------------------------------------------
class MudaeRoller:
    # Mudae Kakera button value hierarchy (lower number = clicked first when power is limited)
    _BUTTON_PRIORITY_MAP = {
        'spp': 0, 'kakerap': 0,
        'spr': 1, 'spo': 1, 'spy': 1, 'spg': 1, 'spt': 1, 'spb': 1,
        'spl': 1, 'spd': 1, 'spm': 1, 'spw': 1, 'spc': 1,
        'kakerac': 2, 'kakeraw': 2, 'kakeral': 2,
        'kakerar': 3, 'kakerad': 3, 'kakerao': 3,
        'kakeray': 4, 'kakerag': 4, 'kakerat': 4, 'kakerab': 4,
        'kakera': 5,
    }

    _RE_TU_CLAIM_CD = re.compile(
        r'next\s+claim\s+reset\s+(?:is\s+)?in\s*(?:(\d+)\s*h(?:ours?)?)?\s*(?:(\d+)\s*min)?'
    )
    _RE_TU_RT_CD = re.compile(
        r'(?:next\s*\$rt\s*in|\$rt\s*(?:reset|cooldown)\s*in|cannot\s*use\s*\$rt[^\d\n]*)\s*(?:(\d+)\s*h(?:ours?)?)?\s*(?:(\d+)\s*min)?'
    )
    _RE_TU_POWER = re.compile(
        r'(?:kakera\s+)?power(?:\s+is\s+at)?\s*[:：]?\s*[*_]*(\d+)[*_]*%',
        re.IGNORECASE
    )
    _RE_TU_DK_CD = re.compile(
        r'(?:next\s*\$dk\s*in|\$dk\s*(?:reset|cooldown)\s*in|cannot\s*use\s*\$dk[^\d\n]*)\s*(?:(\d+)\s*h(?:ours?)?)?\s*(?:(\d+)\s*min)?'
    )

    def __init__(self):
        self.session = requests.Session()
        self.discum_client: Optional[discum.Client] = None
        self.cached_slash_command: Optional[Dict[str, Any]] = None
        self._cached_cmd_name: Optional[str] = None
        self._cached_token: Optional[str] = None
        self.api_version = getattr(Vars, 'discordApiVersion', 'v10')
        self.messages_url = ""
        self.state_mgr = StateManager()
        self.refresh_config()

    def refresh_config(self):
        """Synchronizes HTTP session headers and slash command cache with current Vars."""
        self.api_version = getattr(Vars, 'discordApiVersion', 'v10')
        self.messages_url = f"https://discord.com/api/{self.api_version}/channels/{Vars.channelId}/messages"
        self.session.headers.update({
            'Authorization': Vars.token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json'
        })
        if self._cached_token != Vars.token:
            self.discum_client = None
            self.cached_slash_command = None
            self._cached_token = Vars.token
        if self._cached_cmd_name != Vars.rollCommand:
            self.cached_slash_command = None
            self._cached_cmd_name = Vars.rollCommand

    def sync_timers_via_tu(self):
        """Sends $tu and synchronizes claim, $rt, kakera power, and $dk timers from Mudae's response."""
        Logger.info("Syncing cooldown timers with Mudae ($tu)...")
        try:
            r = self.session.post(self.messages_url, json={'content': '$tu'}, timeout=5)
            if r.status_code not in (200, 201):
                return
            time.sleep(2.0)
            messages = self.fetch_recent_messages(limit=5)
            mudae_msg = next((
                m for m in messages
                if m.get('author', {}).get('id') == BOT_ID and any(
                    k in (m.get('content', '') + ' ' + str(m.get('embeds', ''))).lower()
                    for k in ('claim', 'rolls', 'power', 'kakera', '$rt', '$dk')
                )
            ), None)
            if not mudae_msg:
                time.sleep(1.5)
                messages = self.fetch_recent_messages(limit=5)
                mudae_msg = next((
                    m for m in messages
                    if m.get('author', {}).get('id') == BOT_ID and any(
                        k in (m.get('content', '') + ' ' + str(m.get('embeds', ''))).lower()
                        for k in ('claim', 'rolls', 'power', 'kakera', '$rt', '$dk')
                    )
                ), None)
                if not mudae_msg:
                    Logger.warn("Did not receive a recognizable $tu response from Mudae.")
                    return

            content = mudae_msg.get('content', '')
            embeds = mudae_msg.get('embeds', [])
            embed_texts = []
            for e in embeds:
                embed_texts.append(e.get('title', ''))
                embed_texts.append(e.get('description', ''))
                for field in e.get('fields', []):
                    embed_texts.append(field.get('name', ''))
                    embed_texts.append(field.get('value', ''))
            full_text = (content + ' ' + ' '.join(t for t in embed_texts if t)).strip()
            full_text_lower = full_text.lower()
            clean_lower = re.sub(r'[*_`]', '', full_text_lower)
            now = time.time()

            # 1. Parse claim status & exact remaining reset timer
            if "can claim right now" in clean_lower or "claim is ready" in clean_lower:
                self.state_mgr.state['claim_available'] = True
                self.state_mgr.state['claim_ready_at'] = 0.0
                Logger.success("Claim status: READY")
            elif "can't claim right now" in clean_lower or "cannot claim" in clean_lower:
                self.state_mgr.state['claim_available'] = False
                claim_cd_match = self._RE_TU_CLAIM_CD.search(clean_lower)
                if claim_cd_match and (claim_cd_match.group(1) or claim_cd_match.group(2)):
                    ch = int(claim_cd_match.group(1) or 0)
                    cm = int(claim_cd_match.group(2) or 0)
                    rem_secs = ch * 3600 + cm * 60
                    cooldown_secs = getattr(Vars, 'claimCooldownHours', 3.0) * 3600.0
                    self.state_mgr.state['claim_ready_at'] = now + rem_secs
                    self.state_mgr.state['last_claim_timestamp'] = now - max(0.0, cooldown_secs - rem_secs)
                    Logger.info(f"Claim status: ON COOLDOWN ({ch}h {cm}m remaining)")
                else:
                    self.state_mgr.state['claim_ready_at'] = now + 1800.0
                    Logger.info("Claim status: ON COOLDOWN")

            # 2. Parse $rt status
            if any(p in clean_lower for p in ["$rt is available", "rt is available", "$rt is ready", "rt is ready", "can use $rt"]):
                self.state_mgr.state['rt_available'] = True
                self.state_mgr.state['rt_ready_at'] = 0.0
                self.state_mgr.state['last_rt_timestamp'] = 0.0
                Logger.success("$rt status: READY")
            else:
                rt_match = self._RE_TU_RT_CD.search(clean_lower)
                if rt_match and (rt_match.group(1) or rt_match.group(2)):
                    h = int(rt_match.group(1) or 0)
                    m = int(rt_match.group(2) or 0)
                    rem_secs = h * 3600 + m * 60
                    cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
                    self.state_mgr.state['rt_ready_at'] = now + rem_secs
                    self.state_mgr.state['last_rt_timestamp'] = now - max(0.0, cooldown_secs - rem_secs)
                    self.state_mgr.state['rt_available'] = False
                    Logger.info(f"$rt status: On cooldown ({h}h {m}m remaining)")

            # 3. Parse Kakera power percentage
            power_match = self._RE_TU_POWER.search(full_text)
            if power_match:
                try:
                    power_pct = int(power_match.group(1))
                    self.state_mgr.state['kakera_power'] = power_pct
                    Logger.info(f"Kakera power: {power_pct}%")
                except ValueError:
                    pass
            else:
                Logger.warn("Could not extract kakera power percentage from $tu response.")

            # 4. Parse $dk status
            dk_match = self._RE_TU_DK_CD.search(clean_lower)
            if dk_match and (dk_match.group(1) or dk_match.group(2)):
                dh = int(dk_match.group(1) or 0)
                dm = int(dk_match.group(2) or 0)
                rem_secs = dh * 3600 + dm * 60
                self.state_mgr.state['dk_available'] = False
                self.state_mgr.state['dk_ready_at'] = now + rem_secs
                Logger.info(f"$dk status: On cooldown ({dh}h {dm}m remaining)")
            elif any(p in clean_lower for p in ["$dk is available", "dk is available", "$dk is ready", "dk is ready", "can use $dk", "may use $dk"]):
                self.state_mgr.state['dk_available'] = True
                self.state_mgr.state['dk_ready_at'] = 0.0
                Logger.success("$dk status: READY")

            self.state_mgr.state['last_tu_sync'] = now
            self.state_mgr.save()
        except Exception as e:
            Logger.warn(f"Failed to sync $tu timers: {e}")

    def _get_discum_client(self) -> discum.Client:
        """Initializes and returns Discum client instance."""
        if self.discum_client is None:
            self.discum_client = discum.Client(token=Vars.token, log=False)
        return self.discum_client

    def get_slash_command_data(self) -> Optional[Dict[str, Any]]:
        """Retrieves and caches slash command metadata for the configured roll command."""
        if self.cached_slash_command is not None:
            return self.cached_slash_command

        client = self._get_discum_client()
        try:
            resp = client.getSlashCommands(BOT_ID)
            if resp.status_code == 200:
                commander = SlashCommander(resp.json())
                self.cached_slash_command = commander.get([Vars.rollCommand])
                self._cached_cmd_name = Vars.rollCommand
                return self.cached_slash_command
            else:
                Logger.error(f"Failed to fetch slash commands: HTTP {resp.status_code}")
        except Exception as e:
            Logger.error(f"Exception fetching slash commands: {e}")

        return None

    def trigger_roll(self) -> bool:
        """Fires the slash command to roll Mudae, with fallback to text command."""
        cmd_data = self.get_slash_command_data()
        if cmd_data:
            try:
                client = self._get_discum_client()
                client.triggerSlashCommand(BOT_ID, Vars.channelId, guildID=Vars.serverId, data=cmd_data)
                return True
            except Exception as e:
                Logger.warn(f"Slash command failed: {e}. Falling back to text command...")

        # Fallback to text command $wx (or configured roll command)
        try:
            r = self.session.post(self.messages_url, json={'content': f"${Vars.rollCommand}"}, timeout=5)
            if r.status_code in (200, 201):
                return True
            else:
                Logger.error(f"Fallback text roll returned HTTP {r.status_code}")
        except Exception as e:
            Logger.error(f"Failed to send fallback text roll: {e}")

        return False

    def fetch_recent_messages(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetches the latest messages from the roll channel with rate limit handling."""
        for _ in range(3):
            try:
                r = self.session.get(f"{self.messages_url}?limit={limit}", timeout=10)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 429:
                    retry_after = r.json().get('retry_after', 2.0)
                    Logger.warn(f"Rate limited by Discord. Waiting {retry_after:.1f}s...")
                    time.sleep(retry_after)
                else:
                    Logger.error(f"Discord API returned status {r.status_code}")
                    time.sleep(1.0)
            except requests.RequestException as e:
                Logger.error(f"Network error while fetching messages: {e}")
                time.sleep(1.0)
        return []

    def claim_card(self, card_info: Dict[str, Any]) -> bool:
        """Attempts to claim a card via interactive claim button (if present) and/or reaction emoji."""
        message_id = card_info['message_id']
        known_kakeras = {k.lower() for k in getattr(Vars, 'ALL_KNOWN_BUTTONS', [])}

        # 1. Check if Mudae attached a non-kakera interactive claim button (e.g. heart button)
        for btn in card_info.get('buttons', []):
            emoji_name = btn.get('emoji', {}).get('name', '')
            emoji_lower = emoji_name.lower()
            custom_id = btn.get('custom_id')
            if custom_id and not (
                emoji_lower in known_kakeras or
                emoji_lower.startswith('kakera') or
                emoji_lower.startswith('sp')
            ):
                try:
                    client = self._get_discum_client()
                    client.click(
                        card_info['author_id'] or BOT_ID,
                        channelID=Vars.channelId,
                        guildID=Vars.serverId,
                        messageID=message_id,
                        messageFlags=card_info.get('flags', 0),
                        data={'component_type': 2, 'custom_id': custom_id}
                    )
                    Logger.success(f"Claim button ({emoji_name or 'Button'}) clicked on {card_info['name']}!")
                    return True
                except Exception as e:
                    Logger.warn(f"Claim button click failed ({e}), falling back to reaction...")

        # 2. Place reaction emoji
        claim_emoji = getattr(Vars, 'claimEmoji', '💖')
        encoded_emoji = urllib.parse.quote(claim_emoji)
        reaction_url = f"https://discord.com/api/{self.api_version}/channels/{Vars.channelId}/messages/{message_id}/reactions/{encoded_emoji}/%40me"

        try:
            r = self.session.put(reaction_url, timeout=5)
            if r.status_code in (200, 204):
                Logger.success(f"Claim reaction ({claim_emoji}) placed successfully on {card_info['name']}!")
                return True
            elif r.status_code == 429:
                retry_after = r.json().get('retry_after', 1.5)
                Logger.warn(f"Rate limited on claim reaction. Waiting {retry_after:.1f}s...")
                time.sleep(retry_after)
                r2 = self.session.put(reaction_url, timeout=5)
                if r2.status_code in (200, 204):
                    Logger.success(f"Claim reaction ({claim_emoji}) placed successfully on {card_info['name']}!")
                    return True
                else:
                    Logger.warn(f"Claim reaction retry returned HTTP {r2.status_code}")
            else:
                Logger.warn(f"Claim reaction returned HTTP {r.status_code}")
        except Exception as e:
            Logger.error(f"Error placing claim reaction: {e}")

        return False

    @classmethod
    def _button_priority(cls, btn: Dict[str, Any]) -> int:
        name = btn.get('emoji', {}).get('name', '').lower()
        if name in cls._BUTTON_PRIORITY_MAP:
            return cls._BUTTON_PRIORITY_MAP[name]
        if name.startswith('sp'):
            return 1
        return 6

    def react_to_kakeras(self, card_info: Dict[str, Any]) -> int:
        """Clicks any matching kakera or ourosphere buttons on the card, ordered by Mudae value tier."""
        buttons = card_info.get('buttons', [])
        if not buttons:
            return 0

        desired_kakeras = {k.lower() for k in getattr(Vars, 'desiredKakeras', []) if k}
        auto_perk_bonus = getattr(Vars, 'autoPerkBonusKakera', True)
        is_bonus_card = auto_perk_bonus and card_info.get('has_sphere_perk_bonus', False)

        if is_bonus_card:
            reason = card_info.get('sphere_bonus_reason', 'Perk 8 Bonus')
            Logger.info(f"[PERK-8] Bonus active ({reason}) on {card_info['name']} -> clicking all kakera and sphere buttons")

        clicked = 0
        client = self._get_discum_client()
        sorted_buttons = sorted(buttons, key=self._button_priority)
        known_kakera_set = {k.lower() for k in getattr(Vars, 'KNOWN_KAKERAS', [])}
        known_sphere_set = {s.lower() for s in getattr(Vars, 'KNOWN_SPHERES', [])}

        for btn in sorted_buttons:
            emoji_name = btn.get('emoji', {}).get('name', '')
            if not emoji_name:
                continue

            emoji_lower = emoji_name.lower()
            should_click = False

            if emoji_lower in desired_kakeras:
                should_click = True
            elif is_bonus_card:
                if (
                    emoji_lower.startswith('kakera') or
                    emoji_lower.startswith('sp') or
                    'kakera' in emoji_lower or
                    'chaos' in emoji_lower or
                    emoji_lower in known_kakera_set or
                    emoji_lower in known_sphere_set
                ):
                    should_click = True

            if should_click:
                custom_id = btn.get('custom_id')
                if not custom_id:
                    continue
                try:
                    if emoji_lower.startswith('sp') or emoji_lower in known_sphere_set:
                        Logger.info(f"[SPHERE] Clicked {emoji_name} on {card_info['name']}")
                    elif is_bonus_card and emoji_lower not in desired_kakeras:
                        Logger.info(f"[PERK-8] Clicked {emoji_name} on {card_info['name']} [{card_info.get('sphere_bonus_reason')}]")
                    else:
                        Logger.kakera_reacted(emoji_name, card_info['name'])

                    client.click(
                        card_info['author_id'] or BOT_ID,
                        channelID=Vars.channelId,
                        guildID=Vars.serverId,
                        messageID=card_info['message_id'],
                        messageFlags=card_info.get('flags', 0),
                        data={'component_type': 2, 'custom_id': custom_id}
                    )
                    clicked += 1
                    time.sleep(0.4)  # Small pacing to avoid component click rate limits
                except Exception as e:
                    Logger.error(f"Failed to click button ({emoji_name}): {e}")

        return clicked

    def send_command(self, name: str, cmd: str) -> bool:
        """Sends a text command to the channel and logs the result."""
        Logger.info(f"Executing command: {name} ({cmd})...")
        try:
            r = self.session.post(self.messages_url, json={'content': cmd}, timeout=5)
            if r.status_code in (200, 201):
                Logger.success(f"{name} ({cmd}) sent successfully.")
                time.sleep(1.5)
                return True
            else:
                Logger.warn(f"{name} ({cmd}) returned HTTP {r.status_code}")
        except Exception as e:
            Logger.error(f"Error executing {name} ({cmd}): {e}")
        return False

    def run_bonus_commands(self, kakeras_hit: int = 0):
        """Executes configured daily and bonus commands ($p, $dk, $daily)."""
        if getattr(Vars, 'pokeRoll', False):
            self.send_command('Pokeslot', '$p')

        if getattr(Vars, 'dailyRoll', False):
            self.send_command('Daily Roll', '$daily')

        if getattr(Vars, 'dailyKakera', False):
            threshold = getattr(Vars, 'dkPowerThreshold', 15)

            # Avoid a redundant $tu call if $dk is already known to be on cooldown
            if self.state_mgr.is_dk_ready() is False:
                Logger.info(f"Daily Kakera ($dk) skipped: command is on cooldown ({self.state_mgr.get_dk_remaining_str()}).")
                return

            # Re-sync $tu only if kakera buttons were clicked during the session (spending power)
            # or if timers have not been synced recently
            since_last_sync = time.time() - self.state_mgr.state.get('last_tu_sync', 0.0)
            if kakeras_hit > 0 or since_last_sync > 600.0 or self.state_mgr.state.get('kakera_power') is None:
                self.sync_timers_via_tu()

            if self.state_mgr.is_dk_ready() is False:
                Logger.info(f"Daily Kakera ($dk) skipped: command is on cooldown ({self.state_mgr.get_dk_remaining_str()}).")
            else:
                current_power = self.state_mgr.state.get('kakera_power', None)
                if current_power is not None:
                    if current_power < threshold:
                        Logger.info(f"Kakera power is at {current_power}% (< {threshold}% threshold). Executing $dk...")
                        if self.send_command('Daily Kakera', '$dk'):
                            self.state_mgr.record_dk_used()
                    else:
                        Logger.info(f"Daily Kakera ($dk) skipped: power is at {current_power}% (threshold: < {threshold}%).")
                else:
                    Logger.warn("Daily Kakera ($dk) skipped: could not verify kakera power.")

    def run_roll_session(self):
        """Executes a full hourly roll session until rolls are exhausted or limits are reached."""
        # Hot-reload settings from disk in case the user saved changes in ConfigUI
        Vars.reload_settings()
        self.refresh_config()

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}")
        print(f"  MUDAE ROLL SESSION STARTED - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        roll_delay = getattr(Vars, 'rollDelay', 2.0)
        jitter = getattr(Vars, 'randomJitter', 0.5)
        max_rolls = getattr(Vars, 'maxRollsPerSession', 50)

        # Sync cooldown timers with $tu if enabled and needed
        if getattr(Vars, 'checkTuOnStartup', True):
            last_sync = self.state_mgr.state.get('last_tu_sync', 0.0)
            if last_sync == 0.0 or (time.time() - last_sync) > 3600.0:
                self.sync_timers_via_tu()

        # Pre-seed last_processed_msg_id so Roll #1 never re-processes an older channel message
        initial_msgs = self.fetch_recent_messages(limit=1)
        last_processed_msg_id = initial_msgs[0].get('id') if initial_msgs else None

        rolls_count = 0
        claimed_cards = []
        kakeras_hit = 0
        consecutive_misses = 0

        while rolls_count < max_rolls:
            # 1. Trigger the slash command
            if not self.trigger_roll():
                break

            # 2. Wait for Discord interaction & Mudae response with random jitter
            delay = max(0.8, roll_delay + random.uniform(-jitter, jitter))
            time.sleep(delay)

            # 3. Poll channel messages
            messages = self.fetch_recent_messages(limit=5)
            if not messages:
                consecutive_misses += 1
                if consecutive_misses >= 3:
                    Logger.warn("No response received after 3 attempts. Ending session.")
                    break
                continue

            # Find newest message from Mudae Bot
            mudae_msg = next((m for m in messages if m.get('author', {}).get('id') == BOT_ID), None)
            if not mudae_msg:
                consecutive_misses += 1
                if consecutive_misses >= 3:
                    Logger.warn("Mudae message not detected. Ending session.")
                    break
                continue

            # Avoid re-processing the exact same message
            if mudae_msg.get('id') == last_processed_msg_id:
                consecutive_misses += 1
                if consecutive_misses >= 4:
                    Logger.warn("No new Mudae messages received after multiple rolls. Ending session.")
                    break
                time.sleep(1.0)
                continue

            last_processed_msg_id = mudae_msg.get('id')
            consecutive_misses = 0

            # 4. Check if Mudae returned out-of-rolls text content instead of a card embed
            msg_content = mudae_msg.get('content', '')
            embeds = mudae_msg.get('embeds', [])

            if msg_content and not embeds:
                limit_indicators = (
                    'limited to', 'rolls left', 'until the reset', 'before the reset',
                    'cannot roll', "can't roll", '⏳', 'limité', '0 min', 'plus de rolls',
                    'roulette is limited', '0 rolls left', 'rolls left: 0', 'no rolls left',
                    'next rolls reset in'
                )
                if any(ind in msg_content.lower() for ind in limit_indicators):
                    clean_msg = msg_content.replace('\n', ' ').strip()
                    Logger.info(f"[ROLL-LIMIT] {clean_msg[:80]}")
                    break
                else:
                    Logger.info(f"Mudae message: {msg_content.strip()[:60]}")
                    time.sleep(1.0)
                    continue

            # 5. Parse character card embed
            card_info = CardParser.parse(mudae_msg)
            if not card_info:
                continue

            rolls_count += 1

            # Log card status
            if card_info['is_claimed']:
                Logger.roll_claimed(rolls_count, card_info['power'], card_info['name'], card_info['series'])
            else:
                Logger.roll_unclaimed(rolls_count, card_info['power'], card_info['name'], card_info['series'])

            # 6. Check and execute AutoClaim
            should_claim, reason = CardParser.should_claim(card_info)
            if should_claim:
                Logger.claim_triggered(card_info['name'], card_info['series'], reason)

                # Check claim timer; if on cooldown, check if $rt is ready
                claim_ready = self.state_mgr.is_claim_ready()
                if not claim_ready:
                    if getattr(Vars, 'autoRtOnWishlist', True) and self.state_mgr.is_rt_ready():
                        Logger.warn(f"Claim timer is on cooldown, but $rt is READY. Triggering $rt for {card_info['name']}...")
                        try:
                            r = self.session.post(self.messages_url, json={'content': '$rt'}, timeout=5)
                            if r.status_code in (200, 201):
                                time.sleep(1.0)
                                self.state_mgr.record_rt_used()
                                Logger.success("[RT-CLAIM] $rt executed successfully. Claim timer refreshed.")
                                claim_ready = True
                        except Exception as e:
                            Logger.error(f"Failed to execute $rt: {e}")
                    else:
                        Logger.warn(f"Claim is on cooldown (and $rt is {self.state_mgr.get_rt_remaining_str()}). Attempting claim anyway...")

                if self.claim_card(card_info):
                    self.state_mgr.record_claim_used()
                    claimed_cards.append(f"{card_info['name']} ({card_info['series']}) - {card_info['power']:,} kakera [{reason}]")

            # 7. Check and execute Kakera Button Reacts
            kakeras_hit += self.react_to_kakeras(card_info)

        # 8. Bonus & Daily Commands ($p, $dk, $daily) if configured
        self.run_bonus_commands(kakeras_hit=kakeras_hit)

        # 9. Print Session Summary
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"  ROLL SESSION SUMMARY")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"  Total Rolls Made   : {rolls_count}")
        print(f"  Kakeras Reacted    : {kakeras_hit}")
        print(f"  Cards Auto-Claimed : {len(claimed_cards)}")
        for claim in claimed_cards:
            print(f"   * {Fore.GREEN}{claim}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}\n{Style.RESET_ALL}")


# ---------------------------------------------------------------------------
# Global Singleton Instance & Backward Compatible Entry Point
# ---------------------------------------------------------------------------
_global_roller: Optional[MudaeRoller] = None


def get_roller() -> MudaeRoller:
    global _global_roller
    if _global_roller is None:
        _global_roller = MudaeRoller()
    return _global_roller


def simpleRoll():
    """Main rolling function invoked by schedule or manual call."""
    try:
        roller = get_roller()
        roller.run_roll_session()
    except Exception as e:
        Logger.error(f"Unexpected error in simpleRoll: {e}")