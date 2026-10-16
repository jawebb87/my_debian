#!/usr/bin/env python3
"""
Clipboard History Scratchpad for Qtile
======================================
A fast, keyboard-driven X11 clipboard history manager styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Persistent clipboard history stored in ~/.cache/clip_pad/history.json
- Background polling daemon tracks X11 CLIPBOARD selection changes live
- Instant keyboard actions (Enter/c: copy to clipboard, d: delete, C: clear all)
- Synchronizes both CLIPBOARD and PRIMARY X11 selections upon copy
- Live search/filtering across text content
- Formats type detection (URLs, Code, Multi-line, Plain text)
- Native X11 WM_CLASS ("clip-pad") for Qtile ScratchPad integration
"""

import sys
import os
import json
import time
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
        "bg": "#282828", "bg_surface": "#32302f", "bg_card": "#3c3836",
        "bg_hover": "#504945", "bg_selected": "#3c3836", "border": "#504945",
        "border_focus": "#83a598", "fg": "#ebdbb2", "fg_dim": "#a89984",
        "fg_header": "#fbf1c7", "key_bg": "#1d2021", "key_fg": "#fabd2f",
        "status_running": "#b8bb26", "status_stopped": "#fb4934",
        "status_paused": "#fabd2f", "accent_blue": "#83a598",
        "accent_aqua": "#8ec07c", "accent_purple": "#d3869b",
    }

CACHE_DIR = os.path.expanduser("~/.cache/clip_pad")
HISTORY_FILE = os.path.join(CACHE_DIR, "history.json")
MAX_HISTORY_ENTRIES = 100


def get_current_xclip() -> str | None:
    """Retrieve the current clipboard text via xclip."""
    try:
        res = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            text=True,
            check=False,
            timeout=1,
        )
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None


def set_xclip(text: str) -> bool:
    """Push text to both CLIPBOARD and PRIMARY X11 buffers."""
    success = True
    for selection in ("clipboard", "primary"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", selection],
                input=text,
                text=True,
                check=False,
                timeout=1,
            )
            if res.returncode != 0:
                success = False
        except Exception:
            success = False
    return success


def detect_type(text: str) -> tuple[str, str]:
    """Detect category of clip and assign badge label and theme color."""
    stripped = text.strip()
    if stripped.startswith(("http://", "https://", "ftp://", "gemini://")):
        return "URL", THEME["accent_aqua"]
    if "\n" in stripped:
        lines = stripped.split("\n")
        if any(line.strip().startswith(("def ", "class ", "import ", "const ", "let ", "function ", "#!/")) for line in lines):
            return "CODE", THEME["accent_purple"]
        return f"{len(lines)} LINES", THEME["accent_blue"]
    if len(stripped) < 40 and not any(c.isspace() for c in stripped) and any(c in "0123456789abcdef" for c in stripped):
        return "HASH/TOKEN", THEME["key_fg"]
    return "TEXT", THEME["fg_dim"]


class ClipCard:
    """Widget representing a single clipboard entry row."""

    def __init__(self, parent, entry_data, index, on_click_callback, on_double_click_callback):
        self.parent = parent
        self.data = entry_data
        self.index = index
        self.on_click = on_click_callback
        self.on_double_click = on_double_click_callback
        self.is_selected = False

        self.card = tk.Frame(
            parent,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=2,
            highlightbackground=THEME["border"],
            cursor="hand2",
        )
        self.card.pack(fill="x", padx=12, pady=3)

        self.inner = tk.Frame(self.card, bg=THEME["bg_card"])
        self.inner.pack(fill="x", padx=10, pady=6)

        # Top row: Type Badge, Index, Timestamp, Length Metrics
        top_row = tk.Frame(self.inner, bg=THEME["bg_card"])
        top_row.pack(fill="x")

        type_label, type_color = detect_type(self.data.get("text", ""))

        # Index / Type Badge
        self.lbl_badge = tk.Label(
            top_row,
            text=f" #{self.index + 1}  {type_label} ",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=type_color,
            bg=THEME["key_bg"],
            padx=6,
            pady=2,
        )
        self.lbl_badge.pack(side="left")

        # Timestamp
        ts = self.data.get("timestamp", time.time())
        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
        self.lbl_time = tk.Label(
            top_row,
            text=f"Copied at {time_str}",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
            padx=8,
        )
        self.lbl_time.pack(side="left")

        # Metrics pill
        text_content = self.data.get("text", "")
        char_count = len(text_content)
        line_count = len(text_content.splitlines()) if text_content else 0
        metrics_str = f"{char_count} chars  |  {line_count} {'line' if line_count == 1 else 'lines'}"

        self.lbl_metrics = tk.Label(
            top_row,
            text=metrics_str,
            font=("DejaVu Sans Mono", 9),
            fg=THEME["accent_blue"],
            bg=THEME["key_bg"],
            padx=8,
            pady=2,
        )
        self.lbl_metrics.pack(side="right")

        # Preview snippet (up to 3 preview lines)
        lines = [l.strip() for l in text_content.splitlines() if l.strip()]
        preview_text = "  ⏎  ".join(lines[:3]) if lines else "[Empty]"
        if len(preview_text) > 130:
            preview_text = preview_text[:127] + "..."

        self.lbl_preview = tk.Label(
            self.inner,
            text=preview_text,
            font=("DejaVu Sans Mono", 10),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
            anchor="w",
            justify="left",
        )
        self.lbl_preview.pack(fill="x", pady=(5, 0))

        # Event bindings
        self._bind_events()

    def _bind_events(self):
        widgets = [self.card, self.inner, self.lbl_badge, self.lbl_time, self.lbl_metrics, self.lbl_preview]
        for w in widgets:
            w.bind("<Button-1>", lambda e: self.on_click(self))
            w.bind("<Double-Button-1>", lambda e: self.on_double_click(self))

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.card.configure(highlightbackground=THEME["border_focus"], bg=THEME["bg_selected"])
            self.inner.configure(bg=THEME["bg_selected"])
            self.lbl_time.configure(bg=THEME["bg_selected"])
            self.lbl_preview.configure(bg=THEME["bg_selected"])
        else:
            self.card.configure(highlightbackground=THEME["border"], bg=THEME["bg_card"])
            self.inner.configure(bg=THEME["bg_card"])
            self.lbl_time.configure(bg=THEME["bg_card"])
            self.lbl_preview.configure(bg=THEME["bg_card"])


class ClipPadApp:
    """Main Application Window."""

    def __init__(self, root):
        self.root = root
        self.root.title("Clipboard History")
        self.root.configure(bg=THEME["bg"])

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        # Set initial dimensions to match Qtile DropDown proportions
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = min(1500, int(sw * 0.8))
        target_h = int(sh * 0.88)
        self.root.geometry(f"{target_w}x{target_h}")

        self.history = []
        self.cards = []
        self.selected_index = 0
        self.last_clipboard = ""

        # UI Layout
        self._build_header()
        self._build_content_area()
        self._build_footer()
        self._bind_keys()

        # Load history from cache file
        self._load_history()

        # Check active clipboard immediately
        current_clip = get_current_xclip()
        if current_clip:
            self.last_clipboard = current_clip
            self._add_to_history(current_clip, save=False)

        self._filter_clips()

        # Start background polling thread
        self.polling_active = True
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.poll_thread = threading.Thread(target=self._clipboard_poller, daemon=True)
        self.poll_thread.start()

    def _build_header(self):
        """Top bar with title, search input, and counts."""
        header_bar = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        header_bar.pack(fill="x", padx=12, pady=(12, 6), ipady=8)

        # Title & Icon
        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=14)

        lbl_logo = tk.Label(
            title_box,
            text="\uf0ea",  # FontAwesome clipboard icon
            font=("FontAwesome", 15),
            fg=THEME["accent_aqua"],
            bg=THEME["bg_card"],
        )
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_title = tk.Label(
            title_box,
            text="CLIPBOARD HISTORY",
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
        self.search_var.trace_add("write", lambda *args: self._filter_clips())

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

        # Summary Counter Badge
        self.lbl_counts = tk.Label(
            header_bar,
            text="0 Clips",
            font=("DejaVu Sans Mono", 10, "bold"),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
            padx=12,
        )
        self.lbl_counts.pack(side="right")

    def _build_content_area(self):
        """Scrollable canvas for the clip cards."""
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

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width),
        )

        # Mouse wheel bindings
        self.root.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def _build_footer(self):
        """Bottom status bar with action pills and toast notification."""
        footer = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12), ipady=5)

        hints = [
            ("Enter / c", "Copy"),
            ("d", "Delete"),
            ("Shift+C", "Clear All"),
            ("j/k", "Navigate"),
            ("/", "Search"),
            ("Esc/q", "Close"),
        ]

        for key, desc in hints:
            pill = tk.Frame(footer, bg=THEME["bg_card"])
            pill.pack(side="left", padx=6)

            lbl_k = tk.Label(
                pill,
                text=key,
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=5,
                pady=1,
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

        # Live Toast / Feedback Message
        self.lbl_toast = tk.Label(
            footer,
            text="Ready",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["accent_aqua"],
            bg=THEME["bg_card"],
            padx=10,
        )
        self.lbl_toast.pack(side="right")

    def show_toast(self, msg: str, color: str = None):
        self.lbl_toast.configure(text=msg, fg=color or THEME["accent_aqua"])

    # ==========================================================================
    # History & Persistence
    # ==========================================================================
    def _load_history(self):
        """Load clipboard history from disk."""
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)

        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def _save_history(self):
        """Save clipboard history to disk atomically with restricted permissions."""
        fd = None
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
            tmp_path = f"{HISTORY_FILE}.tmp"
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                fd = None  # Stream ownership transferred to context manager
                json.dump(self.history[:MAX_HISTORY_ENTRIES], f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, HISTORY_FILE)
        except Exception:
            pass
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _add_to_history(self, text: str, save: bool = True) -> bool:
        """Add new text entry if not identical to the most recent."""
        stripped = text.strip()
        if not stripped:
            return False

        # If already at the top of history, do nothing
        if self.history and self.history[0].get("text") == text:
            return False

        # If it exists elsewhere in history, remove it so it moves to top
        self.history = [e for e in self.history if e.get("text") != text]

        new_entry = {
            "text": text,
            "timestamp": time.time(),
        }
        self.history.insert(0, new_entry)
        if len(self.history) > MAX_HISTORY_ENTRIES:
            self.history = self.history[:MAX_HISTORY_ENTRIES]

        if save:
            self._save_history()
        return True

    def _clipboard_poller(self):
        """Background daemon polling X11 clipboard for new contents."""
        while self.polling_active:
            try:
                current = get_current_xclip()
                if current and current != self.last_clipboard:
                    self.last_clipboard = current
                    self.root.after(0, lambda c=current: self._on_external_clip(c))
            except Exception:
                pass
            time.sleep(0.8)

    def _on_external_clip(self, clip_text: str):
        if not self.polling_active:
            return
        if self._add_to_history(clip_text, save=True):
            self._filter_clips()
            self.show_toast("✓ New clip captured")

    # ==========================================================================
    # Rendering & Filtering
    # ==========================================================================
    def _filter_clips(self):
        query = self.search_var.get().strip().lower()

        # Destroy old cards
        for c in self.cards:
            c.card.destroy()
        self.cards.clear()

        matched_entries = []
        for idx, entry in enumerate(self.history):
            text = entry.get("text", "")
            if query and query not in text.lower():
                continue
            matched_entries.append((idx, entry))

        for display_idx, (real_idx, entry) in enumerate(matched_entries):
            card = ClipCard(
                self.content_frame,
                entry,
                display_idx,
                on_click_callback=self._select_card,
                on_double_click_callback=self._copy_and_toast,
            )
            self.cards.append(card)

        self.lbl_counts.configure(text=f"● {len(self.cards)} Clips")

        if self.cards:
            if self.selected_index >= len(self.cards):
                self.selected_index = len(self.cards) - 1
            self._select_card(self.cards[self.selected_index])
        else:
            self.selected_index = 0

        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _select_card(self, card: ClipCard):
        for idx, c in enumerate(self.cards):
            if c == card:
                c.set_selected(True)
                self.selected_index = idx
            else:
                c.set_selected(False)

    def _copy_and_toast(self, card: ClipCard = None):
        """Copy selected clip back to clipboard and toast."""
        if not self.cards:
            return

        target_card = card or (self.cards[self.selected_index] if 0 <= self.selected_index < len(self.cards) else None)
        if not target_card:
            return

        text = target_card.data.get("text", "")
        self.last_clipboard = text
        success = set_xclip(text)

        if success:
            # Move to top of history
            self._add_to_history(text, save=True)
            self._filter_clips()
            self.show_toast("✓ Copied to CLIPBOARD & PRIMARY", THEME["status_running"])
        else:
            self.show_toast("Error copying via xclip", THEME["status_stopped"])

    def _delete_selected(self):
        """Delete currently selected clip from history."""
        if not self.cards or not (0 <= self.selected_index < len(self.cards)):
            return

        target_card = self.cards[self.selected_index]
        text_to_delete = target_card.data.get("text")

        self.history = [e for e in self.history if e.get("text") != text_to_delete]
        self._save_history()
        self._filter_clips()
        self.show_toast("✓ Clip deleted", THEME["key_fg"])

    def _clear_all(self):
        """Clear entire clipboard history."""
        self.history.clear()
        self._save_history()
        self._filter_clips()
        self.show_toast("✓ Clipboard history cleared", THEME["status_stopped"])

    # ==========================================================================
    # Keyboard Navigation & Bindings
    # ==========================================================================
    def _bind_keys(self):
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("q", self._on_q)
        self.root.bind("<slash>", self._on_slash)
        self.root.bind("j", lambda e: self._navigate(1) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("k", lambda e: self._navigate(-1) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("<Down>", lambda e: self._navigate(1))
        self.root.bind("<Up>", lambda e: self._navigate(-1))
        self.root.bind("<Return>", lambda e: self._copy_and_toast())
        self.root.bind("c", lambda e: self._copy_and_toast() if self.root.focus_get() != self.search_entry else None)
        self.root.bind("d", lambda e: self._delete_selected() if self.root.focus_get() != self.search_entry else None)
        self.root.bind("<Delete>", lambda e: self._delete_selected() if self.root.focus_get() != self.search_entry else None)
        self.root.bind("<C>", lambda e: self._clear_all() if self.root.focus_get() != self.search_entry else None)

    def _navigate(self, delta: int):
        if not self.cards:
            return
        new_idx = max(0, min(len(self.cards) - 1, self.selected_index + delta))
        if new_idx != self.selected_index:
            self._select_card(self.cards[new_idx])

            # Auto-scroll into view if needed
            fraction = new_idx / max(1, len(self.cards) - 1)
            self.canvas.yview_moveto(max(0.0, fraction - 0.2))

    def _on_close(self):
        self.polling_active = False
        self.root.destroy()

    def _on_escape(self, event):
        if self.root.focus_get() == self.search_entry and self.search_var.get():
            self.search_var.set("")
            self.root.focus_set()
        else:
            self._on_close()

    def _on_q(self, event):
        if self.root.focus_get() != self.search_entry:
            self._on_close()

    def _on_slash(self, event):
        if self.root.focus_get() != self.search_entry:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            return "break"


def main():
    root = tk.Tk(className="clip-pad")
    app = ClipPadApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
