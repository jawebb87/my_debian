#!/usr/bin/env python3
"""
Log Pad - Desktop System Log Viewer & Searcher for Qtile
=========================================================
A fast, keyboard-driven log viewer and searcher styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Instant switching across primary Linux and desktop log streams:
    [1] User Journal      : systemd user units, desktop services, portals, PipeWire
    [2] System Boot       : user session journal events for current boot
    [3] Qtile Log         : ~/.local/share/qtile/qtile.log (WM errors, reloads)
    [4] Errors Only       : journalctl priority err..emerg filtered log
    [5] X11 Errors        : ~/.xsession-errors display output
    [6] DPKG / Apt        : /var/log/dpkg.log package update history
- Real-time search and filter with instant match highlighting ('/' to search)
- Next / Previous match navigation (n / N)
- Syntax & log-level color coding (Errors in Red, Warnings in Yellow, Info in Aqua)
- Live auto-follow / tail mode ('f' to toggle auto-scroll)
- One-key clipboard copy ('c' copies selected text or visible logs via xclip)
- Full Vim-style navigation:
    j / k or Down / Up    : Scroll by line
    d / u or PgDn / PgUp  : Half-page jump
    g / G or Home / End   : Jump to Top / Bottom
    1 - 6                 : Quick switch log source
    Tab / Shift-Tab       : Cycle log source
    /                     : Focus search bar
    r                     : Force refresh
    q / Esc               : Dismiss dropdown
- Native X11 WM_CLASS ("log-pad") for Qtile ScratchPad integration
- Full dynamic Gruvbox Dark / Light theme support via theme.py
"""

import sys
import os
import re
import collections
import subprocess
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

LOG_SOURCES = [
    {
        "name": "User Journal",
        "key": "1",
        "icon": "\uf013",  # fa-cog
        "cmd": ["journalctl", "--user", "-q", "-n", "500", "--no-pager"],
        "desc": "Systemd user services, desktop apps, PipeWire, portals",
    },
    {
        "name": "System Boot",
        "key": "2",
        "icon": "\uf108",  # fa-desktop
        "cmd": ["journalctl", "-q", "-b", "-n", "500", "--no-pager"],
        "desc": "User session journal events for current boot",
    },
    {
        "name": "Qtile Log",
        "key": "3",
        "icon": "\uf2d0",  # fa-window-maximize
        "file": os.path.expanduser("~/.local/share/qtile/qtile.log"),
        "desc": "Window manager logs, event errors, config reloads",
    },
    {
        "name": "Errors Only",
        "key": "4",
        "icon": "\uf071",  # fa-exclamation-triangle
        "cmd": ["journalctl", "--user", "-q", "-p", "3", "-n", "500", "--no-pager"],
        "desc": "Critical errors and warnings (priority err..emerg)",
    },
    {
        "name": "X11 Errors",
        "key": "5",
        "icon": "\uf26c",  # fa-television
        "file": os.path.expanduser("~/.xsession-errors"),
        "desc": "X11 display server output and client stderr",
    },
    {
        "name": "DPKG / Apt",
        "key": "6",
        "icon": "\uf1b2",  # fa-cube
        "file": "/var/log/dpkg.log",
        "desc": "Package installation, upgrade, and removal history",
    },
]


# ==============================================================================
# Main Log Viewer Application
# ==============================================================================
class LogPadApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("System Log Viewer")
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

        self.current_source_idx = 0
        self.raw_lines: list[str] = []
        self.is_loading = False
        self.follow_mode = True
        self.search_matches: list[str] = []
        self.current_match_idx = -1

        self.tab_buttons: list[tk.Frame] = []
        self.tab_labels: list[dict[str, tk.Label]] = []

        self._build_header()
        self._build_search_bar()
        self._build_log_area()
        self._build_footer()
        self._bind_keys()

        # Load first log source
        self.switch_source(0)

    # --------------------------------------------------------------------------
    # UI Building
    # --------------------------------------------------------------------------
    def _build_header(self):
        """Build top navigation tabs for switching log streams."""
        header_frame = tk.Frame(self.root, bg=THEME["bg_surface"], height=52)
        header_frame.pack(fill="x", side="top", padx=16, pady=(14, 8))
        header_frame.pack_propagate(False)

        # Left: App Title Badge
        title_box = tk.Frame(header_frame, bg=THEME["bg_surface"])
        title_box.pack(side="left", padx=12, pady=8)

        tk.Label(
            title_box,
            text="\uf022",  # fa-list-alt
            font=("FontAwesome", 15),
            fg=THEME["accent_yellow"],
            bg=THEME["bg_surface"],
        ).pack(side="left", padx=(0, 8))

        tk.Label(
            title_box,
            text="LOG PAD",
            font=("DejaVu Sans", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_surface"],
        ).pack(side="left")

        # Center/Right: Tab buttons for each log source
        tabs_box = tk.Frame(header_frame, bg=THEME["bg_surface"])
        tabs_box.pack(side="left", padx=16, pady=8)

        for i, src in enumerate(LOG_SOURCES):
            btn_frame = tk.Frame(
                tabs_box,
                bg=THEME["bg_card"],
                highlightbackground=THEME["border"],
                highlightthickness=1,
                padx=8,
                pady=4,
                cursor="hand2",
            )
            btn_frame.pack(side="left", padx=4)
            btn_frame.bind("<Button-1>", lambda e, idx=i: self.switch_source(idx))

            badge = tk.Label(
                btn_frame,
                text=f"[{src['key']}]",
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=4,
                pady=1,
            )
            badge.pack(side="left", padx=(0, 6))
            badge.bind("<Button-1>", lambda e, idx=i: self.switch_source(idx))

            lbl_name = tk.Label(
                btn_frame,
                text=src["name"],
                font=("DejaVu Sans", 9, "bold"),
                fg=THEME["fg"],
                bg=THEME["bg_card"],
            )
            lbl_name.pack(side="left")
            lbl_name.bind("<Button-1>", lambda e, idx=i: self.switch_source(idx))

            self.tab_buttons.append(btn_frame)
            self.tab_labels.append({"badge": badge, "name": lbl_name, "frame": btn_frame})

        # Right Action buttons
        right_box = tk.Frame(header_frame, bg=THEME["bg_surface"])
        right_box.pack(side="right", padx=12, pady=8)

        self.btn_follow = tk.Button(
            right_box,
            text="Tail: ON (f)",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=THEME["key_bg"],
            bg=THEME["status_running"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.toggle_follow_mode,
        )
        self.btn_follow.pack(side="left", padx=(0, 8))

        btn_refresh = tk.Button(
            right_box,
            text="\uf021 (r)",  # fa-refresh
            font=("FontAwesome", 9, "bold"),
            fg=THEME["fg"],
            bg=THEME["bg_hover"],
            activebackground=THEME["status_running"],
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.refresh_current_source,
        )
        btn_refresh.pack(side="left", padx=(0, 8))

        btn_close = tk.Button(
            right_box,
            text="\uf00d",  # fa-times
            font=("FontAwesome", 9),
            fg=THEME["fg_dim"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.root.destroy,
        )
        btn_close.pack(side="left")

    def _build_search_bar(self):
        """Build interactive search and filter input bar."""
        search_frame = tk.Frame(self.root, bg=THEME["bg_card"], height=40)
        search_frame.pack(fill="x", padx=16, pady=(0, 8))
        search_frame.pack_propagate(False)

        # Search icon
        tk.Label(
            search_frame,
            text="\uf002",  # fa-search
            font=("FontAwesome", 10),
            fg=THEME["accent_yellow"],
            bg=THEME["bg_card"],
        ).pack(side="left", padx=(12, 6))

        # Search entry
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_search_query_changed())

        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("DejaVu Sans Mono", 10),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
            insertbackground=THEME["accent_blue"],
            bd=0,
            highlightthickness=0,
        )
        self.search_entry.pack(side="left", fill="both", expand=True, padx=(4, 10))

        # Match Counter Label
        self.lbl_matches = tk.Label(
            search_frame,
            text="",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["accent_aqua"],
            bg=THEME["bg_card"],
        )
        self.lbl_matches.pack(side="right", padx=(4, 12))

        # Next / Prev match buttons
        self.btn_next_match = tk.Button(
            search_frame,
            text="▼ (n)",
            font=("DejaVu Sans Mono", 8),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=6,
            pady=2,
            command=self.next_search_match,
        )
        self.btn_next_match.pack(side="right", padx=2)

        self.btn_prev_match = tk.Button(
            search_frame,
            text="▲ (N)",
            font=("DejaVu Sans Mono", 8),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=6,
            pady=2,
            command=self.prev_search_match,
        )
        self.btn_prev_match.pack(side="right", padx=2)

        # Clear search button
        btn_clear = tk.Button(
            search_frame,
            text="Esc: Clear",
            font=("DejaVu Sans Mono", 8),
            fg=THEME["fg_dim"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=6,
            pady=2,
            command=self.clear_search,
        )
        btn_clear.pack(side="right", padx=6)

    def _build_log_area(self):
        """Build main monospace log display canvas."""
        text_container = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
        )
        text_container.pack(fill="both", expand=True, padx=16, pady=0)

        # Scrollbar
        self.scrollbar = tk.Scrollbar(text_container, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")

        # Text Widget
        self.text_widget = tk.Text(
            text_container,
            bg=THEME["key_bg"],
            fg=THEME["fg"],
            font=("DejaVu Sans Mono", 9),
            bd=0,
            padx=10,
            pady=8,
            wrap="none",
            yscrollcommand=self.scrollbar.set,
            selectbackground=THEME["bg_active"],
            selectforeground=THEME["fg_header"],
        )
        self.text_widget.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.text_widget.yview)

        # Define syntax highlighting tags
        self.text_widget.tag_configure("error", foreground=THEME["status_stopped"], font=("DejaVu Sans Mono", 9, "bold"))
        self.text_widget.tag_configure("warn", foreground=THEME["status_paused"], font=("DejaVu Sans Mono", 9, "bold"))
        self.text_widget.tag_configure("info", foreground=THEME["accent_blue"])
        self.text_widget.tag_configure("success", foreground=THEME["status_running"])
        self.text_widget.tag_configure("timestamp", foreground=THEME["accent_aqua"])
        self.text_widget.tag_configure("match_hl", background=THEME["accent_yellow"], foreground=THEME["key_bg"])
        self.text_widget.tag_configure("match_active", background=THEME["accent_orange"], foreground=THEME["key_bg"], font=("DejaVu Sans Mono", 9, "bold"))

    def _build_footer(self):
        """Bottom keybindings cheat-sheet footer bar."""
        footer_frame = tk.Frame(self.root, bg=THEME["bg_surface"], height=36)
        footer_frame.pack(fill="x", side="bottom", padx=16, pady=(8, 12))
        footer_frame.pack_propagate(False)

        shortcuts = [
            ("1-6", "Switch Stream"),
            ("/", "Search"),
            ("n/N", "Next/Prev Match"),
            ("j/k", "Scroll"),
            ("f", "Follow/Tail"),
            ("c", "Copy Clip"),
            ("r", "Refresh"),
            ("q/Esc", "Dismiss"),
        ]

        box = tk.Frame(footer_frame, bg=THEME["bg_surface"])
        box.pack(side="left", padx=12, pady=5)

        for key, desc in shortcuts:
            k_badge = tk.Label(
                box,
                text=key,
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=5,
                pady=1,
            )
            k_badge.pack(side="left", padx=(0, 4))

            d_lbl = tk.Label(
                box,
                text=desc,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            )
            d_lbl.pack(side="left", padx=(0, 12))

        # Status Line / Line Count (Right aligned)
        self.lbl_info = tk.Label(
            footer_frame,
            text="Lines: 0",
            font=("DejaVu Sans Mono", 8),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
        )
        self.lbl_info.pack(side="right", padx=14)

    # --------------------------------------------------------------------------
    # Keyboard Bindings
    # --------------------------------------------------------------------------
    def _bind_keys(self):
        """Register application-wide keyboard shortcuts."""
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<slash>", self._on_slash)
        self.root.bind("q", self._on_q)
        self.root.bind("Q", self._on_q)
        self.root.bind("r", lambda e: self.refresh_current_source() if not self._is_search_focused() else None)
        self.root.bind("R", lambda e: self.refresh_current_source() if not self._is_search_focused() else None)
        self.root.bind("f", lambda e: self.toggle_follow_mode() if not self._is_search_focused() else None)
        self.root.bind("c", lambda e: self.copy_to_clipboard() if not self._is_search_focused() else None)
        self.root.bind("n", lambda e: self.next_search_match() if not self._is_search_focused() else None)
        self.root.bind("N", lambda e: self.prev_search_match() if not self._is_search_focused() else None)

        # Log source switching 1-6
        for i in range(1, len(LOG_SOURCES) + 1):
            self.root.bind(str(i), lambda e, idx=i-1: self.switch_source(idx) if not self._is_search_focused() else None)

        # Tab cycling
        self.root.bind("<Tab>", self._cycle_tabs)
        self.root.bind("<Shift-Tab>", lambda e: self._cycle_tabs(backward=True))

        # Vim scrolling
        self.root.bind("j", lambda e: self._scroll(1) if not self._is_search_focused() else None)
        self.root.bind("<Down>", lambda e: self._scroll(1))
        self.root.bind("k", lambda e: self._scroll(-1) if not self._is_search_focused() else None)
        self.root.bind("<Up>", lambda e: self._scroll(-1))
        self.root.bind("d", lambda e: self._scroll(15) if not self._is_search_focused() else None)
        self.root.bind("<Next>", lambda e: self._scroll(15))
        self.root.bind("u", lambda e: self._scroll(-15) if not self._is_search_focused() else None)
        self.root.bind("<Prior>", lambda e: self._scroll(-15))
        self.root.bind("g", lambda e: self.text_widget.see("1.0") if not self._is_search_focused() else None)
        self.root.bind("G", lambda e: self.text_widget.see("end") if not self._is_search_focused() else None)
        self.root.bind("<Home>", lambda e: self.text_widget.see("1.0") if not self._is_search_focused() else None)
        self.root.bind("<End>", lambda e: self.text_widget.see("end") if not self._is_search_focused() else None)

        # Bind Escape inside search entry
        self.search_entry.bind("<Escape>", self._on_search_escape)
        self.search_entry.bind("<Return>", lambda e: self.next_search_match())

    def _is_search_focused(self) -> bool:
        return self.root.focus_get() == self.search_entry

    def _on_escape(self, event=None):
        if self._is_search_focused():
            self.root.focus_set()
        elif self.search_var.get():
            self.clear_search()
        else:
            self.root.destroy()

    def _on_search_escape(self, event=None):
        self.root.focus_set()
        return "break"

    def _on_slash(self, event=None):
        if not self._is_search_focused():
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            return "break"

    def _on_q(self, event=None):
        if not self._is_search_focused():
            self.root.destroy()

    def _cycle_tabs(self, event=None, backward=False):
        if self._is_search_focused():
            return
        step = -1 if backward else 1
        new_idx = (self.current_source_idx + step) % len(LOG_SOURCES)
        self.switch_source(new_idx)
        return "break"

    def _scroll(self, units: int):
        if self._is_search_focused():
            return
        self.text_widget.yview_scroll(units, "units")

    # --------------------------------------------------------------------------
    # Log Stream Fetching & Management
    # --------------------------------------------------------------------------
    def switch_source(self, idx: int):
        """Switches active log source tab and triggers async fetch."""
        if idx < 0 or idx >= len(LOG_SOURCES):
            return
        self.current_source_idx = idx

        # Update tab visual highlights
        for i, tab in enumerate(self.tab_labels):
            if i == idx:
                tab["frame"].configure(
                    bg=THEME["bg_selected"],
                    highlightbackground=THEME["border_focus"],
                    highlightthickness=2,
                )
                tab["name"].configure(
                    fg=THEME["fg_header"],
                    bg=THEME["bg_selected"],
                )
            else:
                tab["frame"].configure(
                    bg=THEME["bg_card"],
                    highlightbackground=THEME["border"],
                    highlightthickness=1,
                )
                tab["name"].configure(
                    fg=THEME["fg_dim"],
                    bg=THEME["bg_card"],
                )

        self.refresh_current_source()

    def refresh_current_source(self):
        """Asynchronously loads the current log source in background thread."""
        if self.is_loading:
            return
        self.is_loading = True
        src = LOG_SOURCES[self.current_source_idx]
        self.lbl_info.configure(text=f"Loading {src['name']}...", fg=THEME["accent_yellow"])

        def _worker():
            lines = []
            try:
                if "cmd" in src:
                    res = subprocess.run(
                        src["cmd"],
                        capture_output=True,
                        text=True,
                        timeout=6,
                        errors="replace",
                    )
                    content = res.stdout or res.stderr
                    lines = content.splitlines()
                elif "file" in src:
                    path = src["file"]
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            lines = [l.rstrip("\r\n") for l in collections.deque(f, maxlen=600)]
                    else:
                        lines = [f"[File not found: {path}]"]
            except Exception as e:
                lines = [f"[Error reading log: {e}]"]

            # Dispatch UI update strictly to main Tkinter thread
            self.root.after(0, self._apply_logs, lines)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_logs(self, lines: list[str]):
        """Renders raw log lines into the Text widget with syntax highlighting."""
        self.is_loading = False
        self.raw_lines = lines
        self.lbl_info.configure(
            text=f"Stream: {LOG_SOURCES[self.current_source_idx]['name']} | Total: {len(lines)} lines",
            fg=THEME["fg_dim"],
        )
        self._render_text()

    def _render_text(self):
        """Populates the Text widget with formatting and applies search query."""
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")

        query = self.search_var.get().strip().lower()
        self.search_matches.clear()
        self.current_match_idx = -1

        # Regex patterns for fast syntax coloring
        re_error = re.compile(r"(error|crit|alert|emerg|fatal|failed|exception|traceback|badwindow)", re.I)
        re_warn = re.compile(r"(warn|warning)", re.I)
        re_info = re.compile(r"(info|notice)", re.I)
        re_success = re.compile(r"(started|active|success|ok)", re.I)
        re_time = re.compile(r"^(\w{3}\s+\d+\s+\d+:\d+:\d+|\d{4}-\d{2}-\d{2}\s+\d+:\d+:\d+)")

        line_count = 0
        for line in self.raw_lines:
            # If search query active, filter lines
            if query and query not in line.lower():
                continue

            line_start_idx = self.text_widget.index("end-1c")
            self.text_widget.insert("end", line + "\n")
            line_end_idx = self.text_widget.index("end-1c")
            line_count += 1

            # Syntax tagging
            if re_error.search(line):
                self.text_widget.tag_add("error", line_start_idx, line_end_idx)
            elif re_warn.search(line):
                self.text_widget.tag_add("warn", line_start_idx, line_end_idx)
            elif re_success.search(line):
                self.text_widget.tag_add("success", line_start_idx, line_end_idx)
            elif re_info.search(line):
                self.text_widget.tag_add("info", line_start_idx, line_end_idx)

            time_m = re_time.match(line)
            if time_m:
                t_end = f"{line_start_idx}+{time_m.end()}c"
                self.text_widget.tag_add("timestamp", line_start_idx, t_end)

            # Highlight search matches within visible lines
            if query:
                start_p = 0
                lower_l = line.lower()
                while True:
                    p = lower_l.find(query, start_p)
                    if p == -1:
                        break
                    m_start = f"{line_start_idx}+{p}c"
                    m_end = f"{line_start_idx}+{p + len(query)}c"
                    self.text_widget.tag_add("match_hl", m_start, m_end)
                    self.search_matches.append(m_start)
                    start_p = p + len(query)

        self.text_widget.configure(state="disabled")

        # Update Match Count Label
        if query:
            count = len(self.search_matches)
            self.lbl_matches.configure(text=f"{count} matches" if count else "No matches")
            if count > 0:
                self.next_search_match()
        else:
            self.lbl_matches.configure(text="")

        # Auto-follow / tail scrolling
        if self.follow_mode and not query:
            self.text_widget.see("end")

    # --------------------------------------------------------------------------
    # Search & Actions
    # --------------------------------------------------------------------------
    def _on_search_query_changed(self):
        """Called whenever search text changes."""
        self._render_text()

    def clear_search(self):
        """Clears search input and returns focus to log view."""
        self.search_var.set("")
        self.lbl_matches.configure(text="")
        self.root.focus_set()

    def next_search_match(self):
        """Jumps to the next search match."""
        if not self.search_matches:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.search_matches)
        pos = self.search_matches[self.current_match_idx]
        self.text_widget.see(pos)
        self.lbl_matches.configure(
            text=f"Match {self.current_match_idx + 1} of {len(self.search_matches)}"
        )

    def prev_search_match(self):
        """Jumps to previous search match."""
        if not self.search_matches:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.search_matches)
        pos = self.search_matches[self.current_match_idx]
        self.text_widget.see(pos)
        self.lbl_matches.configure(
            text=f"Match {self.current_match_idx + 1} of {len(self.search_matches)}"
        )

    def toggle_follow_mode(self):
        """Toggles auto-follow mode on / off."""
        self.follow_mode = not self.follow_mode
        if self.follow_mode:
            self.btn_follow.configure(
                text="Tail: ON (f)",
                bg=THEME["status_running"],
                fg=THEME["key_bg"],
            )
            self.text_widget.see("end")
        else:
            self.btn_follow.configure(
                text="Tail: OFF (f)",
                bg=THEME["key_bg"],
                fg=THEME["fg_dim"],
            )

    def copy_to_clipboard(self):
        """Copies highlighted text (or full visible logs) to X11 clipboard via xclip."""
        try:
            sel_text = self.text_widget.get("sel.first", "sel.last")
        except Exception:
            sel_text = None

        text_to_copy = sel_text if sel_text else self.text_widget.get("1.0", "end-1c")

        try:
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text_to_copy.encode("utf-8"))
            self.lbl_info.configure(
                text="✓ Copied logs to clipboard!",
                fg=THEME["status_running"],
            )
            self.root.after(2000, lambda: self.lbl_info.configure(
                text=f"Stream: {LOG_SOURCES[self.current_source_idx]['name']} | Total: {len(self.raw_lines)} lines",
                fg=THEME["fg_dim"],
            ))
        except Exception as e:
            self.lbl_info.configure(text=f"Copy failed: {e}", fg=THEME["status_stopped"])


# ==============================================================================
# Application Launch Entrypoint
# ==============================================================================
if __name__ == "__main__":
    root = tk.Tk(className="log-pad")
    app = LogPadApp(root)
    root.mainloop()
