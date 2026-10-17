"""
Bot.py - Main launcher for Mudae AutoRoll, AutoClaim, and AutoReact Bot.
Initializes configuration, validates credentials, schedules hourly rolls, and runs the scheduler loop.
"""

import os
import sys
import time
import schedule

# Reconfigure stdout/stderr on Windows to ensure UTF-8 characters render properly
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
{Fore.CYAN}{Style.BRIGHT}================================================================
                    MUDAE AUTOMATION TOOL
================================================================{Style.RESET_ALL}
"""
    print(banner)


def display_configuration():
    time_str = Vars.format_schedule_minute()
    desired_chars_count = len([c for c in getattr(Vars, 'desiredCharacters', []) if c])
    desired_series_count = len([s for s in getattr(Vars, 'desiredSeries', []) if s])
    desired_kakera_count = len([k for k in getattr(Vars, 'desiredKakeras', []) if k])
    min_power = getattr(Vars, 'minPowerToClaim', 0)
    claim_all = getattr(Vars, 'claimAllUnclaimed', False)
    dk_thresh = getattr(Vars, 'dkPowerThreshold', 15)

    bonus_features = []
    if getattr(Vars, 'pokeRoll', False):
        bonus_features.append('$p')
    if getattr(Vars, 'dailyKakera', False):
        bonus_features.append(f'$dk (<{dk_thresh}% power)')
    if getattr(Vars, 'dailyRoll', False):
        bonus_features.append('$daily')
    bonus_str = ', '.join(bonus_features) if bonus_features else 'Disabled'

    rt_cooldown = getattr(Vars, 'rtCooldownHours', 5.0)
    auto_rt = getattr(Vars, 'autoRtOnWishlist', True)
    perk_bonus = getattr(Vars, 'autoPerkBonusKakera', True)

    print(f"{Fore.CYAN}+-- Configuration Summary -------------------------------------+{Style.RESET_ALL}")
    print(f"|  Account Token     : {Fore.YELLOW}{Vars.get_masked_token()}{Style.RESET_ALL}")
    print(f"|  Channel ID        : {Fore.WHITE}{Vars.channelId}{Style.RESET_ALL}")
    print(f"|  Server ID         : {Fore.WHITE}{Vars.serverId}{Style.RESET_ALL}")
    print(f"|  Roll Command      : {Fore.GREEN}/{Vars.rollCommand}{Style.RESET_ALL}")
    print(f"|  Hourly Schedule   : {Fore.GREEN}Every hour at XX{time_str}{Style.RESET_ALL}")
    print(f"|  Target Characters : {Fore.WHITE}{desired_chars_count} configured{Style.RESET_ALL}")
    print(f"|  Target Series     : {Fore.WHITE}{desired_series_count} configured{Style.RESET_ALL}")
    print(f"|  Min Power Claim   : {Fore.WHITE}{f'{min_power:,} kakera' if min_power > 0 else 'Disabled'}{Style.RESET_ALL}")
    print(f"|  Claim All Unclaim : {Fore.WHITE}{'Enabled' if claim_all else 'Disabled'}{Style.RESET_ALL}")
    print(f"|  $rt Reset Timer   : {Fore.GREEN}{rt_cooldown}h cooldown (Auto-RT: {'Enabled' if auto_rt else 'Disabled'}){Style.RESET_ALL}")
    print(f"|  Kakera/Spheres    : {Fore.WHITE}{desired_kakera_count} active button types{Style.RESET_ALL}")
    print(f"|  Perk 8 Auto-Bonus : {Fore.GREEN}{'Enabled (All kakera on halved power & double spheres)' if perk_bonus else 'Disabled'}{Style.RESET_ALL}")
    print(f"|  Bonus Commands    : {Fore.WHITE}{bonus_str}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}+--------------------------------------------------------------+{Style.RESET_ALL}\n")


def _get_settings_mtime() -> float:
    try:
        if os.path.isfile(Vars.SETTINGS_FILE):
            return os.path.getmtime(Vars.SETTINGS_FILE)
    except OSError:
        pass
    return 0.0


def main():
    print_banner()

    # 1. Validate configuration
    is_valid, issues = Vars.validate_config()
    if not is_valid:
        Logger.warn("Configuration issues detected:")
        for issue in issues:
            print(f"   {Fore.YELLOW}* {issue}{Style.RESET_ALL}")
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
    current_time_str = Vars.format_schedule_minute()
    schedule.every().hour.at(current_time_str).do(simpleRoll)
    last_mtime = _get_settings_mtime()

    Logger.success(f"Scheduler active. Bot will roll every hour at XX{current_time_str}.")
    Logger.info("Settings changes saved in ConfigUI.py are hot-reloaded automatically.")
    Logger.info("Press Ctrl+C at any time to stop the bot.\n")

    # 4. Main execution loop with live configuration hot-reload
    try:
        while True:
            mtime = _get_settings_mtime()
            if mtime != last_mtime:
                last_mtime = mtime
                Vars.reload_settings()
                new_time_str = Vars.format_schedule_minute()
                if new_time_str != current_time_str:
                    current_time_str = new_time_str
                    schedule.clear()
                    schedule.every().hour.at(current_time_str).do(simpleRoll)
                    Logger.info(f"Configuration reloaded. Rescheduled hourly rolls to XX{current_time_str}.")
                else:
                    Logger.info("Configuration reloaded from settings.json.")

            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user (Ctrl+C).{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        Logger.error(f"Fatal error in scheduler loop: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
