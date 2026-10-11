#!/usr/bin/env python3
"""
Zodiac - Google Calendar Dropdown for Qtile
============================================
A fast, keyboard-driven calendar and agenda dashboard styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Reads directly from Google Calendar via private/secret iCal (.ics) URL
- Offline caching (~/.cache/zodiac/events.json) for 0ms instantaneous startup
- Interactive monthly grid with today & selection highlighting
- Visual event indicators on calendar days with scheduled items
- Chronological daily agenda + automatic upcoming events feed
- In-app URL configuration dialog (press 's')
- Full Vim-style and arrow-key navigation:
    h / l or Left / Right   : Day -1 / +1
    j / k or Down / Up      : Week -1 / +1
    J / K or PgDn / PgUp    : Month +1 / -1
    t                       : Jump to Today
    r                       : Force sync / refresh from Google
    s                       : Settings (Set Calendar URL)
    q / Esc                 : Dismiss dropdown
- Native X11 WM_CLASS ("zodiac-pad") for Qtile ScratchPad integration
"""

import sys
import os
import re
import json
import time
import calendar
import datetime
import urllib.request
import threading
import tkinter as tk
from tkinter import font as tkfont
from dateutil import parser as dt_parser, rrule, tz

# ==============================================================================
# Theme: Gruvbox Dark (matching Qtile & Kitty config)
# ==============================================================================
THEME = {
    "bg": "#282828",           # Dark0 background
    "bg_surface": "#32302f",   # Dark0_soft surface
    "bg_card": "#3c3836",      # Dark1 container
    "bg_hover": "#504945",     # Dark2 hover
    "bg_selected": "#504945",  # Dark2 selected
    "border": "#504945",       # Dark2 border
    "border_focus": "#83a598", # Bright blue border
    "border_today": "#fabd2f", # Bright yellow border for Today
    "fg": "#ebdbb2",           # Light1 main text
    "fg_dim": "#a89984",       # Light4 muted text
    "fg_header": "#fbf1c7",    # Light0 prominent text
    "key_bg": "#1d2021",       # Hard dark background for key badges
    "key_fg": "#fabd2f",       # Bright yellow for key text
    "status_running": "#b8bb26", # Bright green
    "status_stopped": "#fb4934", # Bright red
    "status_paused": "#fabd2f",  # Bright yellow
    "accent_blue": "#83a598",  # Information accent
    "accent_aqua": "#8ec07c",  # Secondary accent
    "accent_purple": "#d3869b",# Special accent
    "accent_orange": "#fe8019",# Warning / highlight accent
}

CONFIG_DIR = os.path.expanduser("~/.config/zodiac")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CACHE_DIR = os.path.expanduser("~/.cache/zodiac")
CACHE_FILE = os.path.join(CACHE_DIR, "events.json")


class CalendarManager:
    """Handles fetching, parsing, and caching iCal Google Calendar events."""

    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.config = self._load_config()
        self.events = self._load_cached_events()
        self.last_sync_time = self._get_cache_mtime()
        self.sync_status = "READY" if self.events else "NO_DATA"
        self.local_tz = tz.tzlocal()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"ical_url": ""}

    def save_config(self, ical_url):
        self.config["ical_url"] = ical_url.strip()
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def _get_cache_mtime(self):
        if os.path.exists(CACHE_FILE):
            try:
                return os.path.getmtime(CACHE_FILE)
            except Exception:
                pass
        return 0

    def _load_cached_events(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_cached_events(self, events):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(events, f, indent=2)
            self.last_sync_time = time.time()
        except Exception:
            pass

    def sync_feed(self, callback=None):
        """Asynchronously downloads and parses the iCal URL feed."""
        url = self.config.get("ical_url", "").strip()
        if not url:
            self.sync_status = "NO_URL"
            if callback:
                callback(False, "No iCal URL configured")
            return

        def _worker():
            self.sync_status = "SYNCING"
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "ZodiacCalendar/1.0 (Linux; Qtile)"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read().decode("utf-8", errors="replace")

                events = self._parse_ics_content(content)
                self.events = events
                self._save_cached_events(events)
                self.sync_status = "SYNCED"
                if callback:
                    callback(True, f"Synced {len(events)} events")
            except Exception as e:
                self.sync_status = "ERROR"
                if callback:
                    callback(False, str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _parse_ics_content(self, text):
        unfolded = re.sub(r"\r?\n[ \t]", "", text)
        raw_events = []
        now_dt = datetime.datetime.now(tz=self.local_tz)
        window_start = now_dt - datetime.timedelta(days=60)
        window_end = now_dt + datetime.timedelta(days=365)

        for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.DOTALL):
            evt = {}
            for line in block.strip().splitlines():
                if ":" not in line:
                    continue
                key_part, val = line.split(":", 1)
                key = key_part.split(";")[0].upper()

                if key == "SUMMARY":
                    evt["summary"] = val.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
                elif key == "DESCRIPTION":
                    evt["description"] = val.replace("\\n", "\n").replace("\\,", ",").strip()
                elif key == "LOCATION":
                    evt["location"] = val.replace("\\,", ",").strip()
                elif key == "DTSTART":
                    evt["dtstart_raw"] = val.strip()
                    evt["is_all_day"] = ("VALUE=DATE" in key_part) or (len(val.strip()) == 8)
                elif key == "DTEND":
                    evt["dtend_raw"] = val.strip()
                elif key == "RRULE":
                    evt["rrule"] = val.strip()
                elif key == "STATUS":
                    evt["status"] = val.strip().upper()

            if "summary" in evt and "dtstart_raw" in evt:
                if evt.get("status") == "CANCELLED":
                    continue
                raw_events.append(evt)

        # Expand recurrences and normalize datetimes
        expanded = []
        for r in raw_events:
            summary = r["summary"]
            desc = r.get("description", "")
            loc = r.get("location", "")
            is_all_day = r.get("is_all_day", False)
            dt_raw = r["dtstart_raw"]

            try:
                if is_all_day:
                    start_date = datetime.datetime.strptime(dt_raw[:8], "%Y%m%d").date()
                    expanded.append({
                        "summary": summary,
                        "description": desc,
                        "location": loc,
                        "is_all_day": True,
                        "date": start_date.strftime("%Y-%m-%d"),
                        "start_time": "",
                        "end_time": "",
                        "timestamp": int(datetime.datetime(start_date.year, start_date.month, start_date.day).timestamp())
                    })
                else:
                    dt_start = dt_parser.parse(dt_raw)
                    if dt_start.tzinfo is None:
                        dt_start = dt_start.replace(tzinfo=tz.tzutc())
                    local_start = dt_start.astimezone(self.local_tz)

                    duration = datetime.timedelta(hours=1)
                    if "dtend_raw" in r:
                        dt_end = dt_parser.parse(r["dtend_raw"])
                        if dt_end.tzinfo is None:
                            dt_end = dt_end.replace(tzinfo=tz.tzutc())
                        local_end = dt_end.astimezone(self.local_tz)
                        duration = local_end - local_start

                    if "rrule" in r:
                        try:
                            rule = rrule.rrulestr(r["rrule"], dtstart=local_start)
                            occurrences = rule.between(window_start, window_end, inc=True)
                            for occ in occurrences:
                                expanded.append({
                                    "summary": summary,
                                    "description": desc,
                                    "location": loc,
                                    "is_all_day": False,
                                    "date": occ.date().strftime("%Y-%m-%d"),
                                    "start_time": occ.strftime("%I:%M %p").lstrip("0"),
                                    "end_time": (occ + duration).strftime("%I:%M %p").lstrip("0"),
                                    "timestamp": int(occ.timestamp())
                                })
                        except Exception:
                            # Fallback if rrule fails
                            expanded.append({
                                "summary": summary,
                                "description": desc,
                                "location": loc,
                                "is_all_day": False,
                                "date": local_start.date().strftime("%Y-%m-%d"),
                                "start_time": local_start.strftime("%I:%M %p").lstrip("0"),
                                "end_time": (local_start + duration).strftime("%I:%M %p").lstrip("0"),
                                "timestamp": int(local_start.timestamp())
                            })
                    else:
                        expanded.append({
                            "summary": summary,
                            "description": desc,
                            "location": loc,
                            "is_all_day": False,
                            "date": local_start.date().strftime("%Y-%m-%d"),
                            "start_time": local_start.strftime("%I:%M %p").lstrip("0"),
                            "end_time": (local_start + duration).strftime("%I:%M %p").lstrip("0"),
                            "timestamp": int(local_start.timestamp())
                        })
            except Exception:
                continue

        # Sort chronologically by timestamp
        expanded.sort(key=lambda x: x["timestamp"])
        return expanded


class ZodiacApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Zodiac Calendar")
        self.root.configure(bg=THEME["bg"])

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = int(sw * 0.8)
        target_h = int(sh * 0.88)
        self.root.geometry(f"{target_w}x{target_h}")
        self.root.minsize(target_w, target_h)

        self.cal_mgr = CalendarManager()

        # Date states
        self.today = datetime.date.today()
        self.view_year = self.today.year
        self.view_month = self.today.month
        self.selected_date = self.today

        # Day button widgets dict: {date_obj: button_widget}
        self.day_buttons = {}

        self.settings_modal = None

        self._build_header()
        self._build_main_split()
        self._build_footer()
        self._bind_keys()

        # Initial render of calendar & agenda
        self._render_month_grid()
        self._render_agenda()

        # Check if URL configured, if not, open config dialog
        if not self.cal_mgr.config.get("ical_url"):
            self.root.after(200, self.open_settings_dialog)
        else:
            # Sync feed if cache older than 30 mins
            if time.time() - self.cal_mgr.last_sync_time > 1800:
                self.trigger_sync()

    def _build_header(self):
        header_bar = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        header_bar.pack(fill="x", padx=12, pady=(12, 6), ipady=8)

        # Title & Logo
        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=14)

        lbl_logo = tk.Label(
            title_box,
            text="✨",
            font=("DejaVu Sans Mono", 14),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
        )
        lbl_logo.pack(side="left", padx=(0, 6))

        lbl_title = tk.Label(
            title_box,
            text="ZODIAC CALENDAR",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(side="left")

        # Today Pill
        lbl_today_str = self.today.strftime("%A, %b %d, %Y")
        lbl_today_badge = tk.Label(
            header_bar,
            text=f" Today: {lbl_today_str} ",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["accent_blue"],
            bg=THEME["key_bg"],
            padx=8,
            pady=3,
        )
        lbl_today_badge.pack(side="left", padx=12)

        # Controls & Status (Right side)
        right_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        right_box.pack(side="right", padx=14)

        self.lbl_status = tk.Label(
            right_box,
            text=self._get_status_text(),
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=self._get_status_color(),
            bg=THEME["key_bg"],
            padx=8,
            pady=3,
        )
        self.lbl_status.pack(side="left", padx=(0, 8))

        btn_sync = tk.Button(
            right_box,
            text="⟳ Sync (r)",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.trigger_sync,
        )
        btn_sync.pack(side="left", padx=(0, 6))

        btn_settings = tk.Button(
            right_box,
            text="⚙ Config (s)",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["fg_dim"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.open_settings_dialog,
        )
        btn_settings.pack(side="left")

    def _get_status_text(self):
        st = self.cal_mgr.sync_status
        if st == "SYNCED":
            diff_m = int((time.time() - self.cal_mgr.last_sync_time) / 60)
            return f"● SYNCED ({diff_m}m ago)"
        elif st == "SYNCING":
            return "◌ SYNCING..."
        elif st == "NO_URL":
            return "○ NO URL SET"
        elif st == "ERROR":
            return "● SYNC ERROR"
        return "● READY"

    def _get_status_color(self):
        st = self.cal_mgr.sync_status
        if st == "SYNCED" or st == "READY":
            return THEME["status_running"]
        elif st == "SYNCING":
            return THEME["status_paused"]
        elif st == "ERROR":
            return THEME["status_stopped"]
        return THEME["fg_dim"]

    def _build_main_split(self):
        self.main_container = tk.Frame(self.root, bg=THEME["bg"])
        self.main_container.pack(fill="both", expand=True, padx=12, pady=4)

        # Left Pane: Calendar Grid (42% width)
        self.left_pane = tk.Frame(
            self.main_container,
            bg=THEME["bg_surface"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        self.left_pane.pack(side="left", fill="both", expand=False, padx=(0, 6))
        self.left_pane.config(width=480)

        # Right Pane: Daily Agenda (58% width)
        self.right_pane = tk.Frame(
            self.main_container,
            bg=THEME["bg_surface"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        self.right_pane.pack(side="right", fill="both", expand=True, padx=(6, 0))

        self._build_month_header()
        self._build_agenda_scroller()

    def _build_month_header(self):
        top_row = tk.Frame(self.left_pane, bg=THEME["bg_surface"])
        top_row.pack(fill="x", padx=10, pady=(10, 6))

        btn_prev = tk.Button(
            top_row,
            text="◀ Prev (J)",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=THEME["fg"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.prev_month,
        )
        btn_prev.pack(side="left")

        btn_today = tk.Button(
            top_row,
            text="Today (t)",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.goto_today,
        )
        btn_today.pack(side="left", padx=6)

        self.lbl_month_year = tk.Label(
            top_row,
            text="",
            font=("DejaVu Sans Mono", 11, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_surface"],
        )
        self.lbl_month_year.pack(side="left", fill="x", expand=True)

        btn_next = tk.Button(
            top_row,
            text="Next ▶ (K)",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=THEME["fg"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.next_month,
        )
        btn_next.pack(side="right")

        # Grid container
        self.grid_frame = tk.Frame(self.left_pane, bg=THEME["bg_surface"])
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def _build_agenda_scroller(self):
        top_agenda_bar = tk.Frame(self.right_pane, bg=THEME["bg_surface"])
        top_agenda_bar.pack(fill="x", padx=12, pady=(10, 6))

        self.lbl_agenda_date = tk.Label(
            top_agenda_bar,
            text="AGENDA",
            font=("DejaVu Sans Mono", 11, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["bg_surface"],
        )
        self.lbl_agenda_date.pack(side="left")

        # Scrollable Agenda content
        scroller_box = tk.Frame(self.right_pane, bg=THEME["bg_surface"])
        scroller_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.agenda_canvas = tk.Canvas(scroller_box, bg=THEME["bg_surface"], bd=0, highlightthickness=0)
        self.agenda_scrollbar = tk.Scrollbar(scroller_box, orient="vertical", command=self.agenda_canvas.yview, bg=THEME["bg_card"])
        self.agenda_frame = tk.Frame(self.agenda_canvas, bg=THEME["bg_surface"])

        self.agenda_frame.bind("<Configure>", lambda e: self.agenda_canvas.configure(scrollregion=self.agenda_canvas.bbox("all")))
        self.agenda_canvas_window = self.agenda_canvas.create_window((0, 0), window=self.agenda_frame, anchor="nw")
        self.agenda_canvas.bind("<Configure>", lambda e: self.agenda_canvas.itemconfig(self.agenda_canvas_window, width=e.width))

        self.agenda_canvas.configure(yscrollcommand=self.agenda_scrollbar.set)
        self.agenda_canvas.pack(side="left", fill="both", expand=True)
        self.agenda_scrollbar.pack(side="right", fill="y")

    def _build_footer(self):
        footer_bar = tk.Frame(
            self.root,
            bg=THEME["bg_surface"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer_bar.pack(fill="x", padx=12, pady=(6, 12), ipady=6)

        shortcuts = [
            ("h/l or ←/→", "Day -1/+1"),
            ("j/k or ↓/↑", "Week -1/+1"),
            ("J/K", "Month -1/+1"),
            ("t", "Today"),
            ("r", "Sync"),
            ("s", "Settings"),
            ("q / Esc", "Close"),
        ]

        for key, desc in shortcuts:
            box = tk.Frame(footer_bar, bg=THEME["bg_surface"])
            box.pack(side="left", padx=8)

            lbl_k = tk.Label(
                box,
                text=f" {key} ",
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=4,
                pady=1,
            )
            lbl_k.pack(side="left")

            lbl_d = tk.Label(
                box,
                text=f" {desc}",
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            )
            lbl_d.pack(side="left")

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("q", lambda e: self.root.destroy())
        self.root.bind("Q", lambda e: self.root.destroy())
        self.root.bind("r", lambda e: self.trigger_sync())
        self.root.bind("R", lambda e: self.trigger_sync())
        self.root.bind("t", lambda e: self.goto_today())
        self.root.bind("s", lambda e: self.open_settings_dialog())

        # Vim navigation
        self.root.bind("h", lambda e: self.change_selected_day(-1))
        self.root.bind("<Left>", lambda e: self.change_selected_day(-1))
        self.root.bind("l", lambda e: self.change_selected_day(1))
        self.root.bind("<Right>", lambda e: self.change_selected_day(1))
        self.root.bind("j", lambda e: self.change_selected_day(7))
        self.root.bind("<Down>", lambda e: self.change_selected_day(7))
        self.root.bind("k", lambda e: self.change_selected_day(-7))
        self.root.bind("<Up>", lambda e: self.change_selected_day(-7))
        self.root.bind("J", lambda e: self.next_month())
        self.root.bind("<Next>", lambda e: self.next_month())
        self.root.bind("K", lambda e: self.prev_month())
        self.root.bind("<Prior>", lambda e: self.prev_month())

    def goto_today(self):
        self.selected_date = self.today
        self.view_year = self.today.year
        self.view_month = self.today.month
        self._render_month_grid()
        self._render_agenda()

    def prev_month(self):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self._render_month_grid()

    def next_month(self):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self._render_month_grid()

    def change_selected_day(self, delta_days):
        new_date = self.selected_date + datetime.timedelta(days=delta_days)
        self.selected_date = new_date
        if (new_date.year != self.view_year) or (new_date.month != self.view_month):
            self.view_year = new_date.year
            self.view_month = new_date.month
            self._render_month_grid()
        else:
            self._update_grid_selection()
        self._render_agenda()

    def select_date(self, target_date):
        self.selected_date = target_date
        self._update_grid_selection()
        self._render_agenda()

    def _render_month_grid(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.day_buttons.clear()

        # Update Month/Year title
        m_name = calendar.month_name[self.view_month].upper()
        self.lbl_month_year.config(text=f"{m_name} {self.view_year}")

        # Weekday headers
        days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        for c, day_str in enumerate(days):
            lbl = tk.Label(
                self.grid_frame,
                text=day_str,
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"] if c in (0, 6) else THEME["fg_dim"],
                bg=THEME["bg_surface"],
                pady=4,
            )
            lbl.grid(row=0, column=c, sticky="nsew", padx=2, pady=2)
            self.grid_frame.columnconfigure(c, weight=1)

        # Days in month
        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        month_days = cal.monthdatescalendar(self.view_year, self.view_month)

        # Set of dates with events
        event_dates = set(e["date"] for e in self.cal_mgr.events)

        for r, week in enumerate(month_days):
            self.grid_frame.rowconfigure(r + 1, weight=1)
            for c, d in enumerate(week):
                is_curr_month = (d.month == self.view_month)
                is_today = (d == self.today)
                is_selected = (d == self.selected_date)
                date_str = d.strftime("%Y-%m-%d")
                has_events = date_str in event_dates

                # Cell styling
                cell_bg = THEME["bg_card"] if is_curr_month else THEME["bg_surface"]
                cell_fg = THEME["fg"] if is_curr_month else THEME["fg_dim"]

                bd_color = THEME["border"]
                bd_thick = 1
                if is_selected:
                    bd_color = THEME["border_focus"]
                    bd_thick = 2
                    cell_bg = THEME["bg_hover"]
                elif is_today:
                    bd_color = THEME["border_today"]
                    bd_thick = 2

                cell_frame = tk.Frame(
                    self.grid_frame,
                    bg=cell_bg,
                    highlightthickness=bd_thick,
                    highlightbackground=bd_color,
                    cursor="hand2",
                )
                cell_frame.grid(row=r + 1, column=c, sticky="nsew", padx=2, pady=2)

                # Day number
                lbl_num = tk.Label(
                    cell_frame,
                    text=str(d.day),
                    font=("DejaVu Sans Mono", 9, "bold" if (is_today or is_selected) else "normal"),
                    fg=THEME["key_fg"] if is_today else cell_fg,
                    bg=cell_bg,
                )
                lbl_num.pack(anchor="nw", padx=4, pady=2)

                # Event Dot
                if has_events:
                    lbl_dot = tk.Label(
                        cell_frame,
                        text="●",
                        font=("DejaVu Sans Mono", 7),
                        fg=THEME["status_running"],
                        bg=cell_bg,
                    )
                    lbl_dot.pack(anchor="s", pady=(0, 2))

                def make_click_cmd(target_d):
                    return lambda e: self.select_date(target_d)

                cell_frame.bind("<Button-1>", make_click_cmd(d))
                lbl_num.bind("<Button-1>", make_click_cmd(d))

                self.day_buttons[d] = cell_frame

    def _update_grid_selection(self):
        for d, frame in self.day_buttons.items():
            is_today = (d == self.today)
            is_selected = (d == self.selected_date)
            is_curr_month = (d.month == self.view_month)

            cell_bg = THEME["bg_card"] if is_curr_month else THEME["bg_surface"]
            bd_color = THEME["border"]
            bd_thick = 1

            if is_selected:
                bd_color = THEME["border_focus"]
                bd_thick = 2
                cell_bg = THEME["bg_hover"]
            elif is_today:
                bd_color = THEME["border_today"]
                bd_thick = 2

            frame.config(bg=cell_bg, highlightthickness=bd_thick, highlightbackground=bd_color)
            for child in frame.winfo_children():
                child.config(bg=cell_bg)

    def _render_agenda(self):
        for w in self.agenda_frame.winfo_children():
            w.destroy()

        date_str = self.selected_date.strftime("%Y-%m-%d")
        full_date_label = self.selected_date.strftime("%A, %B %d, %Y")
        self.lbl_agenda_date.config(text=f"AGENDA: {full_date_label.upper()}")

        # Filter events for selected date
        day_events = [e for e in self.cal_mgr.events if e["date"] == date_str]

        if day_events:
            for evt in day_events:
                self._create_event_card(self.agenda_frame, evt)
        else:
            empty_box = tk.Frame(self.agenda_frame, bg=THEME["bg_surface"])
            empty_box.pack(fill="x", padx=8, pady=16)

            lbl_none = tk.Label(
                empty_box,
                text="No events scheduled for this day.",
                font=("DejaVu Sans Mono", 10, "italic"),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            )
            lbl_none.pack(anchor="w")

        # Upcoming Events Preview (Next 7 days)
        now_date_str = self.today.strftime("%Y-%m-%d")
        upcoming = [e for e in self.cal_mgr.events if e["date"] >= now_date_str and e["date"] != date_str][:8]

        if upcoming:
            sep = tk.Frame(self.agenda_frame, bg=THEME["border"], height=1)
            sep.pack(fill="x", padx=8, pady=(20, 10))

            lbl_up_title = tk.Label(
                self.agenda_frame,
                text="UPCOMING EVENTS",
                font=("DejaVu Sans Mono", 10, "bold"),
                fg=THEME["accent_aqua"],
                bg=THEME["bg_surface"],
            )
            lbl_up_title.pack(anchor="w", padx=8, pady=(0, 6))

            for evt in upcoming:
                self._create_event_card(self.agenda_frame, evt, is_upcoming=True)

    def _create_event_card(self, parent, evt, is_upcoming=False):
        card = tk.Frame(
            parent,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        card.pack(fill="x", padx=8, pady=4)

        inner = tk.Frame(card, bg=THEME["bg_card"])
        inner.pack(fill="x", padx=12, pady=8)

        # Top row: Time pill + Date (if upcoming) + Title
        top_row = tk.Frame(inner, bg=THEME["bg_card"])
        top_row.pack(fill="x")

        # Date pill if in upcoming feed
        if is_upcoming:
            try:
                dt_obj = datetime.datetime.strptime(evt["date"], "%Y-%m-%d").date()
                d_str = dt_obj.strftime("%a %b %d")
            except Exception:
                d_str = evt["date"]
            lbl_d = tk.Label(
                top_row,
                text=f" {d_str} ",
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["accent_aqua"],
                bg=THEME["key_bg"],
                padx=4,
                pady=1,
            )
            lbl_d.pack(side="left", padx=(0, 6))

        # Time pill
        if evt.get("is_all_day"):
            time_text = "ALL DAY"
            time_color = THEME["accent_purple"]
        else:
            st = evt.get("start_time", "")
            et = evt.get("end_time", "")
            time_text = f"{st} - {et}" if et else st
            time_color = THEME["key_fg"]

        lbl_t = tk.Label(
            top_row,
            text=f" {time_text} ",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=time_color,
            bg=THEME["key_bg"],
            padx=5,
            pady=1,
        )
        lbl_t.pack(side="left", padx=(0, 8))

        # Summary / Title
        lbl_sum = tk.Label(
            top_row,
            text=evt.get("summary", "Untitled Event"),
            font=("DejaVu Sans Mono", 10, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
            anchor="w",
        )
        lbl_sum.pack(side="left", fill="x", expand=True)

        # Location row (if any)
        loc = evt.get("location", "").strip()
        if loc:
            loc_row = tk.Frame(inner, bg=THEME["bg_card"])
            loc_row.pack(fill="x", pady=(4, 0))

            icon = "🔗" if "http" in loc else "📍"
            lbl_loc = tk.Label(
                loc_row,
                text=f"{icon} {loc}",
                font=("DejaVu Sans Mono", 8),
                fg=THEME["accent_blue"],
                bg=THEME["bg_card"],
                anchor="w",
            )
            lbl_loc.pack(side="left")

        # Description (if any)
        desc = evt.get("description", "").strip()
        if desc:
            desc_row = tk.Frame(inner, bg=THEME["bg_card"])
            desc_row.pack(fill="x", pady=(4, 0))

            # Truncate description to max 2 lines
            desc_short = desc.splitlines()[0][:120]
            lbl_desc = tk.Label(
                desc_row,
                text=desc_short,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_card"],
                anchor="w",
            )
            lbl_desc.pack(side="left")

    def trigger_sync(self):
        self.lbl_status.config(text="◌ SYNCING...", fg=THEME["status_paused"])

        def on_done(success, msg):
            self.root.after(0, lambda: self._on_sync_finished(success, msg))

        self.cal_mgr.sync_feed(callback=on_done)

    def _on_sync_finished(self, success, msg):
        self.lbl_status.config(text=self._get_status_text(), fg=self._get_status_color())
        self._render_month_grid()
        self._render_agenda()

    def open_settings_dialog(self):
        """Opens a modal overlay to enter or edit the Google Calendar iCal URL."""
        if self.settings_modal:
            return

        modal = tk.Toplevel(self.root)
        modal.title("Google Calendar Settings")
        modal.configure(bg=THEME["bg"])
        modal.transient(self.root)
        modal.grab_set()

        mw, mh = 680, 360
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - mw) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - mh) // 2
        modal.geometry(f"{mw}x{mh}+{rx}+{ry}")
        modal.resizable(False, False)

        self.settings_modal = modal

        container = tk.Frame(modal, bg=THEME["bg_card"], padx=20, pady=20)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        lbl_hdr = tk.Label(
            container,
            text="⚙ GOOGLE CALENDAR SETUP (READ-ONLY)",
            font=("DejaVu Sans Mono", 11, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
        )
        lbl_hdr.pack(anchor="w", pady=(0, 10))

        instructions = (
            "How to get your private iCal URL:\n"
            "1. Open calendar.google.com in a browser.\n"
            "2. Click the gear icon ⚙ > Settings > click your calendar on the left.\n"
            "3. Scroll down to 'Integrate calendar'.\n"
            "4. Copy 'Secret address in iCal format' (starts with https://calendar.google.com/...).\n"
            "5. Paste it in the field below:"
        )
        lbl_inst = tk.Label(
            container,
            text=instructions,
            font=("DejaVu Sans Mono", 8),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
            justify="left",
        )
        lbl_inst.pack(anchor="w", pady=(0, 10))

        lbl_entry = tk.Label(
            container,
            text="Secret iCal URL:",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["accent_blue"],
            bg=THEME["bg_card"],
        )
        lbl_entry.pack(anchor="w")

        entry_frame = tk.Frame(container, bg=THEME["bg_surface"], bd=1, highlightthickness=1, highlightbackground=THEME["border"])
        entry_frame.pack(fill="x", pady=(4, 16), ipady=3)

        url_var = tk.StringVar(value=self.cal_mgr.config.get("ical_url", ""))
        entry = tk.Entry(
            entry_frame,
            textvariable=url_var,
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg"],
            bg=THEME["bg_surface"],
            insertbackground=THEME["key_fg"],
            bd=0,
            highlightthickness=0,
        )
        entry.pack(fill="x", padx=6)
        entry.focus()

        btn_box = tk.Frame(container, bg=THEME["bg_card"])
        btn_box.pack(fill="x")

        def save_and_close():
            new_url = url_var.get().strip()
            self.cal_mgr.save_config(new_url)
            modal.destroy()
            self.settings_modal = None
            self.trigger_sync()

        def cancel_dialog():
            modal.destroy()
            self.settings_modal = None

        btn_save = tk.Button(
            btn_box,
            text="✔ Save & Sync",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["key_bg"],
            bg=THEME["status_running"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            command=save_and_close,
        )
        btn_save.pack(side="right", padx=(8, 0))

        btn_cancel = tk.Button(
            btn_box,
            text="Cancel",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=cancel_dialog,
        )
        btn_cancel.pack(side="right")

        modal.bind("<Escape>", lambda e: cancel_dialog())
        modal.protocol("WM_DELETE_WINDOW", cancel_dialog)


if __name__ == "__main__":
    root = tk.Tk(className="zodiac-pad")
    app = ZodiacApp(root)
    root.mainloop()
