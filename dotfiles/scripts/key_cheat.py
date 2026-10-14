#!/usr/bin/env python3
"""
Qtile Keybindings Cheatsheet Scratchpad
========================================
A fast, keyboard-driven reference for all Qtile keyboard shortcuts, dropdown
scratchpads, window management commands, and system shortcuts. Styled to match
Qtile's Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Expandable / Collapsible accordions for each functional category
- Instant live search across all keys, descriptions, and action tags
- Full Gruvbox Dark aesthetic matching Qtile & Kitty
- Native X11 WM_CLASS ("key-cheat") for Qtile ScratchPad integration
- Keyboard navigation (j/k to scroll, / to search, e/c to toggle all, Esc/q to dismiss)
"""

import sys
import os
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
        "bg": "#282828", "bg_surface": "#32302f", "bg_card": "#3c3836",
        "bg_hover": "#504945", "bg_active": "#665c54", "border": "#504945",
        "border_focus": "#83a598", "fg": "#ebdbb2", "fg_dim": "#a89984",
        "fg_header": "#fbf1c7", "key_bg": "#1d2021", "key_fg": "#fabd2f",
        "status_running": "#b8bb26", "status_stopped": "#fb4934",
        "accent_blue": "#83a598", "accent_aqua": "#8ec07c",
        "accent_green": "#b8bb26", "accent_yellow": "#fabd2f",
        "accent_purple": "#d3869b", "accent_red": "#fb4934",
    }

# ==============================================================================
# Qtile Keybindings Dataset
# ==============================================================================
KEYBINDINGS_DATA = [
    {
        "category": "Dropdown Scratchpads & Quake Apps",
        "icon": "\uf135",  # fa-rocket
        "color": THEME["accent_yellow"],
        "items": [
            ("Super + Return", "Kitty Terminal (raise existing or launch fresh)", "Launcher"),
            ("F12", "Toggle Quake Dropdown Terminal (term-scratch)", "Scratchpad"),
            ("Super + a", "Toggle Audio Mixer Dropdown (audio-pad / PipeWire wpctl)", "Scratchpad"),
            ("Super + c", "Toggle IPython Calculator (calc-pad)", "Scratchpad"),
            ("Super + d", "Toggle Docker Services Manager (docker-pad)", "Scratchpad"),
            ("Super + e", "Toggle Columns layout split H/V or switch to Columns", "Layout"),
            ("Super + f", "Toggle FZF Fast File Search dropdown (fzf-pad)", "Scratchpad"),
            ("Super + g", "Toggle Antigravity Autonomous Assistant (agy-pad)", "Scratchpad"),
            ("Super + i", "Toggle Wi-Fi Network Selector dropdown (wifi-pad)", "Scratchpad"),
            ("Super + m", "Toggle Emoji Picker dropdown with clipboard copy (emoji-pad)", "Scratchpad"),
            ("Super + n", "Toggle System Log Viewer & Searcher (log-pad)", "Scratchpad"),
            ("Super + r", "Toggle Ranger File Manager dropdown (ranger-pad)", "Scratchpad"),
            ("Super + s", "Toggle Quick Notes in Vim (notes-pad / ~/notes/)", "Scratchpad"),
            ("Super + t", "Toggle btop System & Process Monitor (btop)", "Scratchpad"),
            ("Super + v", "Toggle Vim Reference Cheatsheet dropdown (vim-cheat)", "Scratchpad"),
            ("Super + w", "Toggle Denver Weather Forecast dropdown (weather-pad)", "Scratchpad"),
            ("Super + x", "Toggle Clipboard History Manager (clip-pad)", "Scratchpad"),
            ("Super + z", "Toggle Zodiac Google Calendar & Agenda (zodiac-pad)", "Scratchpad"),
            ("Super + F1", "Toggle this Qtile Keybindings Cheatsheet (key-cheat)", "Scratchpad"),
        ],
    },
    {
        "category": "Window Management & Navigation",
        "icon": "\uf2d0",  # fa-window-maximize
        "color": THEME["accent_blue"],
        "items": [
            ("Super + j / Alt + Tab", "Focus next window in current layout", "Focus"),
            ("Super + k / Alt + Shift + Tab", "Focus previous window in current layout", "Focus"),
            ("Super + Tab", "Toggle layout between Columns and Monocle (Full)", "Layout"),
            ("Super + e", "Columns Split Toggle: Multi-column (H) ⟷ Stacked column (V)", "Layout"),
            ("Super + q / Alt + F4", "Close / kill currently focused window", "Kill"),
            ("Super + Shift + f / Alt + F11", "Toggle fullscreen mode for active window", "Window"),
            ("Alt + Space", "Toggle floating mode for active window", "Window"),
        ],
    },
    {
        "category": "Virtual Workspaces & Groups (1 - 9)",
        "icon": "\uf02c",  # fa-tags
        "color": THEME["accent_aqua"],
        "items": [
            ("Super + [1-9]", "Switch active screen view to workspace 1 through 9", "Workspace"),
            ("Super + Shift + [1-9]", "Move active window to workspace [1-9] and follow it", "Move"),
            ("Ctrl + F[1-9]", "Alternate shortcut to switch directly to workspace [1-9]", "Workspace"),
            ("Super + Left", "Switch to previous active virtual workspace", "Pager"),
            ("Super + Right", "Switch to next active virtual workspace", "Pager"),
        ],
    },
    {
        "category": "Standalone Launchers & System Prompts",
        "icon": "\uf0e7",  # fa-bolt
        "color": THEME["accent_purple"],
        "items": [
            ("Super + Space", "Open Rofi application launcher (rofi -show drun)", "Launcher"),
            ("Super + b", "Raise or run Firefox web browser", "Launcher"),
            ("Super + y", "Raise or run Limusic YouTube Music desktop player", "Launcher"),
            ("Super + Shift + Space", "Open Qtile interactive command prompt in top bar", "Bar Prompt"),
            ("Alt + F2", "Alternate shortcut to open Qtile command prompt in bar", "Bar Prompt"),
            ("Super + l", "Lock screen immediately (slock)", "Security"),
            ("Ctrl + Alt + Escape", "Interactive cursor window killer (xkill)", "Utility"),
        ],
    },
    {
        "category": "Screenshots & Screen Capture",
        "icon": "\uf030",  # fa-camera
        "color": THEME["accent_green"],
        "items": [
            ("Print", "Screenshot entire screen (saved to Pictures + copied to clipboard)", "Screenshot"),
            ("Alt + Print", "Screenshot active focused window (saved to Pictures + clipboard)", "Screenshot"),
            ("Shift + Print", "Interactively select rectangular region to capture", "Screenshot"),
        ],
    },
    {
        "category": "Hardware & Audio Controls (PipeWire)",
        "icon": "\uf028",  # fa-volume-up
        "color": THEME["key_fg"],
        "items": [
            ("XF86AudioRaiseVolume", "Raise audio volume by +5% (capped at 150% via wpctl)", "Volume"),
            ("XF86AudioLowerVolume", "Lower audio volume by -5% (PipeWire wpctl)", "Volume"),
            ("XF86AudioMute", "Toggle audio output mute on/off", "Audio"),
            ("XF86AudioMicMute", "Toggle microphone input mute on/off", "Audio"),
            ("XF86WWW / HomePage", "Hardware web browser key (launches Firefox)", "Web"),
        ],
    },
    {
        "category": "Qtile Lifecycle & Session Controls",
        "icon": "\uf013",  # fa-cogs
        "color": THEME["accent_red"],
        "items": [
            ("Super + o", "Toggle Gruvbox Dark / Light desktop theme opposite", "Theme"),
            ("Super + Ctrl + r", "Hot-reload Qtile configuration in-place without closing apps", "Reload"),
            ("Super + Ctrl + q", "Gracefully shut down and exit Qtile window manager", "Exit"),
            ("Ctrl + Alt + Delete", "Alternate shortcut to exit Qtile session", "Exit"),
        ],
    },
]


class AccordionSection:
    """An individual expandable section in the cheatsheet."""

    def __init__(self, parent, data, on_toggle_callback):
        self.parent = parent
        self.data = data
        self.on_toggle = on_toggle_callback
        self.is_expanded = True  # Expanded by default for instant overview
        self.item_widgets = []

        # Container card
        self.card = tk.Frame(
            parent,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        self.card.pack(fill="x", padx=12, pady=4)

        # Header bar
        self.header = tk.Frame(self.card, bg=THEME["bg_card"], cursor="hand2")
        self.header.pack(fill="x", ipady=7, padx=12)

        # Indicator arrow
        self.lbl_arrow = tk.Label(
            self.header,
            text="▼",
            font=("DejaVu Sans Mono", 10),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
            width=2,
            anchor="w",
        )
        self.lbl_arrow.pack(side="left")

        # Category icon (FontAwesome)
        self.lbl_icon = tk.Label(
            self.header,
            text=data.get("icon", "\uf11c"),
            font=("FontAwesome", 12),
            fg=data.get("color", THEME["accent_blue"]),
            bg=THEME["bg_card"],
            width=2,
            anchor="center",
        )
        self.lbl_icon.pack(side="left", padx=(0, 6))

        # Category title
        self.lbl_title = tk.Label(
            self.header,
            text=data["category"],
            font=("DejaVu Sans Mono", 11, "bold"),
            fg=data.get("color", THEME["accent_blue"]),
            bg=THEME["bg_card"],
            anchor="w",
        )
        self.lbl_title.pack(side="left", fill="x", expand=True)

        # Count badge
        self.lbl_count = tk.Label(
            self.header,
            text=f"{len(data['items'])} keys",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_hover"],
            padx=8,
            pady=2,
        )
        self.lbl_count.pack(side="right")

        # Body container
        self.body = tk.Frame(self.card, bg=THEME["bg_surface"])
        self.body.pack(fill="x", padx=2, pady=2)

        # Render items initially
        self._render_items()

        # Bind clicks & hover
        for w in (self.header, self.lbl_arrow, self.lbl_icon, self.lbl_title, self.lbl_count):
            w.bind("<Button-1>", lambda e: self.toggle())
            w.bind("<Enter>", lambda e: self._on_hover(True))
            w.bind("<Leave>", lambda e: self._on_hover(False))

    def _on_hover(self, hovering):
        color = THEME["bg_hover"] if hovering else THEME["bg_card"]
        self.header.configure(bg=color)
        self.lbl_arrow.configure(bg=color)
        self.lbl_icon.configure(bg=color)
        self.lbl_title.configure(bg=color)

    def toggle(self, force_state=None):
        new_state = (not self.is_expanded) if force_state is None else force_state
        if new_state == self.is_expanded:
            return

        self.is_expanded = new_state
        if self.is_expanded:
            self.lbl_arrow.configure(text="▼", fg=THEME["key_fg"])
            self.card.configure(highlightbackground=THEME["border_focus"])
            self._render_items()
            self.body.pack(fill="x", padx=2, pady=2)
        else:
            self.lbl_arrow.configure(text="▶", fg=THEME["fg_dim"])
            self.card.configure(highlightbackground=THEME["border"])
            self.body.pack_forget()

        if self.on_toggle:
            self.on_toggle()

    def _render_items(self, filter_query=None):
        for w in self.item_widgets:
            w.destroy()
        self.item_widgets.clear()

        query = (filter_query or "").strip().lower()

        for idx, (keys, desc, tag) in enumerate(self.data["items"]):
            if query and not (query in keys.lower() or query in desc.lower() or query in tag.lower()):
                continue

            row_bg = THEME["bg_surface"] if idx % 2 == 0 else THEME["bg_card"]
            row = tk.Frame(self.body, bg=row_bg)
            row.pack(fill="x", padx=6, pady=2, ipady=4)

            # Key pill badge
            pill = tk.Label(
                row,
                text=f" {keys} ",
                font=("DejaVu Sans Mono", 10, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=8,
                pady=3,
                bd=0,
                anchor="w",
            )
            pill.pack(side="left", padx=(6, 12))

            # Description
            desc_lbl = tk.Label(
                row,
                text=desc,
                font=("DejaVu Sans Mono", 10),
                fg=THEME["fg"],
                bg=row_bg,
                anchor="w",
                justify="left",
            )
            desc_lbl.pack(side="left", fill="x", expand=True)

            # Tag / Category badge
            tag_lbl = tk.Label(
                row,
                text=tag,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=row_bg,
                padx=8,
            )
            tag_lbl.pack(side="right")

            self.item_widgets.append(row)

    def apply_filter(self, query):
        q = query.strip().lower()
        if not q:
            self.card.pack(fill="x", padx=12, pady=4)
            if self.is_expanded:
                self._render_items()
            return

        cat_matches = q in self.data["category"].lower()
        matching_items = [
            item for item in self.data["items"]
            if cat_matches or q in item[0].lower() or q in item[1].lower() or q in item[2].lower()
        ]

        if matching_items:
            self.card.pack(fill="x", padx=12, pady=4)
            self.toggle(force_state=True)
            self._render_items(filter_query=q)
        else:
            self.card.pack_forget()


class KeyCheatApp:
    """Main Application Window."""

    def __init__(self, root):
        self.root = root
        self.root.title("Qtile Keybindings Cheatsheet")

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        self.root.configure(bg=THEME["bg"])
        self.sections = []

        # Build UI
        self._build_header()
        self._build_scroll_area()
        self._build_footer()
        self._populate_sections()
        self._bind_keys()

        # Focus search immediately
        self.search_entry.focus_set()

    def _build_header(self):
        """Top bar with title, search input, and Expand/Collapse buttons."""
        header_bar = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        header_bar.pack(fill="x", padx=12, pady=(12, 6), ipady=8)

        # Title & Keyboard Icon
        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=14)

        lbl_logo = tk.Label(
            title_box,
            text="\uf11c",  # FontAwesome keyboard icon
            font=("FontAwesome", 15),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
        )
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_title = tk.Label(
            title_box,
            text="QTILE KEYBINDINGS",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(side="left")

        # Search Bar
        search_frame = tk.Frame(
            header_bar,
            bg=THEME["bg_surface"],
            bd=1,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        search_frame.pack(side="left", fill="x", expand=True, padx=20, ipady=3)

        lbl_search_icon = tk.Label(
            search_frame,
            text="\uf002",  # fa-search
            font=("FontAwesome", 10),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
        )
        lbl_search_icon.pack(side="left", padx=(8, 4))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("DejaVu Sans Mono", 11),
            fg=THEME["fg"],
            bg=THEME["bg_surface"],
            insertbackground=THEME["key_fg"],
            bd=0,
            highlightthickness=0,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6)

        # Expand / Collapse All Buttons
        btn_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        btn_box.pack(side="right", padx=12)

        self.btn_expand_all = tk.Button(
            btn_box,
            text="▼ Expand All",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg"],
            bg=THEME["bg_hover"],
            activebackground=THEME["bg_active"],
            activeforeground=THEME["key_fg"],
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.expand_all,
        )
        self.btn_expand_all.pack(side="left", padx=4)

        self.btn_collapse_all = tk.Button(
            btn_box,
            text="▶ Collapse All",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg"],
            bg=THEME["bg_hover"],
            activebackground=THEME["bg_active"],
            activeforeground=THEME["key_fg"],
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.collapse_all,
        )
        self.btn_collapse_all.pack(side="left", padx=4)

    def _build_scroll_area(self):
        """Scrollable canvas hosting the accordion sections."""
        container = tk.Frame(self.root, bg=THEME["bg"])
        container.pack(fill="both", expand=True, padx=0, pady=2)

        self.canvas = tk.Canvas(
            container,
            bg=THEME["bg"],
            bd=0,
            highlightthickness=0,
        )
        self.scrollbar = tk.Scrollbar(
            container,
            orient="vertical",
            command=self.canvas.yview,
            bg=THEME["bg_card"],
            troughcolor=THEME["bg"],
            activebackground=THEME["accent_blue"],
            bd=0,
            width=10,
        )

        self.scroll_frame = tk.Frame(self.canvas, bg=THEME["bg"])
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )
        self.canvas.configure(xscrollcommand=None, yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width),
        )

        # Mouse wheel bindings
        self.root.bind_all("<Button-4>", lambda e: self._on_scroll(-1))
        self.root.bind_all("<Button-5>", lambda e: self._on_scroll(1))
        self.root.bind_all("<MouseWheel>", lambda e: self._on_scroll(-1 if e.delta > 0 else 1))

    def _build_footer(self):
        """Bottom status bar with action hints and total count."""
        footer = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12), ipady=5)

        hints = [
            ("j / k or Arrows", "Scroll"),
            ("/", "Search"),
            ("e / c", "Expand / Collapse"),
            ("Esc / q", "Close"),
        ]

        for key, desc in hints:
            pill = tk.Frame(footer, bg=THEME["bg_card"])
            pill.pack(side="left", padx=8)

            lbl_k = tk.Label(
                pill,
                text=key,
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=6,
                pady=2,
            )
            lbl_k.pack(side="left")

            lbl_d = tk.Label(
                pill,
                text=desc,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_card"],
                padx=4,
            )
            lbl_d.pack(side="left")

        # Total keybindings count
        total_keys = sum(len(sec["items"]) for sec in KEYBINDINGS_DATA)
        self.lbl_status = tk.Label(
            footer,
            text=f"Total: {total_keys} Shortcuts",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
            padx=12,
        )
        self.lbl_status.pack(side="right")

    def _populate_sections(self):
        """Instantiate accordion sections from data."""
        for item in KEYBINDINGS_DATA:
            sec = AccordionSection(
                self.scroll_frame, item, on_toggle_callback=self._update_scrollregion
            )
            self.sections.append(sec)

    def _update_scrollregion(self):
        self.scroll_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_scroll(self, direction):
        self.canvas.yview_scroll(direction * 2, "units")

    def _on_search_change(self, *args):
        query = self.search_var.get()
        for sec in self.sections:
            sec.apply_filter(query)
        self._update_scrollregion()

    def expand_all(self):
        for sec in self.sections:
            sec.toggle(force_state=True)
        self._update_scrollregion()

    def collapse_all(self):
        for sec in self.sections:
            sec.toggle(force_state=False)
        self._update_scrollregion()

    def _bind_keys(self):
        """Global key navigation."""
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("q", self._on_q)
        self.root.bind("<slash>", self._on_slash)
        self.root.bind("j", lambda e: self._on_scroll(1) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("k", lambda e: self._on_scroll(-1) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("<Down>", lambda e: self._on_scroll(1))
        self.root.bind("<Up>", lambda e: self._on_scroll(-1))
        self.root.bind("<Next>", lambda e: self.canvas.yview_scroll(1, "pages"))
        self.root.bind("<Prior>", lambda e: self.canvas.yview_scroll(-1, "pages"))
        self.root.bind("e", lambda e: self.expand_all() if self.root.focus_get() != self.search_entry else None)
        self.root.bind("c", lambda e: self.collapse_all() if self.root.focus_get() != self.search_entry else None)

    def _on_escape(self, event):
        if self.root.focus_get() == self.search_entry and self.search_var.get():
            self.search_var.set("")
            self.root.focus_set()
        else:
            self.root.destroy()

    def _on_q(self, event):
        if self.root.focus_get() != self.search_entry:
            self.root.destroy()

    def _on_slash(self, event):
        if self.root.focus_get() != self.search_entry:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            return "break"


def main():
    root = tk.Tk(className="key-cheat")
    app = KeyCheatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
