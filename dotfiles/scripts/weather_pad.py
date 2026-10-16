#!/usr/bin/env python3
"""
Weather Pad - Desktop Weather & Forecast Dropdown for Qtile
============================================================
A fast, keyboard-driven weather dashboard styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Live weather and 3-day forecast for Denver, CO from wttr.in JSON API
- Offline caching (~/.cache/weather/forecast.json) for 0ms instantaneous startup
- Non-blocking asynchronous threading with thread-safe UI updates (root.after)
- Current conditions hero card: Temp (F/C), Feels Like, Humidity, Wind, UV, Pressure
- 3-Day forecast cards with Day/Date, condition glyphs, High/Low, and rain chance
- 8-slot hourly timeline for the selected forecast day (12 AM - 9 PM)
- Full Vim-style and arrow-key navigation:
    h / l or Left / Right : Select Previous / Next Forecast Day
    t                     : Jump to Today
    r                     : Force sync / refresh from wttr.in
    q / Esc               : Dismiss dropdown
- Native X11 WM_CLASS ("weather-pad") for Qtile ScratchPad integration
- Full dynamic Gruvbox Dark / Light theme support via theme.py
"""

import sys
import os
import json
import time
import datetime
import urllib.request
import threading
import tkinter as tk
from tkinter import font as tkfont

# ==============================================================================
# Theme: Central Gruvbox (Dark / Light via Super + o)
# ==============================================================================
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from theme import get_theme
    THEME = get_theme()
except Exception:
    THEME = {
        "bg": "#282828",
        "bg_surface": "#32302f",
        "bg_card": "#3c3836",
        "bg_hover": "#504945",
        "bg_active": "#665c54",
        "bg_selected": "#3c3836",
        "border": "#504945",
        "border_focus": "#83a598",
        "border_today": "#fabd2f",
        "fg": "#ebdbb2",
        "fg_dim": "#a89984",
        "fg_header": "#fbf1c7",
        "key_bg": "#1d2021",
        "key_fg": "#fabd2f",
        "status_running": "#b8bb26",
        "status_stopped": "#fb4934",
        "status_paused": "#fabd2f",
        "accent_blue": "#83a598",
        "accent_aqua": "#8ec07c",
        "accent_green": "#b8bb26",
        "accent_yellow": "#fabd2f",
        "accent_orange": "#fe8019",
        "accent_purple": "#d3869b",
        "accent_red": "#fb4934",
    }

CACHE_DIR = os.path.expanduser("~/.cache/weather")
CACHE_FILE = os.path.join(CACHE_DIR, "forecast.json")
API_URL = "https://wttr.in/Denver?format=j1"


# ==============================================================================
# FontAwesome Weather Glyph Mapper
# ==============================================================================
def get_weather_icon(desc_text: str) -> tuple[str, str]:
    """
    Maps weather description strings to FontAwesome Unicode glyphs and theme colors.
    Returns: (glyph, theme_color_key)
    """
    text = (desc_text or "").lower()
    if any(k in text for k in ("thunder", "lightning", "storm")):
        return ("\uf0e7", "accent_purple")       # fa-bolt
    elif any(k in text for k in ("snow", "blizzard", "sleet", "ice", "hail")):
        return ("\uf2dc", "accent_blue")         # fa-snowflake-o
    elif any(k in text for k in ("heavy rain", "torrential", "shower")):
        return ("\uf0e9", "accent_aqua")         # fa-umbrella
    elif any(k in text for k in ("rain", "drizzle", "patchy rain")):
        return ("\uf0e9", "accent_aqua")         # fa-umbrella
    elif any(k in text for k in ("fog", "mist", "haze")):
        return ("\uf070", "fg_dim")              # fa-eye-slash
    elif any(k in text for k in ("partly cloudy", "scattered clouds")):
        return ("\uf0c2", "accent_yellow")       # fa-cloud (warm)
    elif any(k in text for k in ("cloud", "overcast")):
        return ("\uf0c2", "fg_dim")              # fa-cloud
    elif any(k in text for k in ("sunny", "clear")):
        return ("\uf185", "accent_yellow")       # fa-sun-o
    return ("\uf0c2", "fg")                      # default cloud


def format_hour_time(time_str: str) -> str:
    """Converts wttr.in time strings (e.g. '0', '300', '1200', '2100') to '12 AM', '3 PM'."""
    try:
        val = int(time_str)
        hour = val // 100
        if hour == 0:
            return "12 AM"
        elif hour < 12:
            return f"{hour} AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"
    except Exception:
        return time_str


# ==============================================================================
# Weather Data Manager (Fetch & Cache)
# ==============================================================================
class WeatherManager:
    """Handles fetching, caching, and parsing wttr.in JSON data."""

    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.data: dict | None = self._load_cache()
        self.last_fetch_time: float = self._get_cache_mtime()
        self.is_fetching = False

    def _get_cache_mtime(self) -> float:
        if os.path.exists(CACHE_FILE):
            try:
                return os.path.getmtime(CACHE_FILE)
            except Exception:
                pass
        return 0.0

    def _load_cache(self) -> dict | None:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_cache(self, data: dict):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.last_fetch_time = time.time()
        except Exception:
            pass

    def fetch_async(self, callback):
        """Asynchronously fetches weather data from wttr.in in a daemon thread."""
        if self.is_fetching:
            return
        self.is_fetching = True

        def _worker():
            err_msg = None
            result_data = None
            try:
                req = urllib.request.Request(
                    API_URL,
                    headers={"User-Agent": "QtileWeatherPad/1.0 (Linux; x86_64)"},
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw_content = resp.read().decode("utf-8", errors="replace")
                    result_data = json.loads(raw_content)
                    self.data = result_data
                    self._save_cache(result_data)
            except Exception as e:
                err_msg = str(e)
            finally:
                self.is_fetching = False
                if callback:
                    callback(result_data is not None, result_data or self.data, err_msg)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()


# ==============================================================================
# Main Weather Dropdown Application
# ==============================================================================
class WeatherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Denver Weather")
        self.root.configure(bg=THEME["bg"])

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        # Target dimensions matching other bench pads (80% width x 88% height)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = min(1500, int(sw * 0.8))
        target_h = int(sh * 0.88)
        self.root.geometry(f"{target_w}x{target_h}")

        self.manager = WeatherManager()
        self.selected_day_idx = 0  # 0: Today, 1: Tomorrow, 2: Day After

        # UI Widget references
        self.day_card_frames: list[tk.Frame] = []
        self.day_card_labels: list[dict[str, tk.Label]] = []
        self.hourly_slot_frames: list[tk.Frame] = []

        self._build_header()
        self._build_main_content()
        self._build_footer()
        self._bind_keys()

        # Initial render with cached data (0ms startup)
        if self.manager.data:
            self._render_weather_data(self.manager.data)

        # Trigger background refresh
        self.trigger_refresh()

    # --------------------------------------------------------------------------
    # UI Building
    # --------------------------------------------------------------------------
    def _build_header(self):
        """Build top navigation and location status bar."""
        header_frame = tk.Frame(self.root, bg=THEME["bg_surface"], height=52)
        header_frame.pack(fill="x", side="top", padx=16, pady=(14, 10))
        header_frame.pack_propagate(False)

        # Left: Location Title
        loc_frame = tk.Frame(header_frame, bg=THEME["bg_surface"])
        loc_frame.pack(side="left", padx=14, pady=8)

        loc_icon = tk.Label(
            loc_frame,
            text="\uf041",  # fa-map-marker
            font=("FontAwesome", 16),
            fg=THEME["accent_red"],
            bg=THEME["bg_surface"],
        )
        loc_icon.pack(side="left", padx=(0, 8))

        self.lbl_location = tk.Label(
            loc_frame,
            text="Denver, Colorado",
            font=("DejaVu Sans", 13, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_surface"],
        )
        self.lbl_location.pack(side="left")

        # Right: Sync Status & Refresh Button
        status_box = tk.Frame(header_frame, bg=THEME["bg_surface"])
        status_box.pack(side="right", padx=14, pady=8)

        self.lbl_status = tk.Label(
            status_box,
            text="Checking forecast...",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
        )
        self.lbl_status.pack(side="left", padx=(0, 14))

        self.btn_refresh = tk.Button(
            status_box,
            text="\uf021 Refresh (r)",  # fa-refresh
            font=("FontAwesome", 9, "bold"),
            fg=THEME["key_bg"],
            bg=THEME["status_running"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.trigger_refresh,
        )
        self.btn_refresh.pack(side="left", padx=(0, 8))

        btn_close = tk.Button(
            status_box,
            text="\uf00d",  # fa-times
            font=("FontAwesome", 10),
            fg=THEME["fg_dim"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.root.destroy,
        )
        btn_close.pack(side="left")

    def _build_main_content(self):
        """Builds Hero Card, 3-Day Forecast Cards, and Hourly Timeline."""
        self.main_container = tk.Frame(self.root, bg=THEME["bg"])
        self.main_container.pack(fill="both", expand=True, padx=16, pady=4)

        # 1. Current Conditions Hero Card
        self._build_hero_card()

        # 2. 3-Day Forecast Cards Grid
        self._build_forecast_section()

        # 3. Hourly Timeline for Selected Day
        self._build_hourly_section()

    def _build_hero_card(self):
        """Top card: Current live temperature, weather icon, and atmospheric metrics."""
        self.hero_card = tk.Frame(
            self.main_container,
            bg=THEME["bg_card"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
            padx=20,
            pady=16,
        )
        self.hero_card.pack(fill="x", pady=(0, 12))

        # Split into Left (Huge Temp + Condition) and Right (Metrics 2x3 Grid)
        left_hero = tk.Frame(self.hero_card, bg=THEME["bg_card"])
        left_hero.pack(side="left", fill="y", padx=(10, 30))

        # Huge Weather Icon + Temp Display
        temp_row = tk.Frame(left_hero, bg=THEME["bg_card"])
        temp_row.pack(anchor="w")

        self.lbl_hero_icon = tk.Label(
            temp_row,
            text="\uf185",  # fa-sun-o
            font=("FontAwesome", 42),
            fg=THEME["accent_yellow"],
            bg=THEME["bg_card"],
        )
        self.lbl_hero_icon.pack(side="left", padx=(0, 18))

        temp_text_col = tk.Frame(temp_row, bg=THEME["bg_card"])
        temp_text_col.pack(side="left")

        self.lbl_hero_temp_f = tk.Label(
            temp_text_col,
            text="--°F",
            font=("DejaVu Sans", 34, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        self.lbl_hero_temp_f.pack(anchor="w")

        self.lbl_hero_temp_c = tk.Label(
            temp_text_col,
            text="(--°C)",
            font=("DejaVu Sans", 13),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
        )
        self.lbl_hero_temp_c.pack(anchor="w")

        # Condition Description & Feels Like
        self.lbl_hero_desc = tk.Label(
            left_hero,
            text="Loading conditions...",
            font=("DejaVu Sans", 13, "bold"),
            fg=THEME["accent_blue"],
            bg=THEME["bg_card"],
        )
        self.lbl_hero_desc.pack(anchor="w", pady=(6, 2))

        self.lbl_hero_feels = tk.Label(
            left_hero,
            text="Feels like: --°F",
            font=("DejaVu Sans Mono", 10),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
        )
        self.lbl_hero_feels.pack(anchor="w")

        # Right: 6 Atmospheric Metrics Grid
        right_metrics = tk.Frame(self.hero_card, bg=THEME["bg_card"])
        right_metrics.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # Metric badges: Humidity, Wind, UV Index, Pressure, Visibility, Precip
        self.metric_labels: dict[str, tk.Label] = {}
        metric_configs = [
            ("humidity", "\uf043", "Humidity", THEME["accent_aqua"]),       # fa-tint
            ("wind", "\uf14e", "Wind", THEME["accent_green"]),              # fa-compass
            ("uv", "\uf185", "UV Index", THEME["accent_yellow"]),           # fa-sun-o
            ("pressure", "\uf0e4", "Pressure", THEME["accent_orange"]),     # fa-tachometer
            ("visibility", "\uf06e", "Visibility", THEME["accent_blue"]),   # fa-eye
            ("precip", "\uf0e9", "Precipitation", THEME["accent_purple"]),  # fa-umbrella
        ]

        for i, (key, glyph, title, color) in enumerate(metric_configs):
            row = i // 3
            col = i % 3

            pill = tk.Frame(
                right_metrics,
                bg=THEME["bg_surface"],
                highlightbackground=THEME["border"],
                highlightthickness=1,
                padx=12,
                pady=8,
            )
            pill.grid(row=row, column=col, padx=6, pady=5, sticky="nsew")
            right_metrics.grid_columnconfigure(col, weight=1)

            pill_title_box = tk.Frame(pill, bg=THEME["bg_surface"])
            pill_title_box.pack(anchor="w")

            tk.Label(
                pill_title_box,
                text=glyph,
                font=("FontAwesome", 10),
                fg=color,
                bg=THEME["bg_surface"],
            ).pack(side="left", padx=(0, 6))

            tk.Label(
                pill_title_box,
                text=title,
                font=("DejaVu Sans Mono", 9),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            ).pack(side="left")

            val_lbl = tk.Label(
                pill,
                text="--",
                font=("DejaVu Sans", 11, "bold"),
                fg=THEME["fg"],
                bg=THEME["bg_surface"],
            )
            val_lbl.pack(anchor="w", pady=(3, 0))
            self.metric_labels[key] = val_lbl

    def _build_forecast_section(self):
        """Middle: 3-Day Forecast Cards."""
        section_lbl = tk.Label(
            self.main_container,
            text="\uf073  3-DAY EXTENDED FORECAST (Use 'h' / 'l' to select day)",
            font=("FontAwesome", 10, "bold"),
            fg=THEME["accent_yellow"],
            bg=THEME["bg"],
        )
        section_lbl.pack(anchor="w", pady=(0, 6))

        cards_box = tk.Frame(self.main_container, bg=THEME["bg"])
        cards_box.pack(fill="x", pady=(0, 14))

        for idx in range(3):
            card = tk.Frame(
                cards_box,
                bg=THEME["bg_card"],
                highlightbackground=THEME["border"],
                highlightthickness=2,
                padx=14,
                pady=10,
                cursor="hand2",
            )
            card.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else 8, 0))
            self.day_card_frames.append(card)

            # Click binding to select forecast day
            card.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            # Header: Day Name + Date
            lbl_title = tk.Label(
                card,
                text=f"Day {idx + 1}",
                font=("DejaVu Sans", 11, "bold"),
                fg=THEME["fg_header"],
                bg=THEME["bg_card"],
            )
            lbl_title.pack(anchor="w")
            lbl_title.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            lbl_date = tk.Label(
                card,
                text="--",
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_card"],
            )
            lbl_date.pack(anchor="w", pady=(1, 6))
            lbl_date.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            # Icon & High/Low Temps
            content_row = tk.Frame(card, bg=THEME["bg_card"])
            content_row.pack(fill="x", pady=2)
            content_row.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            lbl_icon = tk.Label(
                content_row,
                text="\uf185",
                font=("FontAwesome", 24),
                fg=THEME["accent_yellow"],
                bg=THEME["bg_card"],
            )
            lbl_icon.pack(side="left", padx=(0, 12))
            lbl_icon.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            temps_col = tk.Frame(content_row, bg=THEME["bg_card"])
            temps_col.pack(side="left")
            temps_col.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            lbl_high_low = tk.Label(
                temps_col,
                text="High: --°F  Low: --°F",
                font=("DejaVu Sans", 10, "bold"),
                fg=THEME["fg"],
                bg=THEME["bg_card"],
            )
            lbl_high_low.pack(anchor="w")
            lbl_high_low.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            lbl_condition = tk.Label(
                temps_col,
                text="--",
                font=("DejaVu Sans", 9),
                fg=THEME["accent_blue"],
                bg=THEME["bg_card"],
            )
            lbl_condition.pack(anchor="w")
            lbl_condition.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            # Rain / Sun info badge
            lbl_details = tk.Label(
                card,
                text="Precip: --",
                font=("DejaVu Sans Mono", 9),
                fg=THEME["fg_dim"],
                bg=THEME["bg_card"],
            )
            lbl_details.pack(anchor="w", pady=(6, 0))
            lbl_details.bind("<Button-1>", lambda e, i=idx: self.select_day(i))

            self.day_card_labels.append({
                "title": lbl_title,
                "date": lbl_date,
                "icon": lbl_icon,
                "high_low": lbl_high_low,
                "condition": lbl_condition,
                "details": lbl_details,
            })

    def _build_hourly_section(self):
        """Bottom: Hourly timeline breakdown for the selected forecast day."""
        self.lbl_hourly_heading = tk.Label(
            self.main_container,
            text="\uf017  HOURLY TIMELINE - TODAY",
            font=("FontAwesome", 10, "bold"),
            fg=THEME["accent_aqua"],
            bg=THEME["bg"],
        )
        self.lbl_hourly_heading.pack(anchor="w", pady=(0, 6))

        self.hourly_container = tk.Frame(
            self.main_container,
            bg=THEME["bg_card"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
            padx=10,
            pady=12,
        )
        self.hourly_container.pack(fill="both", expand=True)

        self.hourly_slots_box = tk.Frame(self.hourly_container, bg=THEME["bg_card"])
        self.hourly_slots_box.pack(fill="both", expand=True)

        # 8 Slots across the width (12 AM, 3 AM, 6 AM, 9 AM, 12 PM, 3 PM, 6 PM, 9 PM)
        self.hourly_slot_widgets = []
        for i in range(8):
            slot = tk.Frame(
                self.hourly_slots_box,
                bg=THEME["bg_surface"],
                highlightbackground=THEME["border"],
                highlightthickness=1,
                padx=6,
                pady=8,
            )
            slot.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))

            lbl_time = tk.Label(
                slot,
                text="--",
                font=("DejaVu Sans Mono", 9, "bold"),
                fg=THEME["accent_yellow"],
                bg=THEME["bg_surface"],
            )
            lbl_time.pack(pady=(0, 4))

            lbl_icon = tk.Label(
                slot,
                text="\uf185",
                font=("FontAwesome", 18),
                fg=THEME["accent_yellow"],
                bg=THEME["bg_surface"],
            )
            lbl_icon.pack(pady=2)

            lbl_temp = tk.Label(
                slot,
                text="--°F",
                font=("DejaVu Sans", 11, "bold"),
                fg=THEME["fg_header"],
                bg=THEME["bg_surface"],
            )
            lbl_temp.pack(pady=2)

            lbl_rain = tk.Label(
                slot,
                text="0% Rain",
                font=("DejaVu Sans Mono", 8),
                fg=THEME["accent_aqua"],
                bg=THEME["bg_surface"],
            )
            lbl_rain.pack(pady=(2, 0))

            lbl_wind = tk.Label(
                slot,
                text="-- mph",
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            )
            lbl_wind.pack(pady=(1, 0))

            self.hourly_slot_widgets.append({
                "time": lbl_time,
                "icon": lbl_icon,
                "temp": lbl_temp,
                "rain": lbl_rain,
                "wind": lbl_wind,
            })

    def _build_footer(self):
        """Bottom keybindings cheat-sheet footer bar."""
        footer_frame = tk.Frame(self.root, bg=THEME["bg_surface"], height=38)
        footer_frame.pack(fill="x", side="bottom", padx=16, pady=(0, 12))
        footer_frame.pack_propagate(False)

        shortcuts = [
            ("r", "Refresh"),
            ("h / l", "Select Day"),
            ("t", "Today"),
            ("q / Esc", "Dismiss"),
        ]

        box = tk.Frame(footer_frame, bg=THEME["bg_surface"])
        box.pack(side="left", padx=14, pady=6)

        for key, desc in shortcuts:
            k_badge = tk.Label(
                box,
                text=key,
                font=("DejaVu Sans Mono", 9, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=6,
                pady=2,
            )
            k_badge.pack(side="left", padx=(0, 4))

            d_lbl = tk.Label(
                box,
                text=desc,
                font=("DejaVu Sans Mono", 9),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            )
            d_lbl.pack(side="left", padx=(0, 16))

    # --------------------------------------------------------------------------
    # Event Handlers & Keybindings
    # --------------------------------------------------------------------------
    def _bind_keys(self):
        """Bind keyboard controls for fast navigation."""
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("q", lambda e: self.root.destroy())
        self.root.bind("Q", lambda e: self.root.destroy())
        self.root.bind("r", lambda e: self.trigger_refresh())
        self.root.bind("R", lambda e: self.trigger_refresh())
        self.root.bind("h", lambda e: self.select_day(self.selected_day_idx - 1))
        self.root.bind("<Left>", lambda e: self.select_day(self.selected_day_idx - 1))
        self.root.bind("l", lambda e: self.select_day(self.selected_day_idx + 1))
        self.root.bind("<Right>", lambda e: self.select_day(self.selected_day_idx + 1))
        self.root.bind("t", lambda e: self.select_day(0))
        self.root.bind("T", lambda e: self.select_day(0))

    def select_day(self, idx: int):
        """Select a forecast day (0: Today, 1: Tomorrow, 2: Day After) and update hourly timeline."""
        if idx < 0 or idx > 2:
            return
        self.selected_day_idx = idx
        self._highlight_active_card()
        if self.manager.data:
            self._render_hourly_slots(self.manager.data)

    def _highlight_active_card(self):
        """Applies border highlighting to the currently selected forecast day card."""
        for i, card in enumerate(self.day_card_frames):
            if i == self.selected_day_idx:
                card.configure(
                    highlightbackground=THEME["border_focus"],
                    highlightthickness=2,
                )
            else:
                card.configure(
                    highlightbackground=THEME["border"],
                    highlightthickness=2,
                )

    def trigger_refresh(self):
        """Starts background fetch with visual UI indication."""
        self.lbl_status.configure(text="\uf021 Syncing from wttr.in...", fg=THEME["accent_yellow"])
        self.manager.fetch_async(self._on_fetch_complete)

    def _on_fetch_complete(self, success: bool, data: dict | None, err_msg: str | None):
        """Thread-safe callback invoked from background worker."""
        # Dispatch UI update strictly to Tkinter's main event loop thread
        self.root.after(0, self._apply_update, success, data, err_msg)

    def _apply_update(self, success: bool, data: dict | None, err_msg: str | None):
        """Renders fetched data safely in Tkinter's main thread."""
        now_str = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
        if success and data:
            self.lbl_status.configure(
                text=f"✔ Updated {now_str} (wttr.in)",
                fg=THEME["status_running"],
            )
            self._render_weather_data(data)
        else:
            if data:
                self.lbl_status.configure(
                    text=f"⚠️ Offline Cache ({now_str})",
                    fg=THEME["status_paused"],
                )
                self._render_weather_data(data)
            else:
                self.lbl_status.configure(
                    text=f"✖ Network Error: {err_msg or 'Failed to fetch'}",
                    fg=THEME["status_stopped"],
                )

    # --------------------------------------------------------------------------
    # Data Rendering
    # --------------------------------------------------------------------------
    def _render_weather_data(self, data: dict):
        """Populates all UI widgets with parsed weather JSON data."""
        try:
            current = (data.get("current_condition") or [{}])[0]
            weather_days = data.get("weather") or []

            # 1. Update Hero Card
            temp_f = current.get("temp_F", "--")
            temp_c = current.get("temp_C", "--")
            feels_f = current.get("FeelsLikeF", "--")
            desc_list = current.get("weatherDesc") or [{}]
            condition_desc = desc_list[0].get("value", "Clear").strip()

            glyph, color_key = get_weather_icon(condition_desc)
            self.lbl_hero_icon.configure(text=glyph, fg=THEME[color_key])
            self.lbl_hero_temp_f.configure(text=f"{temp_f}°F")
            self.lbl_hero_temp_c.configure(text=f"({temp_c}°C)")
            self.lbl_hero_desc.configure(text=condition_desc)
            self.lbl_hero_feels.configure(text=f"Feels like: {feels_f}°F")

            # Update Metrics
            humidity = current.get("humidity", "--")
            wind_speed = current.get("windspeedMiles", "--")
            wind_dir = current.get("winddir16Point", "")
            uv_index = current.get("uvIndex", "--")
            pressure = current.get("pressure", "--")
            visibility = current.get("visibilityMiles", "--")
            precip = current.get("precipInches", "0.0")

            self.metric_labels["humidity"].configure(text=f"{humidity}%")
            self.metric_labels["wind"].configure(text=f"{wind_dir} {wind_speed} mph")
            self.metric_labels["uv"].configure(text=f"{uv_index}")
            self.metric_labels["pressure"].configure(text=f"{pressure} mb")
            self.metric_labels["visibility"].configure(text=f"{visibility} mi")
            self.metric_labels["precip"].configure(text=f"{precip} in")

            # 2. Update 3-Day Forecast Cards
            day_titles = ["Today", "Tomorrow", "Day After"]
            for idx, day_data in enumerate(weather_days[:3]):
                labels = self.day_card_labels[idx]
                date_str = day_data.get("date", "")
                try:
                    dt_obj = datetime.date.fromisoformat(date_str)
                    display_date = dt_obj.strftime("%A, %b %d")
                    card_title = day_titles[idx] if idx < len(day_titles) else dt_obj.strftime("%A")
                except Exception:
                    display_date = date_str
                    card_title = day_titles[idx]

                max_f = day_data.get("maxtempF", "--")
                min_f = day_data.get("mintempF", "--")

                # Predominant daytime hourly condition (e.g. noon slot)
                hourly_list = day_data.get("hourly") or []
                noon_slot = hourly_list[4] if len(hourly_list) > 4 else (hourly_list[0] if hourly_list else {})
                day_desc = ((noon_slot.get("weatherDesc") or [{}])[0].get("value") or "Clear").strip()
                day_glyph, day_color = get_weather_icon(day_desc)
                rain_chance = noon_slot.get("chanceofrain", "0")
                snow_chance = noon_slot.get("chanceofsnow", "0")
                try:
                    snow_val = int(snow_chance)
                except (ValueError, TypeError):
                    snow_val = 0
                try:
                    rain_val = int(rain_chance)
                except (ValueError, TypeError):
                    rain_val = 0

                precip_summary = f"{snow_val}% Snow" if snow_val > 0 else f"{rain_val}% Rain"

                labels["title"].configure(text=card_title)
                labels["date"].configure(text=display_date)
                labels["icon"].configure(text=day_glyph, fg=THEME[day_color])
                labels["high_low"].configure(text=f"High: {max_f}°F   Low: {min_f}°F")
                labels["condition"].configure(text=day_desc)
                labels["details"].configure(text=f"Precip Chance: {precip_summary}")

            self._highlight_active_card()

            # 3. Update Hourly Slots for selected day
            self._render_hourly_slots(data)

        except Exception as e:
            self.lbl_status.configure(text=f"Parse Error: {e}", fg=THEME["status_stopped"])

    def _render_hourly_slots(self, data: dict):
        """Updates the 8 hourly slots for the currently selected forecast day."""
        weather_days = data.get("weather") or []
        if self.selected_day_idx >= len(weather_days):
            return

        selected_day = weather_days[self.selected_day_idx]
        hourly_data = selected_day.get("hourly") or []
        day_date = selected_day.get("date", "")

        day_names = ["TODAY", "TOMORROW", "DAY AFTER"]
        header_name = day_names[self.selected_day_idx] if self.selected_day_idx < len(day_names) else "EXTENDED"
        self.lbl_hourly_heading.configure(
            text=f"\uf017  HOURLY TIMELINE - {header_name} ({day_date})",
        )

        for slot_idx, slot_widgets in enumerate(self.hourly_slot_widgets):
            if slot_idx < len(hourly_data):
                hour_entry = hourly_data[slot_idx]
                raw_time = hour_entry.get("time", "0")
                time_str = format_hour_time(raw_time)

                h_temp_f = hour_entry.get("tempF", "--")
                h_desc = ((hour_entry.get("weatherDesc") or [{}])[0].get("value") or "Clear").strip()
                h_glyph, h_color = get_weather_icon(h_desc)
                rain_chance = hour_entry.get("chanceofrain", "0")
                snow_chance = hour_entry.get("chanceofsnow", "0")
                wind_speed = hour_entry.get("windspeedMiles", "--")
                try:
                    h_snow_val = int(snow_chance)
                except (ValueError, TypeError):
                    h_snow_val = 0

                precip_text = f"{snow_chance}% Snow" if h_snow_val > 0 else f"{rain_chance}% Rain"

                slot_widgets["time"].configure(text=time_str)
                slot_widgets["icon"].configure(text=h_glyph, fg=THEME[h_color])
                slot_widgets["temp"].configure(text=f"{h_temp_f}°F")
                slot_widgets["rain"].configure(text=precip_text)
                slot_widgets["wind"].configure(text=f"{wind_speed} mph")


# ==============================================================================
# Application Launch Entrypoint
# ==============================================================================
if __name__ == "__main__":
    root = tk.Tk(className="weather-pad")
    app = WeatherApp(root)
    root.mainloop()
