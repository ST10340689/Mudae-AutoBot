"""
ConfigUI.py - Graphical settings editor for the Mudae Automation Tool.

Reads and writes settings.json next to this file (see Vars.py for how it is loaded).
Run with:  python ConfigUI.py
Changes saved here are automatically hot-reloaded by Bot.py.
"""

import os
import sys
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox

import Vars

# Kakera button emoji names ordered by Mudae tier/color
KNOWN_KAKERAS = [
    'kakeraP', 'kakeraW', 'kakeraC', 'kakeraL', 'kakeraR', 'kakeraO',
    'kakeraY', 'kakeraG', 'kakeraT', 'kakeraB', 'kakeraD', 'kakera',
]

# Kakera button emoji names -> Friendly Color Display Name
KAKERA_DISPLAY_NAMES = {
    'kakeraP': 'Purple (0% Cost)',
    'kakeraW': 'Rainbow',
    'kakeraC': 'Chaos',
    'kakeraL': 'Light Blue',
    'kakeraR': 'Red',
    'kakeraO': 'Orange',
    'kakeraY': 'Yellow',
    'kakeraG': 'Green',
    'kakeraT': 'Teal',
    'kakeraB': 'Blue',
    'kakeraD': 'Dark Blue',
    'kakera':  'Bronze (Base)',
}

# Hex color swatches for visual identification in the UI
BUTTON_SWATCH_COLORS = {
    'kakeraP': '#9b59b6',
    'kakeraW': '#e84393',
    'kakeraC': '#6c5ce7',
    'kakeraL': '#74b9ff',
    'kakeraR': '#e74c3c',
    'kakeraO': '#e67e22',
    'kakeraY': '#f1c40f',
    'kakeraG': '#2ecc71',
    'kakeraT': '#1abc9c',
    'kakeraB': '#3498db',
    'kakeraD': '#1f3a93',
    'kakera':  '#cd7f32',
    'spP': '#9b59b6',
    'spR': '#e74c3c',
    'spO': '#e67e22',
    'spY': '#f1c40f',
    'spG': '#2ecc71',
    'spT': '#1abc9c',
    'spB': '#3498db',
    'spL': '#74b9ff',
    'spD': '#1f3a93',
    'spM': '#fd79a8',
    'spW': '#dfe6e9',
    'spC': '#00cec9',
}

# Ourosphere (Sphere) button emoji names (Perk 9 & drops)
KNOWN_SPHERES = [
    'spP', 'spR', 'spO', 'spY', 'spG', 'spT', 'spB', 'spL', 'spD', 'spM', 'spW', 'spC',
]

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
STATE_FILE = os.path.join(Vars.BASE_DIR, 'bot_state.json')


class ConfigApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Mudae Automation Settings")
        root.minsize(720, 640)

        self._configure_styles(root)

        self.vars = {}          # setting key -> tk variable (scalar settings)
        self.lists = {}         # setting key -> tk.Text (list settings)
        self.list_frames = {}   # setting key -> (LabelFrame, base_title)
        self.kakera_vars = {}   # kakera name -> BooleanVar
        self._snapshot = None

        self._build_layout()
        self.load_into_form(Vars.get_file_settings())
        self._snapshot = self._form_state()
        self._refresh_live_state()

        # Bindings for shortcuts and dirty tracking
        root.bind('<Control-s>', lambda e: self.save())
        root.bind('<Control-r>', lambda e: self.reload())
        root.protocol('WM_DELETE_WINDOW', self.on_close)

        for var in self.vars.values():
            var.trace_add('write', lambda *_: self._on_field_changed())
        for var in self.kakera_vars.values():
            var.trace_add('write', lambda *_: self._on_field_changed())

    def _configure_styles(self, root: tk.Tk):
        style = ttk.Style(root)
        # Use native vista/xpnative on Windows if available for crisp controls
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        elif 'clam' in style.theme_names():
            style.theme_use('clam')

        style.configure('TLabel', font=('Segoe UI', 9))
        style.configure('TCheckbutton', font=('Segoe UI', 9))
        style.configure('TButton', font=('Segoe UI', 9), padding=(8, 3))
        style.configure('Save.TButton', font=('Segoe UI', 9, 'bold'), padding=(12, 3))
        style.configure('Small.TButton', font=('Segoe UI', 8), padding=(5, 1))
        style.configure('TLabelframe.Label', font=('Segoe UI', 9, 'bold'), foreground='#1f2937')
        style.configure('TNotebook.Tab', font=('Segoe UI', 9), padding=(10, 4))

        style.configure('Header.TLabel', font=('Segoe UI', 13, 'bold'), foreground='#111827')
        style.configure('SubHeader.TLabel', font=('Segoe UI', 8), foreground='#6b7280')
        style.configure('Hint.TLabel', font=('Segoe UI', 8), foreground='#6b7280')
        style.configure('Warn.TLabel', font=('Segoe UI', 8, 'bold'), foreground='#b45309')
        style.configure('StatusOk.TLabel', font=('Segoe UI', 9), foreground='#15803d')
        style.configure('StatusDirty.TLabel', font=('Segoe UI', 9, 'bold'), foreground='#b45309')
        style.configure('Badge.TLabel', font=('Segoe UI', 8, 'bold'), foreground='#374151')

    # ------------------------------------------------------------------ layout
    def _build_layout(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)

        # Top Header Row
        header_row = ttk.Frame(outer)
        header_row.pack(fill='x', pady=(0, 6))

        title_col = ttk.Frame(header_row)
        title_col.pack(side='left', fill='x', expand=True)
        ttk.Label(title_col, text="Mudae Automation Settings", style='Header.TLabel').pack(anchor='w')
        ttk.Label(
            title_col,
            text=f"Configuration file: {Vars.SETTINGS_FILE} (Hot-reloaded automatically by Bot.py)",
            style='SubHeader.TLabel'
        ).pack(anchor='w')

        # Live Bot State Bar (reads bot_state.json)
        state_box = ttk.LabelFrame(outer, text=" Live Bot Cooldown & Power Status (bot_state.json) ", padding=(8, 4))
        state_box.pack(fill='x', pady=(0, 8))
        self.live_state_label = ttk.Label(state_box, text="No state recorded yet.", style='Badge.TLabel')
        self.live_state_label.pack(side='left', fill='x', expand=True)
        ttk.Button(state_box, text="Refresh Status", style='Small.TButton', command=self._refresh_live_state).pack(side='right')

        overrides = Vars.get_env_overrides()
        if overrides:
            names = ', '.join(Vars.ENV_VARS[k] for k in overrides)
            ttk.Label(
                outer, style='Warn.TLabel', wraplength=680, justify='left',
                text=f"[NOTE] Environment variables / .env override these fields: {names}",
            ).pack(anchor='w', pady=(0, 6))

        # Main Tabbed Notebook
        notebook = ttk.Notebook(outer)
        notebook.pack(fill='both', expand=True)
        notebook.add(self._build_account_tab(notebook), text='  Account  ')
        notebook.add(self._build_rolling_tab(notebook), text='  Rolling & Bonuses  ')
        notebook.add(self._build_claim_tab(notebook), text='  Auto-Claim & Wishlist  ')
        notebook.add(self._build_kakera_tab(notebook), text='  Kakera & Spheres  ')

        # Bottom Action Bar
        bar = ttk.Frame(outer, padding=(0, 10, 0, 0))
        bar.pack(fill='x')
        self.status = ttk.Label(bar, text="Ready.", style='Hint.TLabel')
        self.status.pack(side='left')
        ttk.Button(bar, text="Save Settings (Ctrl+S)", style='Save.TButton', command=self.save).pack(side='right')
        ttk.Button(bar, text="Reload", command=self.reload).pack(side='right', padx=6)
        ttk.Button(bar, text="Reset to Defaults", command=self.reset_defaults).pack(side='right')

    def _tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        frame.columnconfigure(0, weight=1)
        return frame

    def _row(self, parent, row, label, widget, hint=None):
        """Places a label + widget on a grid row, with an optional hint below. Returns next row."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=(5, 0))
        widget.grid(row=row, column=1, sticky='w', pady=(5, 0))
        row += 1
        if hint:
            ttk.Label(parent, text=hint, style='Hint.TLabel', wraplength=460, justify='left') \
                .grid(row=row, column=1, sticky='w', pady=(1, 2))
            row += 1
        return row

    def _string(self, key):
        self.vars[key] = tk.StringVar(self.root)
        return self.vars[key]

    def _bool(self, key):
        self.vars[key] = tk.BooleanVar(self.root)
        return self.vars[key]

    # ------------------------------------------------------------------ tabs
    def _build_account_tab(self, nb):
        f = self._tab(nb)

        cred_group = ttk.LabelFrame(f, text=" Discord Authentication ", padding=10)
        cred_group.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        cred_group.columnconfigure(1, weight=1)

        token_box = ttk.Frame(cred_group)
        self.token_entry = ttk.Entry(token_box, textvariable=self._string('token'), show='•', width=54)
        self.token_entry.pack(side='left')
        self.show_token = tk.BooleanVar(self.root, value=False)
        ttk.Checkbutton(
            token_box, text="Show", variable=self.show_token,
            command=lambda: self.token_entry.config(show='' if self.show_token.get() else '•')
        ).pack(side='left', padx=(8, 0))

        self._row(
            cred_group, 0, "Discord Token", token_box,
            "User token of the Discord account that rolls. Stored locally in settings.json (gitignored)."
        )

        target_group = ttk.LabelFrame(f, text=" Target Discord Location ", padding=10)
        target_group.grid(row=1, column=0, sticky='ew')
        target_group.columnconfigure(1, weight=1)

        r = self._row(
            target_group, 0, "Channel ID",
            ttk.Entry(target_group, textvariable=self._string('channelId'), width=28),
            "Right-click the target text channel in Discord -> Copy Channel ID (Developer Mode enabled)."
        )
        r = self._row(
            target_group, r, "Server ID",
            ttk.Entry(target_group, textvariable=self._string('serverId'), width=28),
            "Right-click the Discord server icon -> Copy Server ID."
        )
        return f

    def _build_rolling_tab(self, nb):
        f = self._tab(nb)

        sched_group = ttk.LabelFrame(f, text=" Roll Schedule & Pacing ", padding=10)
        sched_group.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        sched_group.columnconfigure(1, weight=1)

        r = self._row(
            sched_group, 0, "Roll command",
            ttk.Combobox(sched_group, textvariable=self._string('rollCommand'), values=ROLL_COMMANDS, width=10),
            "Slash command used to roll (w = waifu, h = husbando, m = both; x/a/g = all/anime/game)."
        )
        r = self._row(
            sched_group, r, "Roll at minute (0-59)",
            ttk.Spinbox(sched_group, textvariable=self._string('repeatMinute'), from_=0, to=59, width=10, wrap=True),
            "Scheduled minute of every hour when the roll session starts (e.g. 39 runs at XX:39)."
        )
        r = self._row(
            sched_group, r, "Delay between rolls (s)",
            ttk.Spinbox(sched_group, textvariable=self._string('rollDelay'), from_=0.5, to=30, increment=0.1, width=10),
            "Base delay in seconds between consecutive rolls (recommended: 1.8 - 2.5s)."
        )
        r = self._row(
            sched_group, r, "Random jitter (+/- s)",
            ttk.Spinbox(sched_group, textvariable=self._string('randomJitter'), from_=0, to=10, increment=0.1, width=10),
            "Randomized variance added to the roll delay to avoid fixed-interval patterns."
        )
        r = self._row(
            sched_group, r, "Max rolls per session",
            ttk.Spinbox(sched_group, textvariable=self._string('maxRollsPerSession'), from_=1, to=500, width=10),
            "Safety cap. A session normally concludes automatically as soon as Mudae reports 0 rolls left."
        )
        r = self._row(
            sched_group, r, "",
            ttk.Checkbutton(sched_group, text="Run a roll session immediately when Bot.py starts",
                            variable=self._bool('runOnStartup'))
        )

        bonus_group = ttk.LabelFrame(f, text=" Bonus & Daily Commands ", padding=10)
        bonus_group.grid(row=1, column=0, sticky='ew')
        bonus_group.columnconfigure(1, weight=1)

        r = 0
        r = self._row(
            bonus_group, r, "",
            ttk.Checkbutton(bonus_group, text="Roll Pokeslot ($p) after session",
                            variable=self._bool('pokeRoll'))
        )
        r = self._row(
            bonus_group, r, "",
            ttk.Checkbutton(bonus_group, text="Claim Daily rolls ($daily) after session",
                            variable=self._bool('dailyRoll'))
        )

        dk_var = self._bool('dailyKakera')
        r = self._row(
            bonus_group, r, "",
            ttk.Checkbutton(bonus_group, text="Claim Daily Kakera ($dk) when power is low",
                            variable=dk_var, command=self._update_dk_spinbox_state)
        )
        self.dk_threshold_spinbox = ttk.Spinbox(
            bonus_group, textvariable=self._string('dkPowerThreshold'), from_=1, to=100, width=10
        )
        r = self._row(
            bonus_group, r, "Daily kakera power threshold (%)",
            self.dk_threshold_spinbox,
            "Only executes $dk when live kakera power (via $tu) is strictly below this percentage (default: 15%)."
        )
        return f

    def _update_dk_spinbox_state(self):
        if hasattr(self, 'dk_threshold_spinbox') and 'dailyKakera' in self.vars:
            state = 'normal' if self.vars['dailyKakera'].get() else 'disabled'
            self.dk_threshold_spinbox.config(state=state)

    def _list_box(self, parent, key, title, hint):
        box = ttk.LabelFrame(parent, text=f" {title} (0) ", padding=8)
        self.list_frames[key] = (box, title)

        # Toolbar for sorting/deduplicating and clearing
        toolbar = ttk.Frame(box)
        toolbar.pack(side='top', fill='x', pady=(0, 4))
        ttk.Button(
            toolbar, text="Sort & Deduplicate", style='Small.TButton',
            command=lambda k=key: self._sort_and_dedupe_list(k)
        ).pack(side='left')
        ttk.Button(
            toolbar, text="Clear", style='Small.TButton',
            command=lambda k=key: self._clear_list(k)
        ).pack(side='right')

        # Hint at bottom
        ttk.Label(box, text=hint, style='Hint.TLabel', wraplength=290, justify='left') \
            .pack(side='bottom', anchor='w', pady=(6, 0))

        # Text editor + scrollbar
        editor_frame = ttk.Frame(box)
        editor_frame.pack(side='top', fill='both', expand=True)

        text = tk.Text(
            editor_frame, height=8, width=28, wrap='none', undo=True,
            font=('Segoe UI', 9), relief='solid', borderwidth=1, padx=4, pady=4
        )
        scroll = ttk.Scrollbar(editor_frame, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)

        text.bind('<KeyRelease>', lambda e, k=key: self._on_list_modified(k))
        self.lists[key] = text
        return box

    def _update_list_counts(self):
        for key, (box, base_title) in self.list_frames.items():
            text_widget = self.lists.get(key)
            if text_widget:
                lines = [ln.strip() for ln in text_widget.get('1.0', 'end').splitlines() if ln.strip()]
                box.config(text=f" {base_title} ({len(lines)}) ")

    def _on_list_modified(self, key):
        self._update_list_counts()
        self._on_field_changed()

    def _sort_and_dedupe_list(self, key):
        text_widget = self.lists.get(key)
        if not text_widget:
            return
        raw_lines = [ln.strip() for ln in text_widget.get('1.0', 'end').splitlines() if ln.strip()]
        seen = set()
        unique = []
        for ln in raw_lines:
            norm = ln.lower()
            if norm not in seen:
                seen.add(norm)
                unique.append(ln)
        unique.sort(key=lambda s: s.lower())
        text_widget.delete('1.0', 'end')
        text_widget.insert('1.0', '\n'.join(unique))
        self._on_list_modified(key)

    def _clear_list(self, key):
        text_widget = self.lists.get(key)
        if not text_widget:
            return
        content = text_widget.get('1.0', 'end').strip()
        if content and messagebox.askyesno("Clear list", "Remove all entries from this list?", parent=self.root):
            text_widget.delete('1.0', 'end')
            self._on_list_modified(key)

    def _build_claim_tab(self, nb):
        f = self._tab(nb)

        rules_group = ttk.LabelFrame(f, text=" Claim Rules & Timer Cooldowns ", padding=10)
        rules_group.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        rules_group.columnconfigure(1, weight=1)

        r = self._row(
            rules_group, 0, "",
            ttk.Checkbutton(rules_group, text="Claim EVERY unclaimed card rolled (overrides filters below)",
                            variable=self._bool('claimAllUnclaimed'))
        )
        r = self._row(
            rules_group, r, "Claim if kakera value >=",
            ttk.Spinbox(rules_group, textvariable=self._string('minPowerToClaim'), from_=0, to=100000,
                        increment=50, width=10),
            "0 disables minimum kakera value claiming."
        )
        r = self._row(
            rules_group, r, "Claim reaction emoji",
            ttk.Combobox(rules_group, textvariable=self._string('claimEmoji'), values=list(CLAIM_EMOJIS), width=16),
            "Select from list or paste a custom emoji."
        )
        r = self._row(
            rules_group, r, "$rt cooldown (hours)",
            ttk.Spinbox(rules_group, textvariable=self._string('rtCooldownHours'), from_=0.1, to=24.0, increment=0.5, width=10),
            "Base 20h, select how much rt cooldown you have. Persisted in bot_state.json across restarts."
        )
        r = self._row(
            rules_group, r, "",
            ttk.Checkbutton(rules_group, text="Auto-use $rt if a wishlist character drops while claim is on cooldown",
                            variable=self._bool('autoRtOnWishlist'))
        )
        r = self._row(
            rules_group, r, "",
            ttk.Checkbutton(rules_group, text="Auto-sync timers with Mudae ($tu) on start and every hour",
                            variable=self._bool('checkTuOnStartup'))
        )

        lists = ttk.Frame(f)
        lists.grid(row=1, column=0, sticky='nsew')
        f.rowconfigure(1, weight=1)
        lists.columnconfigure((0, 1), weight=1, uniform='lists')
        lists.rowconfigure(0, weight=1)

        char_hint = "One per line. Case-insensitive exact name match (e.g. 'Rem' only matches 'Rem', not 'Remilia')."
        series_hint = "One per line. Case-insensitive whole-word or prefix match (e.g. 'Fate' matches 'Fate/stay night')."
        self._list_box(lists, 'desiredCharacters', "Characters to claim", char_hint) \
            .grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        self._list_box(lists, 'desiredSeries', "Series to claim", series_hint) \
            .grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        return f

    def _create_swatch_checkbox(self, parent, name: str, display_text: str, var: tk.BooleanVar):
        cell = ttk.Frame(parent)
        color = BUTTON_SWATCH_COLORS.get(name, '#888888')
        swatch = tk.Canvas(cell, width=10, height=10, highlightthickness=1, highlightbackground='#555555')
        swatch.create_rectangle(0, 0, 10, 10, fill=color, outline='')
        swatch.pack(side='left', padx=(0, 4))
        ttk.Checkbutton(cell, text=display_text, variable=var, width=19).pack(side='left')
        return cell

    def _build_kakera_tab(self, nb):
        f = self._tab(nb)
        cols = 3

        # 1. Standard Kakera group
        k_frame = ttk.LabelFrame(f, text=" Standard Kakera Buttons (Ordered by Priority) ", padding=8)
        k_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        for c in range(cols):
            k_frame.columnconfigure(c, weight=1)
        for i, name in enumerate(KNOWN_KAKERAS):
            var = tk.BooleanVar(self.root)
            self.kakera_vars[name] = var
            display_text = KAKERA_DISPLAY_NAMES.get(name, name)
            cell = self._create_swatch_checkbox(k_frame, name, display_text, var)
            cell.grid(row=i // cols, column=i % cols, sticky='w', padx=(0, 8), pady=2)

        # 2. Ourospheres group
        s_frame = ttk.LabelFrame(f, text=" Ourospheres (Perk 9 / Sphere Buttons) ", padding=8)
        s_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        for c in range(cols):
            s_frame.columnconfigure(c, weight=1)
        for i, name in enumerate(KNOWN_SPHERES):
            var = tk.BooleanVar(self.root)
            self.kakera_vars[name] = var
            display_text = SPHERE_DISPLAY_NAMES.get(name, name)
            cell = self._create_swatch_checkbox(s_frame, name, display_text, var)
            cell.grid(row=i // cols, column=i % cols, sticky='w', padx=(0, 8), pady=2)

        # Quick Selection Toolbar
        btns = ttk.Frame(f)
        btns.grid(row=2, column=0, columnspan=2, sticky='w', pady=(0, 8))
        ttk.Button(btns, text="All Kakera", command=lambda: self._set_kakeras_group(KNOWN_KAKERAS, True)).pack(side='left')
        ttk.Button(btns, text="Clear Kakera", command=lambda: self._set_kakeras_group(KNOWN_KAKERAS, False)).pack(side='left', padx=(4, 10))
        ttk.Button(btns, text="All Spheres", command=lambda: self._set_kakeras_group(KNOWN_SPHERES, True)).pack(side='left')
        ttk.Button(btns, text="Clear Spheres", command=lambda: self._set_kakeras_group(KNOWN_SPHERES, False)).pack(side='left', padx=(4, 10))
        ttk.Button(btns, text="Select All", command=lambda: self._set_all_kakeras(True)).pack(side='left')
        ttk.Button(btns, text="Clear All", command=lambda: self._set_all_kakeras(False)).pack(side='left', padx=4)

        # Advanced & Perk 8 Options
        adv_frame = ttk.LabelFrame(f, text=" Perk 8 & Custom Button Rules ", padding=8)
        adv_frame.grid(row=3, column=0, columnspan=2, sticky='ew')
        adv_frame.columnconfigure(1, weight=1)

        r = self._row(
            adv_frame, 0, "Custom buttons",
            ttk.Entry(adv_frame, textvariable=self._string('otherKakeras'), width=42),
            "Comma-separated extra button emoji names not listed above (case-insensitive)."
        )
        r = self._row(
            adv_frame, r, "",
            ttk.Checkbutton(
                adv_frame,
                text="Auto-click all kakera buttons on Perk 8 cards (halved power cost and double spheres)",
                variable=self._bool('autoPerkBonusKakera')
            ),
            "Overrides color restrictions on cards with halved power cost or double sphere indicators."
        )
        return f

    def _set_kakeras_group(self, group: list, value: bool):
        for name in group:
            if name in self.kakera_vars:
                self.kakera_vars[name].set(value)

    def _set_all_kakeras(self, value: bool):
        for var in self.kakera_vars.values():
            var.set(value)

    # --------------------------------------------------------- live state bar
    def _refresh_live_state(self):
        if not os.path.isfile(STATE_FILE):
            self.live_state_label.config(text="No bot_state.json found yet. Run Bot.py to synchronize with Mudae ($tu).")
            return
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                st = json.load(f)
            now = time.time()

            def fmt_cd(avail_key, ready_at_key):
                if st.get(avail_key) is True:
                    return "READY"
                ready_at = st.get(ready_at_key, 0.0) or 0.0
                if ready_at > now:
                    rem = int(ready_at - now)
                    return f"{rem // 3600}h {(rem % 3600) // 60:02d}m"
                if st.get(avail_key) is False:
                    return "Cooldown"
                return "Unknown"

            claim_str = fmt_cd('claim_available', 'claim_ready_at')
            rt_str = fmt_cd('rt_available', 'rt_ready_at')
            dk_str = fmt_cd('dk_available', 'dk_ready_at')
            pwr = st.get('kakera_power')
            pwr_str = f"{pwr}%" if pwr is not None else "Unknown"
            last_sync = st.get('last_tu_sync', 0.0)
            sync_str = time.strftime('%H:%M:%S', time.localtime(last_sync)) if last_sync > 0 else "Never"

            summary = f"Claim: {claim_str}   |   $rt: {rt_str}   |   $dk: {dk_str}   |   Power: {pwr_str}   |   Last $tu sync: {sync_str}"
            self.live_state_label.config(text=summary)
        except Exception:
            self.live_state_label.config(text="Could not read bot_state.json.")

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

        self._update_list_counts()
        self._update_dk_spinbox_state()

    def _form_state(self):
        """Raw snapshot of every field, used to detect unsaved changes."""
        return (
            tuple((k, str(v.get())) for k, v in sorted(self.vars.items())),
            tuple((k, t.get('1.0', 'end-1c')) for k, t in sorted(self.lists.items())),
            tuple((k, v.get()) for k, v in sorted(self.kakera_vars.items())),
        )

    def _on_field_changed(self):
        if self._snapshot is None:
            return
        if self._has_unsaved_changes():
            self._set_status("* Unsaved changes", style='StatusDirty.TLabel')
        else:
            self._set_status("All changes saved.", style='Hint.TLabel')

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
        for key in (
            'runOnStartup', 'pokeRoll', 'dailyKakera', 'dailyRoll',
            'autoRtOnWishlist', 'checkTuOnStartup', 'claimAllUnclaimed', 'autoPerkBonusKakera'
        ):
            s[key] = bool(self.vars[key].get())
        for key, text in self.lists.items():
            s[key] = [line.strip() for line in text.get('1.0', 'end').splitlines() if line.strip()]

        others = [k.strip() for k in self.vars['otherKakeras'].get().replace(';', ',').split(',') if k.strip()]
        s['desiredKakeras'] = [k for k in ALL_KNOWN_BUTTONS if self.kakera_vars[k].get()] + others
        return s

    # ----------------------------------------------------------------- actions
    def _set_status(self, msg: str, style: str = 'Hint.TLabel'):
        self.status.config(text=msg, style=style)

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
            text = "\n".join(f"* {i}" for i in issues)
            if not messagebox.askyesno("Check your settings", f"{text}\n\nSave anyway?",
                                       icon='warning', parent=self.root):
                return False
        try:
            Vars.save_settings(settings)
        except OSError as e:
            messagebox.showerror("Save failed", f"Could not write settings file:\n{e}", parent=self.root)
            return False

        self._snapshot = self._form_state()
        self._set_status(f"Saved at {time.strftime('%H:%M:%S')} (active automatically in Bot.py).", style='StatusOk.TLabel')
        return True

    def reload(self):
        if self._has_unsaved_changes() and not messagebox.askyesno(
                "Discard changes?", "Discard unsaved changes and reload from disk?", parent=self.root):
            return
        self.load_into_form(Vars.get_file_settings())
        self._snapshot = self._form_state()
        self._refresh_live_state()
        self._set_status("Reloaded from disk.", style='Hint.TLabel')

    def reset_defaults(self):
        if not messagebox.askyesno(
                "Reset to defaults",
                "Reset all rolling, claim and kakera settings to their defaults?\n"
                "Your token, channel ID and server ID are kept.\n\nNothing is saved until you click Save.",
                parent=self.root):
            return
        self.load_into_form(Vars.DEFAULTS, skip_keys=ACCOUNT_KEYS)
        self._set_status("Defaults loaded (click Save to apply).", style='StatusDirty.TLabel')

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
