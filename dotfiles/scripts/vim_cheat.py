#!/usr/bin/env python3
"""
Vim Cheatsheet Dropdown for Qtile
=================================
A fast, searchable, expandable Vim reference styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Expandable / Collapsible accordions for each Vim category
- Instant live search across all keys, descriptions, and modes
- Keyboard accessible (j/k to scroll, / to search, Esc/q to dismiss)
- Full Gruvbox Dark aesthetic matching Qtile & Kitty
- Native X11 WM_CLASS ("vim-cheat") for Qtile ScratchPad integration
- Uses native FontAwesome & DejaVu fonts (no missing glyph boxes)
"""

import sys
import tkinter as tk
from tkinter import font as tkfont

# ==============================================================================
# Theme: Central Gruvbox (Dark / Light via Super + o)
# ==============================================================================
try:
    import os
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
# Vim Cheatsheet Dataset
# (Icons use FontAwesome codepoints matching Qtile's system font)
# ==============================================================================
CHEATSHEET_DATA = [
    {
        "category": "Cursor Navigation & Motions",
        "icon": "\uf14e",  # fa-compass
        "color": THEME["accent_aqua"],
        "items": [
            ("h, j, k, l", "Move cursor Left, Down, Up, Right", "Normal"),
            ("w / W", "Jump forward to start of next word / WORD (space-delimited)", "Normal"),
            ("b / B", "Jump backward to start of previous word / WORD", "Normal"),
            ("e / E", "Jump forward to end of current/next word / WORD", "Normal"),
            ("0 / ^", "Jump to absolute start of line / first non-blank character", "Normal"),
            ("$", "Jump to end of line", "Normal"),
            ("gg / G", "Jump to first line / last line of buffer", "Normal"),
            (":{N} or {N}G", "Jump directly to line number N", "Normal"),
            ("H / M / L", "Jump to High (top), Middle, Low (bottom) of screen", "Normal"),
            ("Ctrl+u / Ctrl+d", "Scroll window half-page Up / Down", "Normal"),
            ("Ctrl+b / Ctrl+f", "Scroll window full-page Back / Forward", "Normal"),
            ("f{char} / F{char}", "Find & jump forward / backward to {char} on current line", "Normal"),
            ("t{char} / T{char}", "Jump 'till before' / 'after' {char} on current line", "Normal"),
            ("; / ,", "Repeat last f/F/t/T search forward / backward", "Normal"),
            ("%", "Jump to matching parenthesis, bracket, or brace ( ), [ ], { }", "Normal"),
        ],
    },
    {
        "category": "Insert & Entry Modes",
        "icon": "\uf040",  # fa-pencil
        "color": THEME["accent_green"],
        "items": [
            ("i / I", "Insert before cursor / Insert at beginning of line", "Insert"),
            ("a / A", "Append after cursor / Append at end of line", "Insert"),
            ("o / O", "Open new line below / Open new line above", "Insert"),
            ("s / S", "Substitute character (delete & insert) / Substitute whole line", "Insert"),
            ("C", "Change to end of line (shorthand for c$)", "Insert"),
            ("cc", "Change entire current line", "Insert"),
            ("gi", "Insert text at the position where last insert mode exited", "Insert"),
            ("Esc / Ctrl+[", "Exit to Normal mode", "Mode"),
        ],
    },
    {
        "category": "Editing, Deletion & Change",
        "icon": "\uf044",  # fa-edit
        "color": THEME["accent_red"],
        "items": [
            ("x / X", "Delete character under cursor / Delete character before cursor", "Edit"),
            ("dw / de / db", "Delete word forward / to end of word / backward", "Edit"),
            ("dd", "Delete (cut) entire current line ({N}dd for N lines)", "Edit"),
            ("D", "Delete from cursor to end of line (d$)", "Edit"),
            ("cw / cb", "Change word forward / change word backward", "Edit"),
            ("r{char}", "Replace character under cursor with {char}", "Edit"),
            ("R", "Enter Replace mode (overwrite characters)", "Edit"),
            ("J", "Join current line with line below into single line", "Edit"),
            ("~", "Toggle uppercase/lowercase of character under cursor", "Edit"),
            ("gu{motion} / gU{motion}", "Make text lowercase / uppercase over motion", "Edit"),
            ("u / Ctrl+r", "Undo last change / Redo last undone change", "History"),
            (".", "Repeat last change command exactly", "Action"),
        ],
    },
    {
        "category": "Visual Mode & Selections",
        "icon": "\uf06e",  # fa-eye
        "color": THEME["accent_purple"],
        "items": [
            ("v", "Start character-wise Visual mode", "Visual"),
            ("V", "Start line-wise Visual mode", "Visual"),
            ("Ctrl+v", "Start block-wise (column) Visual mode", "Visual"),
            ("gv", "Re-select previous visual selection area", "Visual"),
            ("o", "Move cursor to opposite end of visual selection", "Visual"),
            ("> / <", "Indent / Unindent selected text by shiftwidth", "Visual"),
            ("y / d / c", "Yank / Delete / Change selected text", "Visual"),
            ("I / A (in block mode)", "Insert / Append text across all selected columns simultaneously", "Visual"),
            ("u / U (in visual)", "Convert selected text to lowercase / uppercase", "Visual"),
        ],
    },
    {
        "category": "Copy, Cut & Paste (Registers)",
        "icon": "\uf0c5",  # fa-copy
        "color": THEME["key_fg"],
        "items": [
            ("yy or Y", "Yank (copy) current line ({N}yy for N lines)", "Yank"),
            ("yw / y$", "Yank word / Yank from cursor to end of line", "Yank"),
            ("p / P", "Paste register after cursor / before cursor", "Paste"),
            ("\"+y / \"+p", "Yank to system clipboard / Paste from system clipboard", "Clipboard"),
            ("\"*y / \"*p", "Yank to primary selection / Paste primary selection", "Clipboard"),
            ("\"0p", "Paste from last explicit yank (ignores accidental dd deletions)", "Register"),
            ("\"_d", "Delete into black hole register (doesn't overwrite clipboard)", "Register"),
            (":reg", "Show contents of all vim registers", "Command"),
        ],
    },
    {
        "category": "Text Objects (The Vim Superpower)",
        "icon": "\uf1b2",  # fa-cube
        "color": THEME["accent_blue"],
        "items": [
            ("ciw / caw", "Change inner word / change a word (includes surrounding space)", "Object"),
            ("diw / daw", "Delete inner word / delete a word with space", "Object"),
            ("ci\" / ca\"", "Change inside \"quotes\" / change including quotes", "Object"),
            ("ci' / ca'", "Change inside 'single quotes' / change including quotes", "Object"),
            ("ci( or cib", "Change inside (parentheses) / ca( includes parentheses", "Object"),
            ("ci{ or ciB", "Change inside {braces} / ca{ includes braces", "Object"),
            ("ci[ / ca[", "Change inside [brackets] / ca[ includes brackets", "Object"),
            ("cit / cat", "Change inside XML/HTML <tag> / cat includes tags", "Object"),
            ("cip / cap", "Change inside paragraph / ca(p) includes paragraph", "Object"),
            ("Formula: {op}{i/a}{obj}", "Combine operator (c, d, y, v) + inner/around (i, a) + target", "Concept"),
        ],
    },
    {
        "category": "Search & Pattern Matching",
        "icon": "\uf002",  # fa-search
        "color": THEME["accent_aqua"],
        "items": [
            ("/{pattern}", "Search forward for regex pattern", "Search"),
            ("?{pattern}", "Search backward for regex pattern", "Search"),
            ("n / N", "Repeat search in same direction / opposite direction", "Search"),
            ("* / #", "Search forward / backward for exact word under cursor", "Search"),
            (":%s/old/new/g", "Replace all occurrences of 'old' with 'new' in entire file", "Replace"),
            (":%s/old/new/gc", "Replace all occurrences with interactive confirmation prompt", "Replace"),
            (":s/old/new/g", "Replace all occurrences on current line only", "Replace"),
            (":noh", "Turn off search highlight until next search", "Search"),
        ],
    },
    {
        "category": "Windows, Splits & Tabs",
        "icon": "\uf2d0",  # fa-window-maximize
        "color": THEME["accent_green"],
        "items": [
            (":sp / :vsp [file]", "Split window horizontally / vertically", "Window"),
            ("Ctrl+w h / j / k / l", "Move focus to window Left, Down, Up, Right", "Window"),
            ("Ctrl+w w", "Cycle focus to next window in current tab", "Window"),
            ("Ctrl+w c / q", "Close active window / Quit active window", "Window"),
            ("Ctrl+w o", "Close all other windows except current active one (Only)", "Window"),
            ("Ctrl+w =", "Make all split windows equal height & width", "Window"),
            ("Ctrl+w r / R", "Rotate windows downward / upward", "Window"),
            (":tabnew [file]", "Open new tab page", "Tab"),
            ("gt / gT", "Switch to next tab / previous tab", "Tab"),
            ("{N}gt", "Go directly to tab number N", "Tab"),
            (":tabclose", "Close current tab page", "Tab"),
        ],
    },
    {
        "category": "Marks, Jumps & History",
        "icon": "\uf02e",  # fa-bookmark
        "color": THEME["accent_purple"],
        "items": [
            ("m{a-z}", "Set local mark at cursor ({a-z} specific to current file)", "Mark"),
            ("m{A-Z}", "Set global uppercase mark (can jump between different files)", "Mark"),
            ("'{mark}", "Jump to line of mark", "Jump"),
            ("`{mark}", "Jump to exact line and column position of mark", "Jump"),
            ("'' / ``", "Jump back to position before last jump", "Jump"),
            ("Ctrl+o / Ctrl+i", "Jump backward / forward in jump history list", "Jump"),
            (":jumps", "View list of jump locations", "Command"),
            (":marks", "View list of set marks", "Command"),
        ],
    },
    {
        "category": "Buffers & File Management",
        "icon": "\uf15b",  # fa-file-text-o
        "color": THEME["key_fg"],
        "items": [
            (":w / :w!", "Save file / Force write file", "File"),
            (":q / :q!", "Quit / Force quit discarding unsaved changes", "File"),
            (":wq or :x or ZZ", "Write file and quit", "File"),
            ("ZQ", "Quit immediately without saving (same as :q!)", "File"),
            (":e {file}", "Edit file in current buffer", "Buffer"),
            (":ls or :buffers", "List all active open buffers", "Buffer"),
            (":bn / :bp", "Switch to next buffer / previous buffer", "Buffer"),
            (":b {N or name}", "Jump to buffer by number or filename match", "Buffer"),
            (":bd", "Delete (close) current buffer", "Buffer"),
        ],
    },
]


class AccordionSection:
    """An individual expandable section in the cheatsheet."""

    def __init__(self, parent, data, on_toggle_callback):
        self.parent = parent
        self.data = data
        self.on_toggle = on_toggle_callback
        self.is_expanded = False
        self.item_widgets = []

        # Container card
        self.card = tk.Frame(parent, bg=THEME["bg_card"], bd=0, highlightthickness=1,
                             highlightbackground=THEME["border"])
        self.card.pack(fill="x", padx=12, pady=4)

        # Header bar
        self.header = tk.Frame(self.card, bg=THEME["bg_card"], cursor="hand2")
        self.header.pack(fill="x", ipady=8, padx=12)

        # Indicator arrow (using standard DejaVu geometric triangle)
        self.lbl_arrow = tk.Label(
            self.header,
            text="▶",
            font=("DejaVu Sans Mono", 10),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
            width=2,
            anchor="w",
        )
        self.lbl_arrow.pack(side="left")

        # Category icon (FontAwesome)
        self.lbl_icon = tk.Label(
            self.header,
            text=data.get("icon", "\uf121"),
            font=("FontAwesome", 11),
            fg=data.get("color", THEME["accent_blue"]),
            bg=THEME["bg_card"],
            width=2,
            anchor="center",
        )
        self.lbl_icon.pack(side="left", padx=(0, 6))

        # Category title (DejaVu Sans Mono)
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

        # Body container (items placed here when expanded)
        self.body = tk.Frame(self.card, bg=THEME["bg_surface"])

        # Bind clicks and hovers to entire header & children
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
        # Clear old rows
        for w in self.item_widgets:
            w.destroy()
        self.item_widgets.clear()

        query = (filter_query or "").strip().lower()

        for idx, (keys, desc, mode) in enumerate(self.data["items"]):
            # Filter check
            if query and not (query in keys.lower() or query in desc.lower() or query in mode.lower()):
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

            # Mode pill
            mode_lbl = tk.Label(
                row,
                text=mode,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_hover"],
                padx=6,
                pady=1,
            )
            mode_lbl.pack(side="right", padx=8)

            self.item_widgets.append(row)

    def apply_filter(self, query):
        """Show matching items, hide section if no match."""
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


class VimCheatApp:
    """Main Application Window."""

    def __init__(self, root):
        self.root = root
        self.root.title("Vim Cheatsheet")

        # Dialog attribute for X11 WMs
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
        header_bar = tk.Frame(self.root, bg=THEME["bg_card"], bd=0, highlightthickness=1,
                              highlightbackground=THEME["border"])
        header_bar.pack(fill="x", padx=12, pady=(12, 6), ipady=8)

        # Title & Terminal Icon
        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=14)

        lbl_logo = tk.Label(
            title_box,
            text="\uf120",  # FontAwesome terminal icon
            font=("FontAwesome", 15),
            fg=THEME["accent_green"],
            bg=THEME["bg_card"],
        )
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_title = tk.Label(
            title_box,
            text="VIM CHEATSHEET",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(side="left")

        # Search Bar
        search_frame = tk.Frame(header_bar, bg=THEME["bg_surface"], bd=1,
                                highlightthickness=1, highlightbackground=THEME["border"])
        search_frame.pack(side="left", fill="x", expand=True, padx=20, ipady=3)

        lbl_search_icon = tk.Label(
            search_frame,
            text="\uf002",  # FontAwesome search icon
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

        self.content_frame = tk.Frame(self.canvas, bg=THEME["bg"])
        self.content_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        self.canvas.configure(xscrollcommand=None, yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Keep frame width matched to canvas width
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width),
        )

        # Mouse wheel bindings
        self.root.bind_all("<Button-4>", lambda e: self._on_scroll(-1))
        self.root.bind_all("<Button-5>", lambda e: self._on_scroll(1))
        self.root.bind_all("<MouseWheel>", lambda e: self._on_scroll(-1 if e.delta > 0 else 1))

    def _build_footer(self):
        """Bottom status bar with helpful keyboard hints."""
        footer = tk.Frame(self.root, bg=THEME["bg_card"], bd=0, highlightthickness=1,
                          highlightbackground=THEME["border"])
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12), ipady=5)

        hints = [
            ("Esc / q", "Dismiss"),
            ("/", "Focus Search"),
            ("j / k", "Scroll"),
            ("Super+v", "Toggle Qtile Scratchpad"),
        ]

        for key, action in hints:
            box = tk.Frame(footer, bg=THEME["bg_card"])
            box.pack(side="left", padx=10)

            k_lbl = tk.Label(
                box,
                text=key,
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=5,
                pady=1,
            )
            k_lbl.pack(side="left", padx=(0, 4))

            a_lbl = tk.Label(
                box,
                text=action,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_card"],
            )
            a_lbl.pack(side="left")

    def _populate_sections(self):
        for data in CHEATSHEET_DATA:
            sec = AccordionSection(
                self.content_frame,
                data,
                on_toggle_callback=self._update_scrollregion,
            )
            self.sections.append(sec)

        # Expand first two sections by default
        if self.sections:
            self.sections[0].toggle(force_state=True)
            if len(self.sections) > 1:
                self.sections[1].toggle(force_state=True)

    def _update_scrollregion(self):
        self.root.update_idletasks()
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
    root = tk.Tk(className="vim-cheat")
    app = VimCheatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
