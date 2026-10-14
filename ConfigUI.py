"""
ConfigUI.py - Graphical settings editor for the Mudae AutoRoll/AutoClaim/AutoReact bot.

Reads and writes settings.json next to this file (see Vars.py for how it is loaded).
Run with:  python ConfigUI.py
Restart Bot.py after saving for the changes to take effect.
"""

import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox

import Vars

# Kakera button emoji names
KNOWN_KAKERAS = [
    'kakeraP', 'kakeraR', 'kakeraO', 'kakeraY', 'kakeraG', 'kakeraB',
    'kakeraT', 'kakeraW', 'kakeraL', 'kakeraD', 'kakeraC', 'kakera',
]
# Kakera button emoji names -> Friendly Color Display Name
KAKERA_DISPLAY_NAMES = {
    'kakeraP': 'Purple',
    'kakeraR': 'Red',
    'kakeraO': 'Orange',
    'kakeraY': 'Yellow',
    'kakeraG': 'Green',
    'kakeraB': 'Blue',
    'kakeraT': 'Teal',
    'kakeraW': 'Rainbow',
    'kakeraL': 'Light Blue',
    'kakeraD': 'Dark Blue',
    'kakeraC': 'Chaos',
    'kakera':  'Basic / Bronze',
}

# Ourosphere (Sphere) button emoji names (Perk 9 & drops)
KNOWN_SPHERES = [
    'spP', 'spR', 'spO', 'spY', 'spG', 'spT', 'spB', 'spL', 'spD', 'spM', 'spW', 'spC',
]
# Ourosphere (Sphere) button emoji names -> Friendly Color Display Name
SPHERE_DISPLAY_NAMES = {
    'spP': 'Purple (Free Claim)',
    'spR': 'Red (Top Tier)',
    'spO': 'Orange',
    'spY': 'Yellow',
    'spG': 'Green',
    'spT': 'Teal',
    'spB': 'Blue',
    'spL': 'Light Blue',
    'spD': 'Dark Blue',
    'spM': 'Magenta',
    'spW': 'White',
    'spC': 'Cyan',
}
ALL_KNOWN_BUTTONS = KNOWN_KAKERAS + KNOWN_SPHERES
# Display name -> emoji. Tk 8.6 can't draw colour emoji, so the dropdown shows names instead.
# A raw emoji can still be typed/pasted into the box.
CLAIM_EMOJIS = {
    'Sparkling heart': '💖',
    'Red heart': '❤️',
    'Chipmunk': '🐿️',
    'Ring': '💍',
    'Thumbs up': '👍',
    'Star': '⭐',
}
EMOJI_NAMES = {emoji: name for name, emoji in CLAIM_EMOJIS.items()}
ROLL_COMMANDS = ['wx', 'wa', 'wg', 'mx', 'ma', 'mg', 'hx', 'ha', 'hg']
ACCOUNT_KEYS = ('token', 'channelId', 'serverId')


class ConfigApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Mudae Automation Settings")
        root.minsize(640, 560)

        style = ttk.Style(root)
        style.configure('Hint.TLabel', foreground='#6b6b6b')
        style.configure('Warn.TLabel', foreground='#9a5b00')
        style.configure('Header.TLabel', font=('Segoe UI', 13, 'bold'))

        self.vars = {}          # setting key -> tk variable (scalar settings)
        self.lists = {}         # setting key -> tk.Text (list settings)
        self.kakera_vars = {}   # kakera name -> BooleanVar

        self._build_layout()
        self.load_into_form(Vars.get_file_settings())
        self._snapshot = self._form_state()

        root.bind('<Control-s>', lambda e: self.save())
        root.protocol('WM_DELETE_WINDOW', self.on_close)

    # ------------------------------------------------------------------ layout
    def _build_layout(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)

        ttk.Label(outer, text="Mudae Bot Settings", style='Header.TLabel').pack(anchor='w')
        ttk.Label(outer, text=f"Saved to: {Vars.SETTINGS_FILE}", style='Hint.TLabel').pack(anchor='w', pady=(0, 6))

        overrides = Vars.get_env_overrides()
        if overrides:
            names = ', '.join(Vars.ENV_VARS[k] for k in overrides)
            ttk.Label(
                outer, style='Warn.TLabel', wraplength=600, justify='left',
                text=f"[NOTE] These are set by environment variables / .env and take priority over "
                     f"values saved here: {names}",
            ).pack(anchor='w', pady=(0, 6))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill='both', expand=True)
        notebook.add(self._build_account_tab(notebook), text='  Account  ')
        notebook.add(self._build_rolling_tab(notebook), text='  Rolling  ')
        notebook.add(self._build_claim_tab(notebook), text='  Auto-Claim  ')
        notebook.add(self._build_kakera_tab(notebook), text='  Kakera  ')

        bar = ttk.Frame(outer, padding=(0, 10, 0, 0))
        bar.pack(fill='x')
        self.status = ttk.Label(bar, text="", style='Hint.TLabel')
        self.status.pack(side='left')
        ttk.Button(bar, text="Save", command=self.save).pack(side='right')
        ttk.Button(bar, text="Reload", command=self.reload).pack(side='right', padx=6)
        ttk.Button(bar, text="Reset to defaults", command=self.reset_defaults).pack(side='right')

    def _tab(self, notebook):
        frame = ttk.Frame(notebook, padding=14)
        frame.columnconfigure(1, weight=1)
        return frame

    def _row(self, parent, row, label, widget, hint=None):
        """Places a label + widget on a grid row, with an optional hint below. Returns next row."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=(6, 0))
        widget.grid(row=row, column=1, sticky='w', pady=(6, 0))
        row += 1
        if hint:
            ttk.Label(parent, text=hint, style='Hint.TLabel', wraplength=420, justify='left') \
                .grid(row=row, column=1, sticky='w')
            row += 1
        return row

    def _string(self, key):
        self.vars[key] = tk.StringVar(self.root)
        return self.vars[key]

    def _bool(self, key):
        self.vars[key] = tk.BooleanVar(self.root)
        return self.vars[key]

    def _build_account_tab(self, nb):
        f = self._tab(nb)
        token_box = ttk.Frame(f)
        self.token_entry = ttk.Entry(token_box, textvariable=self._string('token'), show='•', width=52)
        self.token_entry.pack(side='left')
        self.show_token = tk.BooleanVar(self.root, value=False)
        ttk.Checkbutton(token_box, text="Show", variable=self.show_token,
                        command=lambda: self.token_entry.config(show='' if self.show_token.get() else '•')) \
            .pack(side='left', padx=(8, 0))

        r = self._row(f, 0, "Discord token", token_box,
                      "Token of the account that rolls. Keep it secret – anyone with it controls your account.")
        r = self._row(f, r, "Channel ID", ttk.Entry(f, textvariable=self._string('channelId'), width=24),
                      "Right-click the channel → Copy Channel ID (Developer Mode must be enabled).")
        r = self._row(f, r, "Server ID", ttk.Entry(f, textvariable=self._string('serverId'), width=24),
                      "Right-click the server icon → Copy Server ID.")
        return f

    def _build_rolling_tab(self, nb):
        f = self._tab(nb)
        r = self._row(f, 0, "Roll command",
                      ttk.Combobox(f, textvariable=self._string('rollCommand'), values=ROLL_COMMANDS, width=8),
                      "Slash command used to roll (w = waifu, h = husbando, m = both; x/a/g = all/anime/game).")
        r = self._row(f, r, "Roll at minute",
                      ttk.Spinbox(f, textvariable=self._string('repeatMinute'), from_=0, to=59, width=8, wrap=True),
                      "The bot rolls once every hour at this minute (0–59).")
        r = self._row(f, r, "Delay between rolls (s)",
                      ttk.Spinbox(f, textvariable=self._string('rollDelay'), from_=0.5, to=30, increment=0.1, width=8))
        r = self._row(f, r, "Random jitter (± s)",
                      ttk.Spinbox(f, textvariable=self._string('randomJitter'), from_=0, to=10, increment=0.1, width=8),
                      "Random variation added to the delay so rolls aren't perfectly regular.")
        r = self._row(f, r, "Max rolls per session",
                      ttk.Spinbox(f, textvariable=self._string('maxRollsPerSession'), from_=1, to=500, width=8),
                      "Safety limit – a session normally ends when Mudae says you're out of rolls.")
        r = self._row(f, r, "", ttk.Checkbutton(f, text="Roll immediately when Bot.py starts",
                                                variable=self._bool('runOnStartup')))
        r = self._row(f, r, "", ttk.Checkbutton(f, text="Also roll Pokéslot ($p)",
                                                variable=self._bool('pokeRoll')))
        r = self._row(f, r, "", ttk.Checkbutton(f, text="Also claim Daily Kakera ($dk)",
                                                variable=self._bool('dailyKakera')))
        r = self._row(f, r, "Daily kakera power threshold (%)",
                      ttk.Spinbox(f, textvariable=self._string('dkPowerThreshold'), from_=1, to=100, width=8),
                      "Only executes $dk when kakera power is below this percentage (default: 15%).")
        r = self._row(f, r, "", ttk.Checkbutton(f, text="Also claim Daily rolls/vote ($daily)",
                                                variable=self._bool('dailyRoll')))
        return f

    def _list_box(self, parent, key, title, hint):
        box = ttk.LabelFrame(parent, text=title, padding=8)
        text = tk.Text(box, height=10, width=28, wrap='none', undo=True, font=('Segoe UI', 10))
        scroll = ttk.Scrollbar(box, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        ttk.Label(box, text=hint, style='Hint.TLabel', wraplength=260, justify='left') \
            .pack(side='bottom', anchor='w', pady=(6, 0))
        scroll.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        self.lists[key] = text
        return box

    def _build_claim_tab(self, nb):
        f = self._tab(nb)
        r = self._row(f, 0, "", ttk.Checkbutton(f, text="Claim EVERY unclaimed card",
                                                variable=self._bool('claimAllUnclaimed')),
                      "Overrides all filters below – uses your claim on the first unclaimed card.")
        r = self._row(f, r, "Claim if kakera value ≥",
                      ttk.Spinbox(f, textvariable=self._string('minPowerToClaim'), from_=0, to=100000,
                                  increment=50, width=10),
                      "0 disables value-based claiming.")
        r = self._row(f, r, "Claim reaction emoji",
                      ttk.Combobox(f, textvariable=self._string('claimEmoji'), values=list(CLAIM_EMOJIS), width=16),
                      "Pick one, or paste any other emoji.")
        r = self._row(f, r, "$rt cooldown (hours)",
                      ttk.Spinbox(f, textvariable=self._string('rtCooldownHours'), from_=0.1, to=24.0, increment=0.5, width=8),
                      "Base 20h, select how much rt cooldown you have. Persisted in bot_state.json across restarts.")
        r = self._row(f, r, "", ttk.Checkbutton(f, text="Auto-use $rt if a wishlist character drops while claim is on cooldown",
                                                variable=self._bool('autoRtOnWishlist')),
                      "Instantly fires $rt to reset your claim so you never miss a desired character.")
        r = self._row(f, r, "", ttk.Checkbutton(f, text="Auto-sync timers with Mudae ($tu) on start and every hour",
                                                variable=self._bool('checkTuOnStartup')),
                      "Queries $tu to ensure exact claim and $rt cooldown synchronization.")

        lists = ttk.Frame(f)
        lists.grid(row=r, column=0, columnspan=2, sticky='nsew', pady=(12, 0))
        f.rowconfigure(r, weight=1)
        lists.columnconfigure((0, 1), weight=1, uniform='lists')
        lists.rowconfigure(0, weight=1)
        char_hint = "One per line. Case-insensitive exact name match (e.g. 'Rem' only matches 'Rem', not 'Remilia')."
        series_hint = "One per line. Case-insensitive whole-word or prefix match (e.g. 'Fate' matches 'Fate/stay night')."
        self._list_box(lists, 'desiredCharacters', "Characters to claim", char_hint) \
            .grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        self._list_box(lists, 'desiredSeries', "Series to claim", series_hint) \
            .grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        return f

    def _build_kakera_tab(self, nb):
        f = self._tab(nb)

        # 1. Standard Kakera group
        k_frame = ttk.LabelFrame(f, text=" Standard Kakera Buttons ", padding=8)
        k_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        cols = 3
        for i, name in enumerate(KNOWN_KAKERAS):
            var = tk.BooleanVar(self.root)
            self.kakera_vars[name] = var
            display_text = KAKERA_DISPLAY_NAMES.get(name, name)
            ttk.Checkbutton(k_frame, text=display_text, variable=var, width=18) \
                .grid(row=i // cols, column=i % cols, sticky='w', padx=(0, 8), pady=2)

        # 2. Ourospheres group
        s_frame = ttk.LabelFrame(f, text=" Ourospheres (Perk 9 / Sphere Buttons) ", padding=8)
        s_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        for i, name in enumerate(KNOWN_SPHERES):
            var = tk.BooleanVar(self.root)
            self.kakera_vars[name] = var
            display_text = SPHERE_DISPLAY_NAMES.get(name, name)
            ttk.Checkbutton(s_frame, text=display_text, variable=var, width=18) \
                .grid(row=i // cols, column=i % cols, sticky='w', padx=(0, 8), pady=2)

        # Selection Buttons
        btns = ttk.Frame(f)
        btns.grid(row=2, column=0, columnspan=2, sticky='w', pady=(2, 6))
        ttk.Button(btns, text="Select All Kakera", command=lambda: self._set_kakeras_group(KNOWN_KAKERAS, True)).pack(side='left')
        ttk.Button(btns, text="Select All Spheres", command=lambda: self._set_kakeras_group(KNOWN_SPHERES, True)).pack(side='left', padx=4)
        ttk.Button(btns, text="Select All", command=lambda: self._set_all_kakeras(True)).pack(side='left', padx=4)
        ttk.Button(btns, text="Select None", command=lambda: self._set_all_kakeras(False)).pack(side='left')

        r = self._row(f, 3, "Other (comma-separated)",
                      ttk.Entry(f, textvariable=self._string('otherKakeras'), width=40),
                      "Extra button emoji names not listed above. Matching is case-insensitive.")
        r = self._row(f, r, "",
                      ttk.Checkbutton(f, text="Auto-click all kakera buttons on Perk 8 cards (halved power and double spheres)",
                                      variable=self._bool('autoPerkBonusKakera')),
                      "Recommended. Clicking these earns high sphere rewards from Perk 5 at 50% power cost or 2x spheres.")
        return f

    def _set_kakeras_group(self, group: list, value: bool):
        for name in group:
            if name in self.kakera_vars:
                self.kakera_vars[name].set(value)

    def _set_all_kakeras(self, value: bool):
        for var in self.kakera_vars.values():
            var.set(value)

    # ------------------------------------------------------------- data <-> form
    def load_into_form(self, s: dict, skip_keys=()):
        for key, var in self.vars.items():
            if key in skip_keys or key not in s:
                continue
            value = s[key]
            if key == 'claimEmoji':
                value = EMOJI_NAMES.get(value, value)
            var.set(value)
        for key, text in self.lists.items():
            if key in skip_keys:
                continue
            text.delete('1.0', 'end')
            text.insert('1.0', '\n'.join(s.get(key, [])))

        if 'desiredKakeras' not in skip_keys:
            known_lower = {k.lower(): k for k in ALL_KNOWN_BUTTONS}
            selected, others = set(), []
            for name in s.get('desiredKakeras', []):
                if name.lower() in known_lower:
                    selected.add(known_lower[name.lower()])
                else:
                    others.append(name)
            for name, var in self.kakera_vars.items():
                var.set(name in selected)
            self.vars['otherKakeras'].set(', '.join(others))

    def _form_state(self):
        """Raw snapshot of every field, used to detect unsaved changes."""
        return (
            tuple((k, str(v.get())) for k, v in sorted(self.vars.items())),
            tuple((k, t.get('1.0', 'end-1c')) for k, t in sorted(self.lists.items())),
            tuple((k, v.get()) for k, v in sorted(self.kakera_vars.items())),
        )

    def _number(self, key, label, kind, minimum=None, maximum=None):
        raw = self.vars[key].get().strip()
        try:
            value = kind(raw)
        except ValueError:
            word = "a whole number" if kind is int else "a number"
            raise ValueError(f"{label} must be {word} (got '{raw}').")
        if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            bounds = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
            raise ValueError(f"{label} must be {bounds} (got {raw}).")
        return value

    def collect(self) -> dict:
        """Reads the form into a settings dict. Raises ValueError with a readable message on bad input."""
        s = {key: self.vars[key].get().strip() for key in ('token', 'channelId', 'serverId')}
        emoji = self.vars['claimEmoji'].get().strip()
        s['claimEmoji'] = CLAIM_EMOJIS.get(emoji, emoji)
        s['rollCommand'] = self.vars['rollCommand'].get().strip().lower()
        s['repeatMinute'] = f"{self._number('repeatMinute', 'Roll minute', int, 0, 59):02d}"
        s['rollDelay'] = self._number('rollDelay', 'Delay between rolls', float, 0.1)
        s['randomJitter'] = self._number('randomJitter', 'Random jitter', float, 0)
        s['maxRollsPerSession'] = self._number('maxRollsPerSession', 'Max rolls per session', int, 1)
        s['minPowerToClaim'] = self._number('minPowerToClaim', 'Minimum kakera value', int, 0)
        s['rtCooldownHours'] = self._number('rtCooldownHours', '$rt cooldown', float, 0.1, 24.0)
        s['dkPowerThreshold'] = self._number('dkPowerThreshold', 'Daily kakera threshold', int, 1, 100)
        for key in ('runOnStartup', 'pokeRoll', 'dailyKakera', 'dailyRoll', 'autoRtOnWishlist', 'checkTuOnStartup', 'claimAllUnclaimed', 'autoPerkBonusKakera'):
            s[key] = bool(self.vars[key].get())
        for key, text in self.lists.items():
            s[key] = [line.strip() for line in text.get('1.0', 'end').splitlines() if line.strip()]

        others = [k.strip() for k in self.vars['otherKakeras'].get().replace(';', ',').split(',') if k.strip()]
        s['desiredKakeras'] = [k for k in ALL_KNOWN_BUTTONS if self.kakera_vars[k].get()] + others
        return s

    # ----------------------------------------------------------------- actions
    def _set_status(self, msg):
        self.status.config(text=msg)

    def _has_unsaved_changes(self):
        return self._form_state() != self._snapshot

    def save(self) -> bool:
        try:
            settings = self.collect()
        except ValueError as e:
            messagebox.showerror("Invalid value", str(e), parent=self.root)
            return False

        issues = Vars.validate_settings(settings)
        if issues:
            text = "\n".join(f"• {i}" for i in issues)
            if not messagebox.askyesno("Check your settings", f"{text}\n\nSave anyway?",
                                       icon='warning', parent=self.root):
                return False
        try:
            Vars.save_settings(settings)
        except OSError as e:
            messagebox.showerror("Save failed", f"Could not write settings file:\n{e}", parent=self.root)
            return False

        self._snapshot = self._form_state()
        self._set_status(f"Saved at {time.strftime('%H:%M:%S')} – restart Bot.py to apply.")
        return True

    def reload(self):
        if self._has_unsaved_changes() and not messagebox.askyesno(
                "Discard changes?", "Discard unsaved changes and reload from disk?", parent=self.root):
            return
        self.load_into_form(Vars.get_file_settings())
        self._snapshot = self._form_state()
        self._set_status("Reloaded from disk.")

    def reset_defaults(self):
        if not messagebox.askyesno(
                "Reset to defaults",
                "Reset all rolling, claim and kakera settings to their defaults?\n"
                "Your token, channel ID and server ID are kept.\n\nNothing is saved until you click Save.",
                parent=self.root):
            return
        self.load_into_form(Vars.DEFAULTS, skip_keys=ACCOUNT_KEYS)
        self._set_status("Defaults loaded (not saved yet).")

    def on_close(self):
        if self._has_unsaved_changes():
            answer = messagebox.askyesnocancel("Unsaved changes", "Save changes before closing?", parent=self.root)
            if answer is None or (answer and not self.save()):
                return
        self.root.destroy()


def main():
    if sys.platform == 'win32':
        try:  # Crisp text on high-DPI displays
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    ConfigApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
