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

# Reconfigure stdout/stderr on Windows to ensure emojis and UTF-8 symbols render properly without charmap errors
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
            'rt_available': True,
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
        last_rt = self.state.get('last_rt_timestamp', 0.0)
        cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
        if (time.time() - last_rt) >= cooldown_secs:
            self.state['rt_available'] = True
            return True
        return False

    def record_rt_used(self):
        self.state['last_rt_timestamp'] = time.time()
        self.state['rt_available'] = False
        self.state['claim_available'] = True
        self.save()

    def is_claim_ready(self) -> bool:
        if self.state.get('claim_available') is True:
            return True
        last_claim = self.state.get('last_claim_timestamp', 0.0)
        cooldown_secs = getattr(Vars, 'claimCooldownHours', 3.0) * 3600.0
        if (time.time() - last_claim) >= cooldown_secs:
            self.state['claim_available'] = True
            return True
        return False

    def record_claim_used(self):
        self.state['last_claim_timestamp'] = time.time()
        self.state['claim_available'] = False
        self.save()

    def get_rt_remaining_str(self) -> str:
        if self.is_rt_ready():
            return "READY"
        last_rt = self.state.get('last_rt_timestamp', 0.0)
        cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
        remaining = cooldown_secs - (time.time() - last_rt)
        if remaining <= 0:
            return "READY"
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        return f"{h}h {m:02d}m remaining"

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
        print(f"{Fore.CYAN}[{Logger._timestamp()}] ℹ {msg}{Style.RESET_ALL}")

    @staticmethod
    def success(msg: str):
        print(f"{Fore.GREEN}[{Logger._timestamp()}] ✔ {msg}{Style.RESET_ALL}")

    @staticmethod
    def warn(msg: str):
        print(f"{Fore.YELLOW}[{Logger._timestamp()}] ⚠ {msg}{Style.RESET_ALL}")

    @staticmethod
    def error(msg: str):
        print(f"{Fore.RED}[{Logger._timestamp()}] ✖ {msg}{Style.RESET_ALL}")

    @staticmethod
    def roll_unclaimed(index: int, power: int, name: str, series: str):
        p_str = f"{power:,}".rjust(6) if power > 0 else "     -"
        print(f"{Fore.WHITE}[{Logger._timestamp()}] #{index:<2} 🤍 {Fore.CYAN}{p_str} kakera{Fore.WHITE} │ {Fore.GREEN}{name}{Fore.WHITE} ({series}){Style.RESET_ALL}")

    @staticmethod
    def roll_claimed(index: int, power: int, name: str, series: str):
        p_str = f"{power:,}".rjust(6) if power > 0 else "     -"
        print(f"{Fore.LIGHTBLACK_EX}[{Logger._timestamp()}] #{index:<2} ❤️ {p_str} kakera │ {name} ({series}){Style.RESET_ALL}")

    @staticmethod
    def claim_triggered(name: str, series: str, reason: str):
        print(f"{Fore.MAGENTA}{Style.BRIGHT}[{Logger._timestamp()}] ✨ AUTO-CLAIM TRIGGERED ➔ {name} ({series}) [{reason}]{Style.RESET_ALL}")

    @staticmethod
    def kakera_reacted(emoji_name: str, card_name: str):
        print(f"{Fore.YELLOW}[{Logger._timestamp()}] 💎 Reacted to {emoji_name} on {card_name}{Style.RESET_ALL}")


# ---------------------------------------------------------------------------
# Card Parser & Matcher
# ---------------------------------------------------------------------------
class CardParser:
    @staticmethod
    def clean_series_name(raw_series: str) -> str:
        """Removes Discord emojis, unicode pictographs, and clutter from series string."""
        if not raw_series:
            return "Unknown Series"
        # Remove Discord custom emojis <:name:id> or <a:name:id>
        cleaned = re.sub(r'<a?:\w+:\d+>', '', raw_series)
        # Remove Discord text emojis like :female:, :male:, :transgender_symbol:, etc.
        cleaned = re.sub(r':(?:female|male|transgender_symbol|gem|star|sparkles|\w+):', '', cleaned)
        # Remove common unicode symbols, emojis, stars, variation selectors
        cleaned = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27ff\u2300-\u23ff\u2b50\ufe0f\u200d]', '', cleaned)
        # Collapse extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else "Unknown Series"

    @staticmethod
    def extract_kakera_power(description: str) -> int:
        """Extracts kakera value from Mudae embed description (both bolded and unbolded)."""
        if not description:
            return 0
        
        # 1. Number adjacent to kakera emoji or text (with or without markdown **)
        # e.g. "18,013:kakera:", "**85**<:kakera:123>", "1,234 kakera", "· 90 kakera"
        m1 = re.search(r'(?:\*\*([\d,]+)\*\*|([\d,]+))\s*(?:<a?:\w+:\d+>|:?kakera\b)', description, re.IGNORECASE)
        if m1:
            try:
                val = m1.group(1) or m1.group(2)
                return int(val.replace(',', ''))
            except (ValueError, AttributeError):
                pass

        # 2. Kakera emoji/text preceding number (with or without **)
        # e.g. "<:kakera:123> **550**", ":kakera: 450"
        m2 = re.search(r'(?:<a?:\w+:\d+>|:?kakera\b)\s*(?:\*\*([\d,]+)\*\*|([\d,]+))', description, re.IGNORECASE)
        if m2:
            try:
                val = m2.group(1) or m2.group(2)
                return int(val.replace(',', ''))
            except (ValueError, AttributeError):
                pass

        # 3. Fallback: find any bold number with commas or digits in description
        all_bold = re.findall(r'\*\*([\d,]+)\*\*', description)
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
        full_text = description + " " + footer.get('text', '') + " " + message.get('content', '')
        is_halved_power = bool(re.search(r'(?:⚡|\u26a1\ufe0f?|:zap:|<a?:\w*zap\w*:\d+>)\s*/\s*2', full_text))
        has_double_spheres = bool(
            re.search(r'(?:<a?:sp:\d+>|:sp:|🔴)\s*(?:<a?:sp:\d+>|:sp:|🔴)', full_text, re.IGNORECASE) or
            len(re.findall(r'<a?:sp:\d+>|:sp:', full_text, re.IGNORECASE)) >= 2
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
        buttons = []
        for row in components:
            for comp in row.get('components', []):
                buttons.append(comp)

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

    @staticmethod
    def normalize_text(s: str) -> str:
        """Normalizes smart quotes, apostrophes, and spacing."""
        if not s:
            return ""
        s = s.replace("’", "'").replace("`", "'").replace("“", '"').replace("”", '"')
        s = re.sub(r'\s+', ' ', s)
        return s.strip().lower()

    @classmethod
    def match_character(cls, target: str, card_name: str) -> bool:
        """
        Matches desired character name against the rolled card name.
        Requires an exact match including any tags (e.g. 'Durandal' will not match 'Durandal (Uma)').
        Strictly prevents cross-character collisions.
        """
        t = cls.normalize_text(target)
        c = cls.normalize_text(card_name)
        if not t or not c:
            return False

        # Exact match (case-insensitive, normalized) prevents any false positives
        return t == c

    @classmethod
    def match_series(cls, target: str, card_series: str) -> bool:
        """
        Precisely matches a desired series name against the rolled card series.
        """
        t = cls.normalize_text(target)
        c = cls.normalize_text(card_series)
        if not t or not c:
            return False

        # 1. Exact match
        if t == c:
            return True

        # 2. Base match stripping parentheses/brackets
        t_base = re.sub(r'[\(\[\{].*?[\)\]\}]', '', t).strip()
        c_base = re.sub(r'[\(\[\{].*?[\)\]\}]', '', c).strip()
        if t_base and c_base and t_base == c_base:
            return True

        # 3. Whole-word / phrase bounded match (e.g. 'Fate' matches 'Fate/stay night')
        pattern = r'(?:\b|^)' + re.escape(t) + r'(?:\b|$)'
        if len(t) >= 3 and re.search(pattern, c):
            return True

        # 4. Prefix match for series (e.g. 'Re:Zero' matches 'Re:Zero kara Hajimeru Isekai Seikatsu')
        if len(t) >= 3 and c.startswith(t):
            return True

        return False

    @classmethod
    def should_claim(cls, card_info: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determines if a card should be claimed based on configured criteria.
        Returns (should_claim: bool, match_reason: str).
        """
        if card_info['is_claimed']:
            return False, ""

        # Option: Claim all unclaimed rolls
        if getattr(Vars, 'claimAllUnclaimed', False):
            return True, "Claim All Unclaimed"

        card_name = card_info['name']
        card_series = card_info['series']

        # Check Desired Characters with precise word-boundary matching
        desired_chars = getattr(Vars, 'desiredCharacters', [])
        for target in desired_chars:
            if not target or not str(target).strip():
                continue
            if cls.match_character(str(target), card_name):
                return True, f"Desired Character: '{target}'"

        # Check Desired Series with precise matching
        desired_series = getattr(Vars, 'desiredSeries', [])
        for target in desired_series:
            if not target or not str(target).strip():
                continue
            if cls.match_series(str(target), card_series):
                return True, f"Desired Series: '{target}'"

        # Check Minimum Kakera Power Threshold
        min_power = getattr(Vars, 'minPowerToClaim', 0)
        if min_power > 0 and card_info['power'] >= min_power:
            return True, f"High Kakera: {card_info['power']} >= {min_power}"

        return False, ""


# ---------------------------------------------------------------------------
# Mudae Roller Engine
# ---------------------------------------------------------------------------
class MudaeRoller:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': Vars.token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json'
        })
        self.discum_client = None
        self.cached_slash_command = None
        self.api_version = getattr(Vars, 'discordApiVersion', 'v10')
        self.messages_url = f"https://discord.com/api/{self.api_version}/channels/{Vars.channelId}/messages"
        self.state_mgr = StateManager()

    def sync_timers_via_tu(self):
        """Sends $tu and synchronizes claim and $rt timers from Mudae's response."""
        Logger.info("Syncing cooldown timers with Mudae ($tu)...")
        try:
            r = self.session.post(self.messages_url, json={'content': '$tu'}, timeout=5)
            if r.status_code not in (200, 201):
                return
            time.sleep(2.0)
            messages = self.fetch_recent_messages(limit=3)
            mudae_msg = next((m for m in messages if m.get('author', {}).get('id') == BOT_ID), None)
            if not mudae_msg:
                return

            content = mudae_msg.get('content', '')
            embeds = mudae_msg.get('embeds', [])
            full_text = content + ' ' + ' '.join(e.get('description', '') for e in embeds)
            full_text_lower = full_text.lower()

            # 1. Parse claim status
            if "can claim right now" in full_text_lower or "claim is ready" in full_text_lower:
                self.state_mgr.state['claim_available'] = True
                Logger.success("Claim status: READY")
            elif "can't claim right now" in full_text_lower or "cannot claim" in full_text_lower:
                self.state_mgr.state['claim_available'] = False
                Logger.info("Claim status: ON COOLDOWN")

            # 2. Parse $rt status
            if "$rt is ready" in full_text_lower or "rt is ready" in full_text_lower:
                self.state_mgr.state['rt_available'] = True
                self.state_mgr.state['last_rt_timestamp'] = 0.0
                Logger.success("🔄 $rt status: READY")
            elif "$rt" in full_text_lower or "reset" in full_text_lower:
                rt_match = re.search(r'(?:reset in|\$rt\b[^\d]*)\s*(?:(\d+)\s*h(?:ours?)?)?\s*(?:(\d+)\s*min)?', full_text_lower)
                if rt_match and (rt_match.group(1) or rt_match.group(2)):
                    h = int(rt_match.group(1) or 0)
                    m = int(rt_match.group(2) or 0)
                    rem_secs = h * 3600 + m * 60
                    cooldown_secs = getattr(Vars, 'rtCooldownHours', 5.0) * 3600.0
                    self.state_mgr.state['last_rt_timestamp'] = time.time() - max(0.0, cooldown_secs - rem_secs)
                    self.state_mgr.state['rt_available'] = False
                    Logger.info(f"🔄 $rt status: On cooldown ({h}h {m}m remaining)")

            self.state_mgr.state['last_tu_sync'] = time.time()
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
        """Attempts to claim a card via reaction with retry verification."""
        message_id = card_info['message_id']
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

    def react_to_kakeras(self, card_info: Dict[str, Any]) -> int:
        """Clicks any matching kakera or ourosphere buttons on the card."""
        desired_kakeras = [k.lower() for k in getattr(Vars, 'desiredKakeras', []) if k]
        auto_perk_bonus = getattr(Vars, 'autoPerkBonusKakera', True)
        is_bonus_card = auto_perk_bonus and card_info.get('has_sphere_perk_bonus', False)

        if is_bonus_card:
            reason = card_info.get('sphere_bonus_reason', 'Perk 8 Bonus')
            Logger.info(f"✨ Perk Bonus Active ({reason}) on {card_info['name']} -> Clicking ALL kakera & sphere buttons!")

        clicked = 0
        client = self._get_discum_client()

        buttons = card_info.get('buttons', [])
        # Prioritize free claims (spP, kakeraP) and high-value buttons first
        def button_priority(b):
            name = b.get('emoji', {}).get('name', '').lower()
            if name in ('spp', 'kakerap'):
                return 0
            if name.startswith('sp'):
                return 1
            if name in ('spr', 'kakerar', 'kakerao', 'spo'):
                return 2
            return 3

        sorted_buttons = sorted(buttons, key=button_priority)
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
                # If Perk 8 halved power (⚡/2) or double spheres (:sp: :sp:) is active,
                # click all kakera and sphere buttons regardless of whether they are in desiredKakeras!
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
                        Logger.info(f"🔮 Ourosphere button ({emoji_name}) clicked on {card_info['name']}")
                    else:
                        if is_bonus_card and emoji_lower not in desired_kakeras:
                            Logger.info(f"⚡ Perk 8 Bonus click ({emoji_name}) on {card_info['name']} [{card_info.get('sphere_bonus_reason')}]")
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

    def run_bonus_commands(self):
        """Executes configured daily and bonus commands ($p, $dk, $daily)."""
        bonus_cmds = []
        if getattr(Vars, 'pokeRoll', False):
            bonus_cmds.append(('Pokéslot', '$p'))
        if getattr(Vars, 'dailyKakera', False):
            bonus_cmds.append(('Daily Kakera', '$dk'))
        if getattr(Vars, 'dailyRoll', False):
            bonus_cmds.append(('Daily Rolls', '$daily'))

        for name, cmd in bonus_cmds:
            Logger.info(f"Executing bonus command: {name} ({cmd})...")
            try:
                r = self.session.post(self.messages_url, json={'content': cmd}, timeout=5)
                if r.status_code in (200, 201):
                    Logger.success(f"{name} ({cmd}) sent successfully.")
                else:
                    Logger.warn(f"{name} ({cmd}) returned HTTP {r.status_code}")
                time.sleep(1.5)
            except Exception as e:
                Logger.error(f"Error executing bonus command {cmd}: {e}")

    def run_roll_session(self):
        """Executes a full hourly roll session until rolls are exhausted or limits are reached."""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}")
        print(f"  🎲 MUDAE ROLL SESSION STARTED - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        roll_delay = getattr(Vars, 'rollDelay', 2.0)
        jitter = getattr(Vars, 'randomJitter', 0.5)
        max_rolls = getattr(Vars, 'maxRollsPerSession', 50)

        # Sync cooldown timers with $tu if enabled and needed
        if getattr(Vars, 'checkTuOnStartup', True):
            last_sync = self.state_mgr.state.get('last_tu_sync', 0.0)
            if last_sync == 0.0 or (time.time() - last_sync) > 3600.0:
                self.sync_timers_via_tu()

        rolls_count = 0
        claimed_cards = []
        kakeras_hit = 0
        last_processed_msg_id = None
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
                time.sleep(1.0)
                continue

            last_processed_msg_id = mudae_msg.get('id')
            consecutive_misses = 0

            # 4. Check if Mudae returned out-of-rolls text content instead of a card embed
            msg_content = mudae_msg.get('content', '')
            embeds = mudae_msg.get('embeds', [])

            if msg_content and not embeds:
                limit_indicators = [
                    'limited to', 'rolls left', 'until the reset', 'before the reset',
                    'cannot roll', "can't roll", '⏳', 'limité', '0 min', 'plus de rolls',
                    'roulette is limited', '0 rolls left', 'rolls left: 0', 'no rolls left',
                    'next rolls reset in'
                ]
                if any(ind in msg_content.lower() for ind in limit_indicators):
                    clean_msg = msg_content.replace('\n', ' ').strip()
                    Logger.warn(f"Out of rolls: {clean_msg[:80]}...")
                    break
                else:
                    # Non-limit text (e.g. Kakera drop confirmation, quote, mini-game)
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

                # Check claim timer; if on cooldown, check if $rt is ready!
                claim_ready = self.state_mgr.is_claim_ready()
                if not claim_ready:
                    if getattr(Vars, 'autoRtOnWishlist', True) and self.state_mgr.is_rt_ready():
                        Logger.warn(f"Claim timer is on cooldown, but $rt is READY! Triggering $rt for {card_info['name']}...")
                        try:
                            r = self.session.post(self.messages_url, json={'content': '$rt'}, timeout=5)
                            if r.status_code in (200, 201):
                                time.sleep(1.0)
                                self.state_mgr.record_rt_used()
                                Logger.success("🔄 $rt executed successfully! Claim timer refreshed.")
                                claim_ready = True
                        except Exception as e:
                            Logger.error(f"Failed to execute $rt: {e}")
                    else:
                        Logger.warn(f"Claim is on cooldown (and $rt is {self.state_mgr.get_rt_remaining_str()}). Attempting claim anyway...")

                if self.claim_card(card_info):
                    self.state_mgr.record_claim_used()
                    claimed_cards.append(f"{card_info['name']} ({card_info['series']}) - {card_info['power']} kakera [{reason}]")

            # 7. Check and execute Kakera Button Reacts
            kakeras_hit += self.react_to_kakeras(card_info)

        # 8. Bonus & Daily Commands ($p, $dk, $daily, $oh, $oc) if configured
        self.run_bonus_commands()

        # 9. Print Session Summary
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"  📊 ROLL SESSION SUMMARY")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"  Total Rolls Made   : {rolls_count}")
        print(f"  Kakeras Reacted    : {kakeras_hit}")
        print(f"  Cards Auto-Claimed : {len(claimed_cards)}")
        for claim in claimed_cards:
            print(f"   ➔ {Fore.GREEN}{claim}{Style.RESET_ALL}")
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