"""
Bot.py - Main launcher for Mudae AutoRoll, AutoClaim, and AutoReact Bot.
Initializes configuration, validates credentials, schedules hourly rolls, and runs the scheduler loop.
"""

import sys
import time
import schedule

# Reconfigure stdout/stderr on Windows to ensure UTF-8 characters and emojis render properly
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from colorama import Fore, Style
except ImportError:
    class DummyColor:
        def __getattr__(self, name):
            return ''
    Fore = DummyColor()
    Style = DummyColor()

import Vars
from Function import simpleRoll, Logger


def print_banner():
    banner = f"""
{Fore.MAGENTA}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════╗
║               MUDAE AUTO-BOT ENGINE 2025/2026                ║
║           AutoRoll • AutoClaim • AutoReact • Pokeslot        ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def display_configuration():
    time_str = Vars.format_schedule_minute()
    desired_chars_count = len([c for c in getattr(Vars, 'desiredCharacters', []) if c])
    desired_series_count = len([s for s in getattr(Vars, 'desiredSeries', []) if s])
    desired_kakera_count = len([k for k in getattr(Vars, 'desiredKakeras', []) if k])
    min_power = getattr(Vars, 'minPowerToClaim', 0)
    claim_all = getattr(Vars, 'claimAllUnclaimed', False)
    poke = getattr(Vars, 'pokeRoll', False)

    bonus_features = []
    if getattr(Vars, 'pokeRoll', False): bonus_features.append('$p')
    if getattr(Vars, 'dailyKakera', False): bonus_features.append('$dk')
    if getattr(Vars, 'dailyRoll', False): bonus_features.append('$daily')
    bonus_str = ', '.join(bonus_features) if bonus_features else 'Disabled'

    rt_cooldown = getattr(Vars, 'rtCooldownHours', 5.0)
    auto_rt = getattr(Vars, 'autoRtOnWishlist', True)

    print(f"{Fore.CYAN}┌── Configuration Summary ─────────────────────────────────────┐{Style.RESET_ALL}")
    print(f"│  Account Token     : {Fore.YELLOW}{Vars.get_masked_token()}{Style.RESET_ALL}")
    print(f"│  Channel ID        : {Fore.WHITE}{Vars.channelId}{Style.RESET_ALL}")
    print(f"│  Server ID         : {Fore.WHITE}{Vars.serverId}{Style.RESET_ALL}")
    print(f"│  Roll Command      : {Fore.GREEN}/{Vars.rollCommand}{Style.RESET_ALL}")
    print(f"│  Hourly Schedule   : {Fore.GREEN}Every hour at XX{time_str}{Style.RESET_ALL}")
    print(f"│  Target Characters : {Fore.WHITE}{desired_chars_count} configured{Style.RESET_ALL}")
    print(f"│  Target Series     : {Fore.WHITE}{desired_series_count} configured{Style.RESET_ALL}")
    print(f"│  Min Power Claim   : {Fore.WHITE}{f'{min_power} kakera' if min_power > 0 else 'Disabled'}{Style.RESET_ALL}")
    print(f"│  Claim All Unclaim : {Fore.WHITE}{'Enabled' if claim_all else 'Disabled'}{Style.RESET_ALL}")
    print(f"│  $rt Reset Timer   : {Fore.GREEN}{rt_cooldown}h cooldown (Auto-RT: {'Enabled' if auto_rt else 'Disabled'}){Style.RESET_ALL}")
    print(f"│  Kakera/Spheres    : {Fore.WHITE}{desired_kakera_count} active button types{Style.RESET_ALL}")
    print(f"│  Perk 8 Auto-Bonus : {Fore.GREEN}{'Enabled (All kakera on ⚡/2 & :sp: :sp:)' if getattr(Vars, 'autoPerkBonusKakera', True) else 'Disabled'}{Style.RESET_ALL}")
    print(f"│  Bonus Commands    : {Fore.WHITE}{bonus_str}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}└──────────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")


def main():
    print_banner()

    # 1. Validate configuration
    is_valid, issues = Vars.validate_config()
    if not is_valid:
        Logger.warn("Configuration issues detected:")
        for issue in issues:
            print(f"   {Fore.YELLOW}• {issue}{Style.RESET_ALL}")
        print()

    display_configuration()

    # 2. Run immediately on startup if configured
    if getattr(Vars, 'runOnStartup', True):
        Logger.info("Executing initial startup roll session...")
        try:
            simpleRoll()
        except Exception as e:
            Logger.error(f"Error during startup roll: {e}")

    # 3. Setup hourly schedule
    time_string = Vars.format_schedule_minute()
    schedule.every().hour.at(time_string).do(simpleRoll)
    Logger.success(f"Scheduler active! Bot will roll every hour at XX{time_string}.")
    Logger.info("Press Ctrl+C at any time to stop the bot.\n")

    # 4. Main execution loop
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user (Ctrl+C). Goodbye!{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        Logger.error(f"Fatal error in scheduler loop: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
